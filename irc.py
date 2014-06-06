#!/usr/bin/python
""" 
    @author Tyler 'Olaf' Stokes <tystokes@umich.edu> 
    An automated lightweight irc client able to interact with XDCC bots.
    Written for python 3.
"""
import socket
import logging
from struct import pack
from time import time, sleep, localtime, asctime
from re import search, sub
from os.path import isfile, getsize
from math import log
from threading import Thread, Lock, Condition
from sys import getfilesystemencoding
from hashlib import md5

encoding = getfilesystemencoding()

# Set us up a log file
logging.getLogger().addHandler(logging.FileHandler(filename = "irc.log", mode = "w", encoding = encoding))
logging.getLogger().setLevel(logging.INFO)
# Global filesystem lock so threads don't make false assumptions over filesystem info.
# Acquired whenever a thread wants to access/use filesystem info (EX: os.path.isfile()).
filesystemLock = Lock()

# Global print lock So multiple threads will not print to the console at the same time
printLock = Lock()

"""
    Converts a string to bytes with a UTF-8 encoding
    the bytes are then sent over the socket.
"""
def send(ircConnection, string):
    ircConnection.socket.send(bytes(string, "UTF-8"))

""" Human readable filesize conversion. """
def convertSize(size):
    names = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    i = int(0)
    if size > 0:
        i = int(log(size, 1024))
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

"""
    A DCCThread handles a DCC SEND request by
    opening up the specified port and receiving the file.
"""
class DCCThread(Thread):
    def __init__(self, filename, host, port, filesize, ircConnection, sender, md5check = False):
        Thread.__init__(self)
        self.ircCon = ircConnection
        self.filename = filename
        self.host = host
        self.port = port
        self.filesize = filesize
        self.bot = sender
        self.md5check = md5check
    def run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(200)
        self.socket.connect((self.host, self.port))
        # make sure we are the only thread looking at the filesystem
        filesystemLock.acquire()
        # File conflict resolution
        while isfile(self.filename):
            if self.shouldOverwrite():
                break
            if self.shouldRename():
                continue
            if self.ircCon.gui == None:
                self.ircCon.lockPrint(self.filename + " already exists, closing socket.")
            else:
                with printLock:
                    self.ircCon.gui.addLine(self.filename)
                    self.ircCon.gui.addLine(" already exists, closing socket.\n", self.ircCon.gui.redText)
            self.socket.close()
            filesystemLock.release()
            return False
        if self.ircCon.gui == None:
            self.ircCon.lockPrint("Downloading " + self.filename + " [" + convertSize(self.filesize) + "]")
        else:
            with printLock:
                self.ircCon.gui.addLine("Downloading", self.ircCon.gui.cyanText)
                self.ircCon.gui.addLine(" " + self.filename + " ")
                self.ircCon.gui.addLine("[" + convertSize(self.filesize) + "]\n", self.ircCon.gui.greenText)
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
                except socket.error as socketerror:
                    self.ircCon.lockPrint("Error: " + str(socketerror))
                    logging.warning("Exception occurred during DCC recv.")
                    self.socket.close()
                    return
                bytesReceived += len(tmp)
                if len(tmp) <= 0:
                    self.ircCon.lockPrint("DCC Error: Socked closed.")
                    logging.warning("DCC Error: Socked closed.")
                    break
                f.write(tmp)
            f.close()
            if self.ircCon.gui == None:
                self.ircCon.lockPrint("Transfer of " + self.filename + " complete.")
            else:
                with printLock:
                    self.ircCon.gui.addLine("Transfer of ", self.ircCon.gui.cyanText)
                    self.ircCon.gui.addLine(self.filename)
                    self.ircCon.gui.addLine(" complete.\n", self.ircCon.gui.cyanText)
        except:
            logging.warning("Exception occurred during file writing.")
        return True
    def shouldOverwrite(self): # Perhaps take in user input?
        if search(r".txt\Z", self.filename):
            if self.md5check:
                if getsize(self.filename) != self.filesize:
                    return True
                else:
                    self.ircCon.md5Conditions[self.bot] = Condition(Lock())
                    md5NotEqual = True
                    with self.ircCon.md5Conditions[self.bot]:
                        # TODO: assumes pack 1 for now
                        self.ircCon.msg(self.bot, "XDCC INFO #1")
                        self.ircCon.md5Conditions[self.bot].wait()
                        if self.bot in self.ircCon.md5Data:
                            with open(self.filename, 'rb') as f:
                                curmd5 = str(md5(f.read()).hexdigest())
                                self.ircCon.logInfo(curmd5)
                                self.ircCon.logInfo(self.ircCon.md5Data[self.bot])
                                if curmd5 == self.ircCon.md5Data[self.bot]:
                                    md5NotEqual = False
                                    self.ircCon.lockPrint("md5sums are equal, not replacing.")
                    del self.ircCon.md5Conditions[self.bot]
                    return md5NotEqual
            else:
                return True
        return False
    def shouldRename(self): # Perhaps take in user input?
        return False

