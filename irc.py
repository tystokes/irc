#!/usr/bin/python
""" 
	@author Tyler 'Olaf' Stokes <tystokes@umich.edu> 
	An automated lightweight irc client able to interact with XDCC bots.
	Written for python 3.
"""
import math, sys, socket, string, os, platform, time, threading, struct
import re, io, logging
from threading import Thread

# Set us up a log file
logging.basicConfig(filename='irc.log', level=logging.INFO)

# Global filesystem lock so threads don't make false assumptions over filesystem info.
# Acquired whenever a thread wants to access/use filesystem info (EX: os.path.isfile()).
filesystemLock = threading.Lock()

# Global print lock So multiple threads will not print to the console at the same time
printLock = threading.Lock()

"""	Converts a string to bytes with a UTF-8 encoding
	the bytes are then sent over the socket. """
def send(ircConnection, string):
	ircConnection.socket.send(bytes(string, "UTF-8"))

""" Acquires the print lock then both logs the info and prints it """
def printAndLogInfo(string):
	printLock.acquire()
	try:
		logging.info(string)
		print(string)
	except:
		pass
	printLock.release()

""" Acquires the print lock then prints the string """
def lockPrint(string):
	printLock.acquire()
	try:
		print(string)
	except:
		pass
	printLock.release()

""" Acquires the print lock then logs the string """
def logInfo(string):
	printLock.acquire()
	try:
		logging.info(string)
	except:
		pass
	printLock.release()

