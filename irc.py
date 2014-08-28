#!/usr/bin/python
"""
An automated lightweight irc client able to interact with XDCC bots.
Written for python 3.
"""
__author__ = "Tyler 'Olaf' Stokes <tystokes@umich.edu>"

try:
    import gui
    NO_GUI = False
except:
    NO_GUI = True
import socket
import logging
from struct import pack
from time import time, sleep, localtime, asctime
from re import match, search, sub
from os import chdir
from os.path import isfile, getsize, realpath, dirname
from math import log
from threading import Thread, Lock, Condition, Event
from sys import getfilesystemencoding
from hashlib import md5

chdir(realpath(dirname(__file__))) # Switch the current working directory to directory this file is in
encoding = getfilesystemencoding()

# Set us up a log file
logging.getLogger().addHandler(logging.FileHandler(filename = "irc.log", mode = "w", encoding = encoding))
logging.getLogger().setLevel(logging.INFO)
# Global filesystem lock so threads don't make false assumptions over filesystem info.
# Acquired whenever a thread wants to access/use filesystem info (EX: os.path.isfile()).
filesystemLock = Lock()
# Global print lock So multiple threads will not print to the console at the same time
printLock = Lock()
# Regular expression string used to parse IRC messages
MESSAGE_REGEX = r"(:(?P<prefix>((?P<nickname>[^@!\s]+)((((!(?P<user>\S+))?)@(?P<host>\S+))?))|(\S*)) )?(?P<command>\S+) ((?!:)(?P<params>.+?) )?:(?P<trailing>.+)"

def send(ircConnection, string):
    """
    Converts a string to bytes with a UTF-8 encoding
    the bytes are then sent over the socket.
    """
    ircConnection.socket.send(bytes(string, "UTF-8"))

def convertSize(size):
    """Human readable filesize conversion."""
    if size < 0:
        raise ValueError("Negative size.")
    elif size == 0:
        return "0 B"
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
    return "%s %s" % (tmp, names[i])


class DCCThread(Thread):
    """
    A DCCThread handles a DCC SEND request by
    opening up the specified port and receiving the file.
    """
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
        self.socket.settimeout(300)
        try:
            self.socket.connect((self.host, self.port))
        except Exception as e:
            self.ircCon.logInfo("error: {0}".format(e))
            self.ircCon.printAndLogInfo("Socket error, trying again.")
            self.ircCon.msg(self.bot, "XDCC CANCEL")
            self.ircCon.lastRequestedPack[self.bot] = None
            sleep(3)
            return
        # make sure we are the only thread looking at the filesystem
        filesystemLock.acquire()
        # File conflict resolution
        while isfile(self.filename):
            if self.shouldOverwrite():
                break
            if self.shouldRename():
                continue
            if not self.ircCon.gui:
                self.ircCon.lockPrint(self.filename + " already exists, closing socket.")
            else:
                with printLock:
                    self.ircCon.gui.addLine(self.filename)
                    self.ircCon.gui.addLine(" already exists, closing socket.\n", self.ircCon.gui.redText)
            self.socket.close()
            filesystemLock.release()
            return False
        if not self.ircCon.gui:
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
            lastTime = time()
            lastTotal = 0
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
                now = time()
                if now - lastTime > 0.5:
                    rate = int((bytesReceived - lastTotal)/(now - lastTime))
                    lastTime = now
                    lastTotal = bytesReceived
                    if not self.ircCon.gui:
                        self.ircCon.lockPrint(convertSize(rate) + "/s [" +
                            convertSize(bytesReceived) + "/" + convertSize(self.filesize) + "] ")
                    else:
                        with printLock:
                            self.ircCon.gui.addInput(convertSize(rate) + "/s", begin = True)
                            self.ircCon.gui.addInput(" [" + convertSize(bytesReceived) + "/" + convertSize(self.filesize) + "]", self.ircCon.gui.greenText, pad = True)
            f.close()
            if not self.ircCon.gui:
                self.ircCon.lockPrint("Transfer of " + self.filename + " complete.")
            else:
                with printLock:
                    self.ircCon.gui.addLine("Transfer of ", self.ircCon.gui.cyanText)
                    self.ircCon.gui.addLine(self.filename)
                    self.ircCon.gui.addLine(" complete.\n", self.ircCon.gui.cyanText)
                    self.ircCon.gui.clearInput()
        except Exception as e:
            with printLock:
                self.ircCon.printAndLogInfo("Exception occurred during file writing.")
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


