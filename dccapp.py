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
@app.route("/<string:packNum>")
def hello(packNum="1"):
    # make sure the pack is a valid integer
    try:
        int(packNum)
    except:
        return json.dumps({})
    with lock:
        print("output")
        connectEvent = Event()
        global count
        con = irc.IRCConnection(network="irc.rizon.net",
                                nick="roughneck" + str(count),
                                connectEvent=connectEvent,
                                sendHook=RelayThread)
        connectEvent.wait()
        # bot = "xdcc"
        bot = "Ginpachi-Sensei"
        global relayThread
        relayThread = None
        con.msg(bot, "XDCC SEND #%s" % packNum)
        # con.msg(bot, "XDCC SEND #1")
        relayEvent.wait(10)
        print(relayThread)
        con.disconnect()
        count += 1
        if relayThread:
            return json.dumps({"filename": relayThread.filename,
                               "hostname": relayThread.host,
                               "port": relayThread.port,
                               "filesize": relayThread.filesize})
    return json.dumps({})
