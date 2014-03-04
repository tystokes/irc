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
	string.encode("UTF-8", "ignore")
	printLock.acquire()
	logging.info(string)
	print(string)
	printLock.release()

""" Acquires the print lock then prints the string """
def lockPrint(string):
	string.encode("UTF-8", "ignore")
	printLock.acquire()
	print(string)
	printLock.release()

""" Acquires the print lock then logs the string """
def logInfo(string):
	string.encode("UTF-8", "ignore")
	printLock.acquire()
	logging.info(string)
	printLock.release()

""" Human readable filesize conversion """
def convertSize(size):
	names = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
	i = int(math.log(size, 1024) // 1)
	if i >= len(names):
		i = int(len(names) - 1)
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
		# make sure we are the only thread looking at the filesystem
		filesystemLock.acquire()
		# File conflict resolution
		while os.path.isfile(self.filename):
			if self.shouldOverwrite():
				break
			if self.shouldRename():
				continue
			self.socket.close()
			filesystemLock.release()
			return
		lockPrint("Downloading " + self.filename + " [" + convertSize(self.filesize) + "]")
		f = None
		try:
			f = open(self.filename, "wb")
		except OSError:
			self.socket.close()
			return
		finally:
			# we should be good to let other threads look at the filesystem
			filesystemLock.release()
		try:
			bytesReceived = 0
			while bytesReceived != self.filesize:
				tmp = None
				try:
					tmp = self.socket.recv(4096)
				except:
					logging.warning("Exception occurred during DCC recv.")
					self.socket.close()
					return
				bytesReceived += len(tmp)
				if len(tmp) <= 0:
					lockPrint("DCC error: Socked closed.")
					logging.warning("DCC error: Socked closed.")
					break
				f.write(tmp)
			f.close()
			lockPrint("Transfer of " + self.filename + " complete.")
		except:
			logging.warning("Exception occurred during file writing.")
	def shouldOverwrite(self): # Perhaps take in user input?
		if re.search('.txt\Z', self.filename):
			return True
		return False
	def shouldRename(self): # Perhaps take in user input?
		return False

"""	A ListenerThread blocks until it receives bytes on the irc socket.
	It then spawns a IRCParseThread that handles parsing the data. """
class ListenerThread(Thread):
	def __init__(self, ircConnection):
		Thread.__init__(self)
		self.ircCon = ircConnection
		self.die = False
	""" Main parse loop receives data and parses it for requests. """
	def run(self):
		lastPing = time.time()
		while not self.die:
			data = str(self.ircCon.socket.recv(512), encoding = "UTF-8", errors = "ignore")
			# recv returns 0 only when the connection is lost
			if len(data) == 0:
				lockPrint("Connection to server lost.")
				break
			IRCParseThread(self.ircCon, data).start()

"""	Handles parsing incoming data from the irc socket. """
class IRCParseThread(Thread):
	def __init__(self, ircConnection, data):
		Thread.__init__(self)
		self.ircCon = ircConnection
		self.data = data
	def run(self):
		logInfo("\"" + self.data + "\"")
		# check for PING request
		tmp = re.search("PING (:[^\r^\n]+)\r\n", self.data)
		if tmp:
			send(self.ircCon, "PONG " + tmp.group(1) + "\r\n")
			lastPing = time.time()
		# check for DCC VERSION request
		tmp = re.search("[^\"]*PRIVMSG " + self.ircCon.nick + " :\x01VERSION\x01", self.data)
		if tmp:
			send(self.ircCon, "VERSION irssi v0.8.12 \r\n")
		# check for DCC SEND request
		tmp = re.search("PRIVMSG " + self.ircCon.nick + " :\x01DCC SEND ", self.data)
		if tmp:
			self.parseSend()
		# check if you were added to the queue for a pack
		tmp = re.search(":([^!^:]+)![^!^:]+NOTICE " + self.ircCon.nick + " :[*]{2}[^:]+queue", self.data)
		if tmp:
			bot = tmp.group(1)
			logInfo("queue notice: " + bot)
			# notify anyone waiting on the responseCondition for this bot
			if bot in self.ircCon.responseConditions:
				self.ircCon.responseConditions[bot].acquire()
				logInfo("notifying_all response waiters" + bot)
				self.ircCon.responseConditions[bot].notify_all()
				self.ircCon.responseConditions[bot].release()
	""" Parse self.data for a valid DCC SEND request. """
	def parseSend(self):
		(sender, filename, ip, port, filesize) = (None, None, None, None, None)
		try:
			(sender, filename, ip, port, filesize) = [t(s) for t,s in zip((str,str,int,int,int),
			re.search(':([^!^:]+)![^!]+DCC SEND \"*([^"]+)\"* (\d+) (\d+) (\d+)',self.data).groups())]
		except:
			logging.warning("Malformed DCC SEND request, ignoring...")
			return
		# notify anyone waiting on the responseCondition for this bot
		if sender in self.ircCon.responseConditions:
			self.ircCon.responseConditions[sender].acquire()
			self.ircCon.responseConditions[sender].notify_all()
			self.ircCon.responseConditions[sender].release()
		# unpack the ip to get a proper hostname
		host = socket.inet_ntoa(struct.pack('!I', ip))
		dcc = DCCThread(filename, host, port, filesize)
		dcc.start() # start the thread
		dcc.join() # wait for the thread to finish
		# notify anyone waiting on the packlistCondition for this bot
		if sender in self.ircCon.packlistConditions:
			self.ircCon.packlistConditions[sender].acquire()
			self.ircCon.packlists[sender] = filename
			self.ircCon.packlistConditions[sender].notify_all()
			self.ircCon.packlistConditions[sender].release()

""" A PacklistParsingThread searches an XDCC bot's packlist
	for packs that match user-specified keywords. """
class PacklistParsingThread(Thread):
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
			startTime = time.time()
			printAndLogInfo(time.asctime(time.localtime()) + " - Checking " + self.bot +" for packs.")
			self.waitOnPacklist()
			self.parseFile()
			printAndLogInfo("Finished checking " + self.bot + " for packs.")
			time.sleep(self.sleepTime - (time.time() - startTime))
	def waitOnPacklist(self):
			self.ircCon.msg(self.bot, "XDCC SEND #1")
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
PacklistParsingThread(con, ginpachi, series).start()
PacklistParsingThread(con, fanService, series).start()