"""
    A ListenerThread blocks until it receives bytes on the irc socket.
    It then spawns a IRCParseThread that handles parsing the data.
"""
class ListenerThread(Thread):
    def __init__(self, ircConnection):
        Thread.__init__(self)
        self.ircCon = ircConnection
        self.die = False
    """ Main parse loop receives data and parses it for requests. """
    def run(self):
        started = time()
        while not self.die:
            data = str()
            try:
                data = str(self.ircCon.socket.recv(512), encoding = "UTF-8", errors = "ignore")
            except socket.timeout as socketerror:
                self.reconnect("Error: Socket timout. Reconnecting.")
                return
            except socket.error as socketerror:
                self.ircCon.lockPrint("Error: " + str(socketerror))
                self.ircCon.lockPrint("Quitting listener thread.")
                return
            # recv returns 0 only when the connection is lost
            if len(data) == 0:
                self.reconnect("Error: Connection to server lost. Reconnecting.")
                return

            lines = data.split("\r\n")
            for l in lines:
                pt = IRCParseThread(self.ircCon, l + "\r\n")
                pt.daemon = True
                pt.start()
    def reconnect(self, msg):
        self.ircCon.lockPrint(msg)
        self.ircCon.listenerThread = ListenerThread(self.ircCon)
        self.ircCon.connect()

""" Handles parsing incoming data from the irc socket. """
class IRCParseThread(Thread):
    def __init__(self, ircConnection, data):
        Thread.__init__(self)
        self.ircCon = ircConnection
        self.data = data
    def run(self):
        self.ircCon.logInfo("\"" + self.data + "\"")
        # check for PING request
        tmp = search(r"PING (:[^\r^\n]+)\r\n", self.data)
        if tmp:
            send(self.ircCon, "PONG " + tmp.group(1) + "\r\n")
        # check for welcome message
        tmp = search(r"Welcome to the[^:]+" + self.ircCon.nick , self.data)
        if tmp:
            if self.ircCon.connectedCondition != None:
                with self.ircCon.connectedCondition:
                    self.ircCon.connectedCondition.notify()
        # check for channel join
        tmp = search(r":" + self.ircCon.nick + r"![^:^!]+ JOIN :#([^\r^\n]+)\r\n", self.data)
        if tmp:
            chan = tmp.group(1).lower()
            if chan in self.ircCon.joinConditions:
                with self.ircCon.joinConditions[chan]:
                    self.ircCon.joinConditions[chan].notify()
        # check for DCC VERSION request
        tmp = search(r"[^\"]*PRIVMSG " + self.ircCon.nick + r" :\x01VERSION\x01", self.data)
        if tmp:
            self.ircCon.notice(self.ircCon, "VERSION irc.py")
        # check for DCC SEND request
        tmp = search(r"PRIVMSG " + self.ircCon.nick + r" :\x01DCC SEND ", self.data)
        if tmp:
            self.parseSend()
        # recv md5 data for a file
        tmp = search(r":([^!^:]+)![^!]+NOTICE " + self.ircCon.nick + r" : md5sum +([a-f0-9]+)", self.data)
        if tmp:
            self.ircCon.logInfo("Got md5 sum")
            bot = tmp.group(1)
            md5sum = tmp.group(2)
            if bot in self.ircCon.md5Conditions:
                self.ircCon.logInfo("bot in md5Conditions")
                with self.ircCon.md5Conditions[bot]:
                    self.ircCon.md5Data[bot] = md5sum
                    self.ircCon.md5Conditions[bot].notify_all()
        for b, t in self.ircCon.packlistStartTime.items():
            if time() - t > 30:
                with self.ircCon.packlistConditions[b]:
                    self.ircCon.packlistStartTime[b] = False
                    self.ircCon.packlistConditions[b].notify()
    """ Parse self.data for a valid DCC SEND request. """
    def parseSend(self):
        (sender, filename, ip, port, filesize) = (None, None, None, None, None)
        try:
            (sender, filename, ip, port, filesize) = [t(s) for t,s in zip((str,str,int,int,int),
            search(r":([^!^:]+)![^!]+DCC SEND \"*([^\"]+)\"* :*(\d+) (\d+) (\d+)",self.data).groups())]
        except:
            logging.warning("Malformed DCC SEND request, ignoring...")
            return
        # unpack the ip to get a proper hostname
        host = socket.inet_ntoa(pack("!I", ip))
        dcc = DCCThread(filename, host, port, filesize, self.ircCon, sender)
        dcc.daemon = True
        dcc.start() # start the thread
        newfile = dcc.join() # wait for the thread to finish
        # notify anyone waiting on the packlistCondition for this bot
        if sender in self.ircCon.packlistConditions:
            with self.ircCon.packlistConditions[sender]:
                self.ircCon.packlists[sender] = filename
                self.ircCon.packlistConditions[sender].notify_all()
        # notify anyone waiting on the responseCondition for this bot
        if sender in self.ircCon.responseConditions:
            with self.ircCon.responseConditions[sender]:
                self.ircCon.responseConditions[sender].notify_all()

