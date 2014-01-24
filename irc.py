#!/usr/bin/python
""" 
	@author Tyler 'Olaf' Stokes <tystokes@umich.edu> 
	Written for python 3. Stay mad.
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
			print("Received msg:")
			print(data)
			if data.find("PING") != -1:
				send(irc, "PONG " + data.split()[1] + "\r\n")
				lastPing = time.time()
			if data.find("VERSION") != -1:
				send(irc, "VERSION irssi [x86] / Linux \r\n")
			if data.find("DCC SEND") != -1:
				(filename, ip, port, filesize) = [t(s) for t,s in zip((str,int,int,int),
					re.search('DCC SEND \"*([^"]+)\"* (\d+) (\d+) (\d+)',data).groups())]
				packedValue = struct.pack('!I', ip)
				host = socket.inet_ntoa(packedValue)
				DCCThread(filename, host, port, filesize).start()
			if (time.time() - lastPing) > 300:
				print("Connection timed out.")
				break

"""	An IRCConnection acts as the 'command thread'.
	It starts a ListenerThread so it doesn't have
	to worry about 'blocking' recv calls."""
class IRCConnection:
	def __init__(self):
		self.host = "irc.rizon.net"
		self.port = 6667
		self.nick = "roughneck"
		self.ident = "roughneck"
		self.realname = "roughneck"
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.settimeout(300)
		self.connected = False
		self.listenerThread = ListenerThread(self)

	def connect(self):
		while not self.connected:
			try:
				self.sock.connect((self.host, self.port))
				self.listenerThread.start()
				#usage example:
				send(self.sock, "NICK %s\r\n" % self.nick)
				send(self.sock, "USER %s %s * :%s\r\n"
					% (self.ident, self.host, self.realname))
				#sleep to make sure nick/usr is registered before anything else
				time.sleep(5)
				#send(self.sock, "PRIVMSG Ginpachi-Sensei :XDCC SEND #1\r\n")
				for i in range(4912, 4914):
					send(self.sock, "PRIVMSG Ginpachi-Sensei :XDCC SEND #" + str(i) + "\r\n")
					time.sleep(15)
				self.connected = True
			except socket.error:
				time.sleep(5)
				print("Connection failed... retrying.")
				continue
#usage example
IRCConnection().connect()