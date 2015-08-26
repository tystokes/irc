from flask import Flask
from time import sleep
from threading import Event, Lock
import json
import irc

count = 0
app = Flask(__name__)

relayEvent = Event()
relayThread = None

class RelayThread(irc.DCCThread):
    def run(self):
        print(self.filename, self.filesize)
        global relayThread
        relayThread = self
        relayEvent.set()
        relayEvent.clear()

lock = Lock()

@app.route("/")
def hello():
    with lock:
        print("output")
        connectEvent = Event()
        global count
        con = irc.IRCConnection(network="irc.rizon.net",
                                nick="roughneck" + str(count),
                                connectEvent=connectEvent,
                                sendHook=RelayThread)
        connectEvent.wait()
        bot = "Ginpachi-Sensei"
        con.msg(bot, "XDCC SEND #175")
        # bot = "xdcc"
        # con.msg(bot, "XDCC SEND #1")
        relayEvent.wait()
        print(relayThread)
        con.disconnect()
        count += 1
        return json.dumps({"filename": relayThread.filename,
                           "hostname": relayThread.host,
                           "port": relayThread.port,
                           "filesize": relayThread.filesize})
