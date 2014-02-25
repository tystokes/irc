#!/usr/bin/python
""" 
	@author Tyler 'Olaf' Stokes <tystokes@umich.edu> 
	A bot able to accept dcc transfers using the irc protocol
	Written for python 3.
"""
import sys
import socket
import string
import os
import platform
import time
import threading
import struct
import re
import codecs
from threading import Thread

"""	Converts a string to bytes with a UTF-8 encoding
	the bytes are then sent over the socket."""
def send(socket, string):
	socket.send(bytes(string, "UTF-8"))

"""	A DCCThread handles a DCC SEND request by
	opening up the specified port and receiving the file."""
class DCCThread(Thread):
	def __init__(self, filename, host, port, filesize):
		Thread.__init__(self)
		self.filename = filename
		self.host = host
		self.port = port
		self.filesize = filesize
	def run(self):
		print("running DCCThread")
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
		# Overwrite file
		with open(self.filename, "w") as f:
			f.write(str())
		f.close()
		totalBytes = 0
		try:
			while totalBytes != self.filesize:
				tmp = self.sock.recv(4096)
				totalBytes += len(tmp)
				if len(tmp) <= 0:
					print("DCC error: Socked closed.")
					break
				# Append to file
				with open(self.filename, "ab") as f:
					f.write(tmp)
				f.close()
		except:
			raise
		print("DCC complete: closing socket.")
		self.sock.close()
	def shouldOverwrite(self): # Perhaps take in user input?
		if re.search('.txt\Z', self.filename):
			return True
		return False
	def shouldRename(self): # Perhaps take in user input?
		return False

"""	A ListenerThread blocks until it receives bytes on the irc socket.
	It then attempts to respond according to normal irc protocol."""
class ListenerThread(Thread):
	def __init__(self, ircConnection):
		Thread.__init__(self)
		self.ircConnection = ircConnection
		self.die = False
	def run(self):
		irc = self.ircConnection.sock
		lastPing = time.time()
		while not self.die:
			data = str(irc.recv(1024), encoding = "UTF-8")
			if len(data) == 0:
				print("Connection to server lost.")
				break
			if data.find("PING") != -1:
				send(irc, "PONG " + data.split()[1] + "\r\n")
				lastPing = time.time()
				continue
			print("Received msg:")
			print(data)
			if data.find("VERSION") != -1:
				send(irc, "VERSION irssi v0.8.12 \r\n")
			if data.find("DCC SEND") != -1:
				try:
					(filename, ip, port, filesize) = [t(s) for t,s in zip((str,int,int,int),
						re.search('DCC SEND \"*([^"]+)\"* (\d+) (\d+) (\d+)',data).groups())]
					packedValue = struct.pack('!I', ip)
					host = socket.inet_ntoa(packedValue)
					DCCThread(filename, host, port, filesize).start()
				except:
					print("back DCC SEND request, ignoring...")
			if (time.time() - lastPing) > 300:
				print("Connection timed out.")
				break
""" A ParseThread searches an XDCC bot's packlist
	for packs that match user-specified keywords."""
class ParseThread(Thread):
	def __init__(self, ircConnection, bot, filename, series):
		Thread.__init__(self)
		self.filename = filename
		self.bot = bot
		self.ircConnection = ircConnection
		self.die = False
		self.series = series
	def run(self):
		while not self.die:
			sleepTime = 60*60*3
			print("Checking for packs. " + time.asctime(time.localtime()))
			self.ircConnection.msg(self.bot, "XDCC SEND #1")
			time.sleep(5)
			sleepTime -= 5
			f = codecs.open(self.filename, "r", "utf-8")
			for line in f:
				try:
					(pack, dls, size, name) = [t(s) for t,s in zip((str,int,str,str),
					re.search('(\S+)[ ]+(\d+)x \[([^\[^\]]+)\] ([^"]+)\n', line).groups())]
					for s in self.series:
						goodCandidate = True
						for kw in s:
							if name.find(kw) == -1:
								goodCandidate = False
								break
						if goodCandidate:
							print(name + " looks like a good candidate.")
							if not os.path.isfile(name):
								self.ircConnection.msg(self.bot, "XDCC SEND %s" % pack)
								time.sleep(20) # wait 20 sec so we aren't spamming the bot
								sleepTime -= 20
							else:
								print("File already exists.")
				except:
					continue
			f.close()
			print("Finished checking for packs.")
			time.sleep(sleepTime)
"""	An IRCConnection acts as the 'command thread'.
	It starts a ListenerThread so it doesn't have
	to worry about 'blocking' recv calls."""
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
				print("Connection failed... retrying.")
				continue
	def msg(self, who, what):
		send(self.sock, "PRIVMSG %s :%s\r\n" % (who, what))

""" usage example """
# IRCConnection(network, port, nick)
con = IRCConnection("irc.rizon.net", 6667, "roughneck")
# A bot I use often on the rizon network
gin = "Ginpachi-Sensei"
# Fill in keywords to look for each series
series = [["Anime X","[Doki]","01"], # Anime X episode 01 by Doki
	["Anime Y","[HorribleSubs]"]] # All episodes of Anime Y by HorribleSubs
# ParseThread will parse the bot's packlist every 3 hours looking for packs that fit the keyword set
ParseThread(con, gin, "Gin.txt", series).start()