class ListenerThread(Thread):
    """
    A ListenerThread blocks until it receives bytes on the irc socket.
    It then spawns a IRCParseThread that handles parsing the data.
    """
    def __init__(self, ircConnection):
        Thread.__init__(self)
        self.ircCon = ircConnection
        self.die = False
        self.data = str()

    def run(self):
        """Main parse loop receives data and parses it for requests."""
        started = time()
        while not self.die:
            try:
                new_data = str(self.ircCon.socket.recv(512), encoding = "UTF-8", errors = "ignore")
            except socket.timeout as socketerror:
                self.reconnect("Error: Socket timout. Reconnecting.")
                return
            except socket.error as socketerror:
                self.ircCon.lockPrint("Error: " + str(socketerror))
                self.ircCon.lockPrint("Quitting listener thread.")
                return
            # recv returns 0 only when the connection is lost
            if len(new_data) == 0:
                self.reconnect("Error: Connection to server lost. Reconnecting.")
                return
            self.data += new_data
            self.ircCon.logInfo("total:\"" + self.data + "\"")
            if '\r\n' not in self.data:
                continue
            lines = self.data.split("\r\n")
            for i in range(0, len(lines)-1):
                if not match(MESSAGE_REGEX, lines[i]):
                    continue
                if lines[i] == "":
                    continue
                pt = IRCParseThread(self.ircCon, lines[i], self)
                pt.daemon = True
                pt.start()
            if lines[len(lines)-1] != "":
                self.data = lines[len(lines)-1]
            else:
                self.data = str()

    def reconnect(self, msg):
        self.ircCon.printAndLogInfo(msg)
        self.ircCon.connect(3)


class IRCParseThread(Thread):
    """Handles parsing incoming data from the irc socket."""
    def __init__(self, ircConnection, data, listenerThread):
        Thread.__init__(self)
        self.ircCon = ircConnection
        self.data = data
        self.listenerThread = listenerThread

    def run(self):
        self.ircCon.logInfo("\"" + self.data + "\"")
        regex = match(MESSAGE_REGEX, self.data)
        nickname, command, params, trailing = regex.group("nickname"), regex.group("command"), regex.group("params"), regex.group("trailing")
        # check for link close
        tmp = search(r"^ERROR :Closing Link:", self.data)
        if tmp:
            if self.ircCon.connectedCondition is not None:
                with self.ircCon.connectedCondition:
                    self.ircCon.unableToConnect = True
                    self.ircCon.connectedCondition.notify()
        if trailing is not None and trailing == "Nickname is already in use.":
            self.ircCon.nick += "_"
            if self.ircCon.connectedCondition is not None:
                with self.ircCon.connectedCondition:
                    self.ircCon.unableToConnect = True
                    self.ircCon.connectedCondition.notify()
        # check for PING request
        if command == "PING" and trailing is not None:
            if self.ircCon.connectedCondition is not None:
                with self.ircCon.connectedCondition:
                    self.ircCon.connectedCondition.notify()
            send(self.ircCon, "PONG :" + trailing + "\r\n")
        # check for welcome message
        if params is not None and params == self.ircCon.nick and search(r"Welcome to the.*" + self.ircCon.nick, trailing):
            if self.ircCon.connectedCondition is not None:
                with self.ircCon.connectedCondition:
                    self.ircCon.connectedCondition.notify()
        # check for channel join
        if command == "JOIN" and nickname is not None and nickname == self.ircCon.nick:
            chan = trailing.lower()
            chan = sub(r"[#]", "", chan)
            if chan in self.ircCon.joinConditions:
                with self.ircCon.joinConditions[chan]:
                    self.ircCon.joinConditions[chan].notify()
        if command == "PRIVMSG" and params is not None and params == self.ircCon.nick:
            if trailing == "\x01VERSION\x01":
                self.ircCon.notice(self.ircCon, "VERSION irc.py")
            elif search(r"\x01DCC SEND", trailing):
                self.parseSend()
        if command == "NOTICE" and params is not None and params == self.ircCon.nick:
            if trailing is not None and search(r"\*\* You can only have .* at a time, Added you to the main queue for", trailing):
                if not self.ircCon.gui:
                    self.ircCon.printAndLogInfo(asctime(localtime()) + " Waiting in queue for pack.")
                else:
                    with printLock:
                        self.ircCon.gui.addLine("Waiting in queue.\n")
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

    def parseSend(self):
        """Parse self.data for a valid DCC SEND request."""
        try:
            (sender, filename, ip, port, filesize) = [t(s) for t,s in zip((str,str,int,int,int),
            search(r":([^!^:]+)![^!]+DCC SEND \"*([^\"]+)\"* :*(\d+) (\d+) (\d+)", self.data).groups())]
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


