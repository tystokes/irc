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
        print("Relaying:", self.filename, self.filesize)
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
        tmp = int(packNum)
        if tmp > 100000 or tmp < 1:
            return json.dumps({})
    except:
        return json.dumps({})
    with lock:
        connectEvent = Event()
        global count
        con = irc.IRCConnection(network="irc.rizon.net",
                                nick="relayroughneck" + str(count),
                                connectEvent=connectEvent,
                                sendHook=RelayThread)
        connectEvent.wait()
        # bot = "xdcc"
        bot = "Ginpachi-Sensei"
        global relayThread
        relayThread = None
        con.msg(bot, "XDCC SEND #%s" % packNum)
        relayEvent.wait(10)
        con.disconnect()
        count += 1
        print('done')
        if relayThread:
            return json.dumps({"filename": relayThread.filename,
                               "hostname": relayThread.host,
                               "port": relayThread.port,
                               "filesize": relayThread.filesize})
    return json.dumps({})
