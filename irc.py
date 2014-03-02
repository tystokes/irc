#!/usr/bin/python
""" 
	@author Tyler 'Olaf' Stokes <tystokes@umich.edu> 
	A bot able to accept dcc transfers using the irc protocol
	Written for python 3.
"""
import math, sys, socket, string, os, platform, time, threading, struct
import re, codecs, logging
from threading import Thread

logging.basicConfig(filename='irc.log', level=logging.INFO)

"""	Converts a string to bytes with a UTF-8 encoding
	the bytes are then sent over the socket. """
def send(socket, string):
	socket.send(bytes(string, "UTF-8"))

""" Human readable filesize conversion """
def convertSize(size):
	names = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
	i = int(math.floor(math.log(size, 1024)))
	p = pow(1024, i)
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
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.settimeout(200)
		self.sock.connect((self.host, self.port))
		# File conflict resolution
		while os.path.isfile(self.filename):
			if self.shouldOverwrite():
				break
			if self.shouldRename():
				continue
			self.sock.close()
			return
		print("Downloading: " + self.filename + " ["
			+ convertSize(self.filesize) + "]")
		totalBytes = 0
		try:
			with open(self.filename, "wb") as f:
				while totalBytes != self.filesize:
					tmp = self.sock.recv(4096)
					totalBytes += len(tmp)
					if len(tmp) <= 0:
						print("DCC error: Socked closed.")
						logging.warning("DCC error: Socked closed.")
						break
					f.write(tmp)
			f.close()
		except:
			logging.warning("Exception occurred during file writing.")
			self.sock.close()
			return
		self.sock.close()
		print("Transfer of " + self.filename + " complete.")
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
	def run(self):
		irc = self.ircCon.sock
		lastPing = time.time()
		while not self.die:
			data = str(irc.recv(1024), encoding = "UTF-8")
			logging.info(data)
			if len(data) == 0:
				print("Connection to server lost.")
				break
			elif data.find("PING") != -1:
				send(irc, "PONG " + data.split()[1] + "\r\n")
				lastPing = time.time()
			elif data.find("VERSION") != -1:
				send(irc, "VERSION irssi v0.8.12 \r\n")
			elif data.find("DCC SEND") != -1:
				try:
					(sender, filename, ip, port, filesize) = [t(s) for t,s in zip((str,str,int,int,int),
					re.search(':([^!]+)![^!]+DCC SEND ([^"]+) (\d+) (\d+) (\d+)',data).groups())]
					try:
						self.ircCon.packlistLock.acquire()
						if self.ircCon.catchPacklist[sender] == "yes":
							self.ircCon.packlists[sender] = filename
							self.ircCon.catchPacklist[sender] = "no"
						self.ircCon.packlistLock.release()
					except KeyError:
						self.ircCon.packlistLock.release()
					packedValue = struct.pack('!I', ip)
					host = socket.inet_ntoa(packedValue)
					DCCThread(filename, host, port, filesize).start()
				except:
					logging.warning("Malformed DCC SEND request, ignoring...")
			if (time.time() - lastPing) > 300:
				print("Connection timed out.")
				logging.warning("Connection timed out.")
				break

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
	def run(self):
		while not self.die:
			sleepTime = 60*60*3
			pack_msg = "Checking for packs. " + time.asctime(time.localtime())
			print(pack_msg)
			logging.info(pack_msg)
			try:
				self.ircCon.packlists[self.bot]
			except KeyError:
				self.ircCon.packlistLock.acquire()
				self.ircCon.catchPacklist[self.bot] = "yes"
				self.ircCon.packlistLock.release()
			self.ircCon.msg(self.bot, "XDCC SEND #1")
			time.sleep(5)
			sleepTime -= 5
			while self.filename == None:
				try:
					self.ircCon.packlistLock.acquire()
					self.filename = self.ircCon.packlists[self.bot]
					self.ircCon.packlistLock.release()
					break
				except KeyError:
					self.ircCon.packlistLock.release()
					time.sleep(5)
					sleepTime -= 5
			f = codecs.open(self.filename, "r", "utf-8")
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
						if not re.match("[^\"]*" + kw + "[^\"]*", name):
							goodCandidate = False
							break
					if not goodCandidate:
						continue
					logging.debug("candidate: " + name)
					if not os.path.isfile(name):
						req_msg = "Requesting pack " + pack + " " + name
						print(req_msg)
						logging.info(req_msg)
						self.ircCon.msg(self.bot, "XDCC SEND %s" % pack)
						time.sleep(20) # wait 20 sec so we aren't spamming the bot
						sleepTime -= 20
					else:
						logging.debug("File already exists.")
			f.close()
			print("Finished checking for packs.")
			logging.info("Finished checking for packs.")
			time.sleep(sleepTime)

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
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.settimeout(300)
		self.connected = False
		self.listenerThread = ListenerThread(self)
		self.connect()
		# stores the filenames of the packlists for each bot
		# assuming bot names are unique and, on an irc server, they are
		self.packlists = dict()
		# stores whether or not to catch the packlist on the next DCC SEND from this bot
		self.catchPacklist = dict()
		# A lock for accessing self.packlists and self.catchPacklist between threads
		self.packlistLock = threading.RLock()
	def connect(self):
		while not self.connected:
			try:
				self.sock.connect((self.host, self.port))
				self.listenerThread.start()
				# supply the standard nick and user info to the server
				send(self.sock, "NICK %s\r\n" % self.nick)
				send(self.sock, "USER %s %s * :%s\r\n"
					% (self.ident, self.host, self.realname))
				# sleep to make sure nick/usr is registered
				time.sleep(3)
				self.connected = True
			except socket.error:
				time.sleep(5)
				logger.warning("Connection failed... retrying.")
				continue
	def msg(self, who, what):
		send(self.sock, "PRIVMSG %s :%s\r\n" % (who, what))

""" usage example """
# IRCConnection(network, port, nick)
con = IRCConnection("irc.rizon.net", 6667, "roughneck")
# A bot I use often on the rizon network
gin = "Ginpachi-Sensei"
# Fill in keywords to search for regarding each series
# now matches as if it's a regular expression
# see http://docs.python.org/3.3/library/re.html
# so be sure to include '\' in front of things like '[',']','(',')', etc...
series = [
	["\[Doki\] Anime A[^^]*\[720p\]"] # All episodes of Anime A by Doki in 720p
	["Anime X","\[Doki\]","01"], # Anime X episode 01 by Doki
	["Anime Y","\[HorribleSubs\]"]] # All episodes of Anime Y by HorribleSubs
# ParseThread will parse the bot's packlist every 3 hours looking for packs that fit the keyword set
ParseThread(con, gin, series).start()
while True:
	tmp = input("")
	# when user types in cmd
	if tmp == "cmd":
		# evaluate the next input
		eval(input("> "))