class PacklistParsingThread(Thread):
    """
    A PacklistParsingThread searches an XDCC bot's packlist
    for packs that match user-specified keywords.
    """
    def __init__(self, ircConnection, bot, series, sleepTime = 3600 * 3, repeat = True):
        Thread.__init__(self)
        self.filename = None
        self.bot = bot
        self.ircCon = ircConnection
        self.die = False
        self.series = series
        self.f = None
        self.sleepTime = sleepTime
        self.repeat = repeat

    def kill(self):
        self.die = True

    def run(self):
        while not self.die:
            startTime = time()
            self.ircCon.msg(self.bot, "XDCC CANCEL")
            sleep(2)
            if not self.ircCon.gui:
                self.ircCon.printAndLogInfo(asctime(localtime()) + " - Checking " + self.bot + " for packs.")
            else:
                with printLock:
                    self.ircCon.gui.addLine(asctime(localtime()), self.ircCon.gui.yellowText)
                    self.ircCon.gui.addLine(" - Checking ")
                    self.ircCon.gui.addLine(self.bot, self.ircCon.gui.magentaText)
                    self.ircCon.gui.addLine(" for packs.\n")
            packlistArrived = self.waitOnPacklist()
            self.parseFile()
            if not self.ircCon.gui:
                self.ircCon.printAndLogInfo("Finished checking " + self.bot + " for packs.")
            else:
                with printLock:
                    self.ircCon.gui.addLine("Finished checking ")
                    self.ircCon.gui.addLine(self.bot, self.ircCon.gui.magentaText)
                    self.ircCon.gui.addLine(" for packs.\n")
            timeShouldSleep = self.sleepTime - (time() - startTime)
            if not self.repeat:
                return
            elif packlistArrived and timeShouldSleep > 0:
                sleep(timeShouldSleep)

    def waitOnPacklist(self):
            self.ircCon.lastRequestedPack[self.bot] = None
            while self.ircCon.lastRequestedPack[self.bot] == None:
                self.ircCon.lastRequestedPack[self.bot] = "#1"
                self.ircCon.msg(self.bot, "XDCC SEND #1")
                if self.bot not in self.ircCon.packlistConditions:
                    self.ircCon.packlistConditions[self.bot] = Condition(Lock())
                with self.ircCon.packlistConditions[self.bot]:
                    self.ircCon.packlistConditions[self.bot].wait()
                    self.ircCon.logInfo("waitOnPacklist lastRequestedPack: " + str(self.ircCon.lastRequestedPack[self.bot]))
                    if self.ircCon.lastRequestedPack[self.bot] == None:
                        self.ircCon.logInfo("waitOnPacklist continuing")
                        continue
                    if not self.bot in self.ircCon.packlists or not self.ircCon.packlists[self.bot]:
                        return False
                    else:
                        self.filename = self.ircCon.packlists[self.bot]
                        self.ircCon.logInfo(self.filename + " received.")
                        return True

    def parseFile(self):
        with open(self.filename, mode = "r", encoding = encoding, errors = "ignore") as f:
            lines = f.read().splitlines()
        for series in self.series:
            for line in lines:
                try:
                    (self.pack, self.dls, self.size, self.name) = [t(s) for t,s in zip((str,int,str,str),
                    search(r"(\S+) +(\d+)x \[([^\[^\]]+)\] ([^\"^\n]+)", line).groups())]
                    if not search(series, self.name):
                        raise Exception("regex failure")
                    self.checkCandidate()
                except:
                    continue

    def checkCandidate(self):
        self.ircCon.logInfo("candidate: " + self.name)
        filesystemLock.acquire()
        if not isfile(self.name):
            filesystemLock.release()
            if not self.ircCon.gui:
                self.ircCon.printAndLogInfo("Requesting pack " + self.pack + " " + self.name)
            else:
                with printLock:
                    self.ircCon.gui.addLine("Requesting pack ", self.ircCon.gui.cyanText)
                    self.ircCon.gui.addLine(self.pack, self.ircCon.gui.yellowText)
                    self.ircCon.gui.addLine(" " + self.name + "\n")
            self.ircCon.lastRequestedPack[self.bot] = None
            while self.ircCon.lastRequestedPack[self.bot] == None:
                self.ircCon.responseConditions[self.bot] = Condition(Lock())
                self.ircCon.lastRequestedPack[self.bot] = self.pack
                with self.ircCon.responseConditions[self.bot]:
                    self.ircCon.msg(self.bot, "XDCC SEND %s" % self.pack)
                    self.ircCon.responseConditions[self.bot].wait()
                del self.ircCon.responseConditions[self.bot]
        else:
            filesystemLock.release()
            self.ircCon.logInfo("File already exists.")