""" Human readable filesize conversion """
def convertSize(size):
	names = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
	i = int(math.log(size, 1024) // 1)
	if i >= len(names):
		i = len(names) - 1
	p = 1024 ** i
	s = size/p
	if s >= 10:
		tmp = round(s)
	else:
		tmp = round(s, 1)
	if s > 0:
		return "%s %s" % (tmp, names[i])
	else:
		return "0 B"

"""	A DCCThread handles a DCC SEND request by
	opening up the specified port and receiving the file. """
class DCCThread(Thread):
	def __init__(self, filename, host, port, filesize):
		Thread.__init__(self)
		self.filename = filename
		self.host = host
		self.port = port
		self.filesize = filesize
	def run(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.settimeout(200)
		self.socket.connect((self.host, self.port))
		# File conflict resolution
		filesystemLock.acquire()
		while os.path.isfile(self.filename):
			if self.shouldOverwrite():
				break
			if self.shouldRename():
				continue
			self.socket.close()
			filesystemLock.release()
			return

		lockPrint("Downloading " + self.filename + " [" + convertSize(self.filesize) + "]")
		totalBytes = 0
		try:
			f = open(self.filename, "wb")
			filesystemLock.release()
			while totalBytes != self.filesize:
				tmp = self.socket.recv(4096)
				totalBytes += len(tmp)
				if len(tmp) <= 0:
					lockPrint("DCC error: Socked closed.")
					logging.warning("DCC error: Socked closed.")
					break
				f.write(tmp)
			f.close()
		except:
			logging.warning("Exception occurred during file writing.")
			self.socket.close()
			return
		self.socket.close()
		lockPrint("Transfer of " + self.filename + " complete.")
		return
	def shouldOverwrite(self): # Perhaps take in user input?
		if re.search('.txt\Z', self.filename):
			return True
		return False
	def shouldRename(self): # Perhaps take in user input?
		return False

"""	A ListenerThread blocks until it receives bytes on the irc socket.
	It then attempts to respond according to normal irc protocol. """
class ListenerThread(Thread):
	def __init__(self, ircConnection):
		Thread.__init__(self)
		self.ircCon = ircConnection
		self.die = False
		self.data = str()
	""" Main parse loop receives data and parses it for requests. """
	def run(self):
		lastPing = time.time()
		while not self.die:
			self.data = str()
			try:
				self.data = str(self.ircCon.socket.recv(512), encoding = "UTF-8", errors="ignore")
				logInfo(self.data)
			except UnicodeDecodeError:
				logging.warning("UnicodeDecodeError in ListenerThread continuing...")
				continue
			if len(self.data) == 0:
				lockPrint("Connection to server lost.")
				break
			tmp = re.search("PING (:[^\r^\n]+)\r\n", self.data)
			if tmp:
				try :
					send(self.ircCon, "PONG " + tmp.group(1) + "\r\n")
					lastPing = time.time()
				except:
					pass
			if re.search("[^\"]*PRIVMSG " + self.ircCon.nick + " :\x01VERSION\x01", self.data):
				send(self.ircCon, "VERSION irssi v0.8.12 \r\n")
			if re.search("PRIVMSG " + self.ircCon.nick + " :\x01DCC SEND ", self.data):
				self.parseSend()
			tmp = re.search(":([^!^:]+)![^!^:]+NOTICE " + self.ircCon.nick + " :[*]{2}[^:]+queue", self.data)
			if tmp:
				bot = tmp.group(1)
				logInfo("queue notice: " + bot)
				if bot in self.ircCon.responseConditions:
					self.ircCon.responseConditions[bot].acquire()
					logInfo("notifying_all response waiters" + bot)
					self.ircCon.responseConditions[bot].notify_all()
					self.ircCon.responseConditions[bot].release()
		return
	""" Parse self.data for a valid DCC SEND request. """
	def parseSend(self):
		try:
			(self.sender, self.filename, self.ip, self.port, self.filesize) = [t(s) for t,s in zip((str,str,int,int,int),
			re.search(':([^!^:]+)![^!]+DCC SEND \"*([^"]+)\"* (\d+) (\d+) (\d+)', self.data).groups())]
		except:
			logging.warning("Malformed DCC SEND request, ignoring...")
		
		if self.sender in self.ircCon.responseConditions:
			self.ircCon.responseConditions[self.sender].acquire()
			self.ircCon.responseConditions[self.sender].notify_all()
			self.ircCon.responseConditions[self.sender].release()


		# unpack the ip to get a proper hostname
		self.host = socket.inet_ntoa(struct.pack('!I', self.ip))
		dcc = DCCThread(self.filename, self.host, self.port, self.filesize)
		dcc.start()
		dcc.join()
		if self.sender in self.ircCon.packlistConditions:
			self.ircCon.packlistConditions[self.sender].acquire()
			self.ircCon.packlists[self.sender] = self.filename
			self.ircCon.packlistConditions[self.sender].notify_all()
			self.ircCon.packlistConditions[self.sender].release()

""" A ParseThread searches an XDCC bot's packlist
	for packs that match user-specified keywords. """
class ParseThread(Thread):
	def __init__(self, ircConnection, bot, series):
		Thread.__init__(self)
		self.filename = None
		self.bot = bot
		self.ircCon = ircConnection
		self.die = False
		self.series = series
		self.f = None
		self.sleepTime = None
	def run(self):
		while not self.die:
			self.sleepTime = 60*60*3 # 3 hours
			printAndLogInfo(time.asctime(time.localtime()) + " - Checking " + self.bot +" for packs.")
			self.waitOnPacklist()
			self.parseFile()
			printAndLogInfo("Finished checking " + self.bot + " for packs.")
			time.sleep(self.sleepTime)
		return
	def sleep(self, amount):
		time.sleep(amount)
		self.sleepTime -= amount
	def waitOnPacklist(self):
			self.ircCon.msg(self.bot, "XDCC SEND #1")
			self.filename = None
			if self.bot not in self.ircCon.packlistConditions:
				self.ircCon.packlistConditions[self.bot] = threading.Condition(threading.Lock())
			self.ircCon.packlistConditions[self.bot].acquire()
			self.ircCon.packlistConditions[self.bot].wait()
			self.filename = self.ircCon.packlists[self.bot]
			logInfo(self.filename + " received, Thread carrying on.")
			self.ircCon.packlistConditions[self.bot].release()
	def parseFile(self):
		f = io.open(self.filename, mode = "r", encoding = "UTF-8", errors = "ignore")
		for line in f:
			(pack, dls, size, name) = (None, None, None, None)
			try:
				(pack, dls, size, name) = [t(s) for t,s in zip((str,int,str,str),
				re.search('(\S+)[ ]+(\d+)x \[([^\[^\]]+)\] ([^"^\n]+)', line).groups())]
			except:
				continue
			for s in self.series:
				goodCandidate = True
				for kw in s:
					if not re.search(kw, name):
						goodCandidate = False
						break
				if not goodCandidate:
					continue
				logging.debug("candidate: " + name)
				filesystemLock.acquire()
				if not os.path.isfile(name):
					printAndLogInfo("Requesting pack " + pack + " " + name)
					self.ircCon.responseConditions[self.bot] = threading.Condition(threading.Lock())
					self.ircCon.responseConditions[self.bot].acquire()
					self.ircCon.msg(self.bot, "XDCC SEND %s" % pack)
					filesystemLock.release()
					self.ircCon.responseConditions[self.bot].wait()
					self.ircCon.responseConditions[self.bot].release()
					del self.ircCon.responseConditions[self.bot]
				else:
					filesystemLock.release()
					logging.debug("File already exists.")
		f.close()

"""	An IRCConnection acts as the 'command thread'.
	It starts a ListenerThread so it doesn't have
	to worry about 'blocking' recv calls. """
class IRCConnection:
	def __init__(self, network, port, nick):
		self.host = network
		self.port = port
		self.nick = nick
		self.ident = nick
		self.realname = nick
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.settimeout(300)
		self.connected = False
		# stores the filenames of the packlists for each bot
		# assuming bot names are unique and, on an irc server, they are
		self.packlists = dict()
		# stores packlist cv's for each bot
		self.packlistConditions = dict()
		# stores response cv's for each bot
		self.responseConditions = dict()
		
		""" After assigning variables start up a listener thread
			and attempt to connect to server """
		self.listenerThread = ListenerThread(self)
		self.connect()
	def connect(self):
		while not self.connected:
			try:
				self.socket.connect((self.host, self.port))
				self.listenerThread.start()
				# supply the standard nick and user info to the server
				send(self, "NICK %s\r\n" % self.nick)
				send(self, "USER %s %s * :%s\r\n"
					% (self.ident, self.host, self.realname))
				# sleep to make sure nick/usr is registered
				time.sleep(1)
				self.connected = True
			except socket.error:
				time.sleep(5)
				logger.warning("Connection failed... retrying.")
				continue
	def msg(self, who, what):
		send(self, "PRIVMSG %s :%s\r\n" % (who, what))

""" usage example """

# IRCConnection(network, port, nick)
con = IRCConnection("irc.rizon.net", 6667, "roughneck")

# A bot I use often on the rizon network
ginpachi = "Ginpachi-Sensei"

# A bot on #nibl
fanService = "A|FanserviceBot"

# Fill in keywords to search for regarding each series
# now matches as if it's a regular expression
# so be sure to include '\' in front of things like '[',']','(',')', etc...
series = [
	["\[Doki\] Anime A[^^]*\[720p\]"], # All episodes of Anime A by Doki in 720p
	["Anime X","\[Doki\]","01"], # Anime X episode 01 by Doki
	["Anime Y","\[HorribleSubs\]"]] # All episodes of Anime Y by HorribleSubs

# fanService bot requires that you join #nibl
send(con, "Join #nibl\r\n")
time.sleep(1)

# ParseThread will parse the bot's packlist every 3 hours looking for packs that fit the keyword set
# you may parse multiple bots at once searching for the same or different files
ParseThread(con, ginpachi, series).start()
ParseThread(con, fanService, series).start()