"""
    A PacklistParsingThread searches an XDCC bot's packlist
    for packs that match user-specified keywords.
"""
class PacklistParsingThread(Thread):
    # default sleepTime is 3 hours
    def __init__(self, ircConnection, bot, series, sleepTime = 3600 * 3):
        Thread.__init__(self)
        self.filename = None
        self.bot = bot
        self.ircCon = ircConnection
        self.die = False
        self.series = series
        self.f = None
        self.sleepTime = sleepTime
    def run(self):
        while not self.die:
            startTime = time()
            self.ircCon.packlistStartTime[self.bot] = startTime
            if self.ircCon.gui == None:
                self.ircCon.printAndLogInfo(asctime(localtime()) + " - Checking " + self.bot +" for packs.")
            else:
                with printLock:
                    self.ircCon.gui.addLine(asctime(localtime()), self.ircCon.gui.yellowText)
                    self.ircCon.gui.addLine(" - Checking ")
                    self.ircCon.gui.addLine(self.bot, self.ircCon.gui.magentaText)
                    self.ircCon.gui.addLine(" for packs.\n")
            packlistArrived = self.waitOnPacklist()
            self.parseFile()
            if self.ircCon.gui == None:
                self.ircCon.printAndLogInfo("Finished checking " + self.bot + " for packs.")
            else:
                with printLock:
                    self.ircCon.gui.addLine("Finished checking ")
                    self.ircCon.gui.addLine(self.bot, self.ircCon.gui.magentaText)
                    self.ircCon.gui.addLine(" for packs.\n")
            timeShouldSleep = self.sleepTime - (time() - startTime)
            del self.ircCon.packlistStartTime[self.bot]
            if packlistArrived and timeShouldSleep > 0:
                sleep(timeShouldSleep)
    def waitOnPacklist(self):
            self.ircCon.msg(self.bot, "XDCC SEND #1")
            if self.bot not in self.ircCon.packlistConditions:
                self.ircCon.packlistConditions[self.bot] = Condition(Lock())
            with self.ircCon.packlistConditions[self.bot]:
                self.ircCon.packlistConditions[self.bot].wait()
                if not self.ircCon.packlistConditions[self.bot]:
                    self.ircCon.logInfo(self.filename + " not received. Request timed out.")
                    return False
                elif self.ircCon.packlists[self.bot] == None:
                    return False
                else:
                    self.filename = self.ircCon.packlists[self.bot]
                    self.ircCon.logInfo(self.filename + " received.")
                    return True
    def parseFile(self):
        f = None
        try :
            f = open(self.filename, mode = "r", encoding = encoding, errors = "ignore")
        except OSError:
            f.close()
            self.ircCon.printAndLogInfo("Error: Unable to open file during parseFile().")
            return
        for line in f:
            (pack, dls, size, name) = (None, None, None, None)
            try:
                (pack, dls, size, name) = [t(s) for t,s in zip((str,int,str,str),
                search(r"(\S+)[ ]+(\d+)x \[([^\[^\]]+)\] ([^\"^\n]+)", line).groups())]
            except:
                continue
            for s in self.series:
                goodCandidate = True
                for kw in s:
                    if not search(kw, name):
                        goodCandidate = False
                        break
                if not goodCandidate:
                    continue
                logging.debug("candidate: " + name)
                filesystemLock.acquire()
                if not isfile(name):
                    if self.ircCon.gui == None:
                        self.ircCon.printAndLogInfo("Requesting pack " + pack + " " + name)
                    else:
                        with printLock:
                            self.ircCon.gui.addLine("Requesting pack ", self.ircCon.gui.cyanText)
                            self.ircCon.gui.addLine(pack, self.ircCon.gui.yellowText)
                            self.ircCon.gui.addLine(" " + name + "\n")
                    self.ircCon.responseConditions[self.bot] = Condition(Lock())
                    with self.ircCon.responseConditions[self.bot]:
                        self.ircCon.msg(self.bot, "XDCC SEND %s" % pack)
                        filesystemLock.release()
                        self.ircCon.responseConditions[self.bot].wait()
                    del self.ircCon.responseConditions[self.bot]
                else:
                    filesystemLock.release()
                    logging.debug("File already exists.")
        f.close()