class IRCConnection:
    """
    An IRCConnection acts as the 'command thread'.
    It starts a ListenerThread so it doesn't have
    to worry about 'blocking' recv calls.
    """
    def __init__(self, network, nick, gui = False):
        port_regex = search(r":([0-9]+)\Z", network)
        if port_regex:
            port_string = port_regex.group(1)
            self.host = network[:-(len(port_string)+1)]
            self.port = int(port_string)
        else:
            self.host = network
            self.port = 6667
        self.nick = self.ident = self.realname = nick
        self.gui = gui
        if gui and not NO_GUI:
            self.initializeGUI()
        elif gui:
            self.gui = False
            print("No curses module detected. Install curses or run with gui = False.")
        self.lastRequestedPack = dict()
        # stores the filenames of the packlists for each bot
        # assuming bot names are unique and, on an irc server, they are
        self.packlists = dict()
        # stores packlist cv's for each bot
        self.packlistConditions = dict()
        # listens for md5 info
        self.md5Conditions = dict()
        self.md5Data = dict()
        # stores response cv's for each bot
        self.responseConditions = dict()
        # stores join cv's for each channel
        self.joinConditions = dict()
        self.connect()

    def initializeGUI(self):
        window_ready = Event()
        self.gui = gui.IRCWindow(window_ready)
        self.gui.daemon = True
        self.gui.start()
        window_ready.wait() # wait for window to be initialized

    def connect(self, timeout = 0):
        while True:
            try:
                self.printAndLogInfo("Attempting to connect.")
                if timeout > 0:
                    sleep(timeout)
                self.connectedCondition = Condition(Lock())
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(300)
                self.socket.connect((self.host, self.port))
                # supply the standard nick and user info to the server
                send(self, "NICK %s\r\n" % self.nick)
                send(self, "USER %s %s * :%s\r\n"
                    % (self.ident, self.host, self.realname))
                self.unableToConnect = False
                with self.connectedCondition:
                    self.listenerThread = ListenerThread(self)
                    self.listenerThread.daemon = True
                    self.listenerThread.start()
                    self.connectedCondition.wait()
                self.connectedCondition = None
                if self.unableToConnect:
                    raise Exception("Unable to connect.")
                if not self.gui:
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
            except Exception as err:
                self.printAndLogInfo("error: {0}".format(err))

    def catchSend(self, string):
        try:
            send(self, string)
        except Exception as e:
            self.printAndLogInfo("catchSend() error: {0}".format(e))
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
        if not self.gui:
            self.lockPrint("Joined channel #" + chan + ".")
        else:
            self.gui.addLine("Joined channel ", self.gui.cyanText)
            self.gui.addLine("#" + chan, self.gui.yellowText)
            self.gui.addLine(".\n")

    def parseBot(self, bot, packs, blocking = True, sleepTime = 3600 * 3, repeat = False):
        ppt = PacklistParsingThread(self, bot, packs, sleepTime = sleepTime, repeat = repeat)
        ppt.daemon = True
        ppt.start()
        if blocking:
            ppt.join()
            return
        return ppt

    def printAndLogInfo(self, string):
        """Acquires the print lock then both logs the info and prints it"""

        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            logging.info(s)
            self.printInfo(s)

    def lockPrint(self, string):
        """Acquires the print lock then prints the string"""
        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            self.printInfo(s)

    def logInfo(self, string):
        """Acquires the print lock then logs the string"""
        s = string.encode(encoding, "replace").decode(encoding, "replace")
        with printLock:
            logging.info(s)

    def printInfo(self, string):
        if not self.gui:
            print(string)
        else:
            color = 0
            if "error:" in string.lower():
                color = self.gui.redText
            self.gui.addLine(string + "\n", color)