""" 
    An IRCConnection acts as the 'command thread'.
    It starts a ListenerThread so it doesn't have
    to worry about 'blocking' recv calls.
"""
class IRCConnection:
    def __init__(self, network, port, nick, window = None):
        self.host, self.port = network, port
        self.nick = self.ident = self.realname = nick
        self.gui = window
        # stores the filenames of the packlists for each bot
        # assuming bot names are unique and, on an irc server, they are
        self.packlists = dict()
        # stores packlist cv's for each bot
        self.packlistConditions = dict()
        self.packlistStartTime = dict()
        # listens for md5 info
        self.md5Conditions = dict()
        self.md5Data = dict()
        # stores response cv's for each bot
        self.responseConditions = dict()
        # stores join cv's for each channel
        self.joinConditions = dict()
        self.listenerThread = ListenerThread(self)
        self.connect()

    def connect(self):
        while True:
            try:
                self.connectedCondition = Condition(Lock())
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(300)
                self.socket.connect((self.host, self.port))
                # supply the standard nick and user info to the server
                send(self, "NICK %s\r\n" % self.nick)
                send(self, "USER %s %s * :%s\r\n"
                    % (self.ident, self.host, self.realname))
                with self.connectedCondition:
                    self.listenerThread.daemon = True
                    self.listenerThread.start()
                    self.connectedCondition.wait()
                self.connectedCondition = None
                if self.gui == None:
                    self.lockPrint("Connected to " + self.host + " as " + self.nick + ".")
                else:
                    self.gui.addLine("Connected to ", self.gui.cyanText)
                    self.gui.addLine(self.host, self.gui.yellowText)
                    self.gui.addLine(" as ")
                    self.gui.addLine(self.nick, self.gui.magentaText)
                    self.gui.addLine(".\n")
                return
            except socket.error:
                self.printAndLogInfo("Error: Connection failed.")
            sleep(10)

    def catchSend(self, string):
        try:
            send(self, string)
        except Exception as e:
            self.lockPrint("catchSend() error: {0}".format(e))
            self.connect()

    def msg(self, who, what):
        self.catchSend("PRIVMSG %s :%s\r\n" % (who, what))

    def notice(self, who, what):
        self.catchSend("NOTICE %s :\x01%s\x01\r\n" % (who, what))

    def join(self, chan):
        chan = sub(r"[#]", "", chan)
        chan = chan.lower()
        self.joinConditions[chan] = Condition(Lock())
        with self.joinConditions[chan]:
            self.catchSend("JOIN #%s\r\n" % chan)
            self.joinConditions[chan].wait()
        del self.joinConditions[chan]
        if self.gui == None:
            self.lockPrint("Joined channel #" + chan + ".")
        else:
            self.gui.addLine("Joined channel ", self.gui.cyanText)
            self.gui.addLine("#" + chan, self.gui.yellowText)
            self.gui.addLine(".\n")

    """ Acquires the print lock then both logs the info and prints it """
    def printAndLogInfo(self, string):
        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            logging.info(s)
            self.printInfo(s)

    """ Acquires the print lock then prints the string """
    def lockPrint(self, string):
        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            self.printInfo(s)

    """ Acquires the print lock then logs the string """
    def logInfo(self, string):
        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            logging.info(s)

    def printInfo(self, string):
        if self.gui == None:
            print(string)
        else:
            color = 0
            if "error:" in string.lower():
                color = self.gui.redText
            self.gui.addLine(string + "\n", color)
