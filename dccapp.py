#!/usr/bin/python3
from bottle import route, run
from time import sleep
from threading import Event, Lock
import json
import irc
import sys

relayEvent = Event()
relayThread = None


class RelayThread(irc.DCCThread):
    """Holds data ready to be relayed to a client."""
    def run(self):
        print("Relaying:", self.filename, self.filesize)
        global relayThread
        relayThread = self
        relayEvent.set()
        relayEvent.clear()

    def json(self):
        return json.dumps({"filename": self.filename,
                           "hostname": self.host,
                           "port": self.port,
                           "filesize": self.filesize})

lock = Lock()

@route("/")
@route("/<bot>/<packNum>")
def hello(bot="Ginpachi-Sensei", packNum="0"):
    # make sure the pack is a valid integer
    try:
        tmp = int(packNum)
        if tmp > 100000 or tmp < 1:
            return json.dumps({})
    except:
        return json.dumps({})
    with lock:
        connectEvent = Event()
        with irc.IRCConnection(network="irc.rizon.net",
                               nick="relayroughneck" + packNum,
                               connectEvent=connectEvent,
                               sendHook=RelayThread) as con:
            connectEvent.wait()
            sleep(1)
            global relayThread
            relayThread = None
            con.msg(bot, "XDCC SEND #%s" % packNum)
            relayEvent.wait(10)
            if relayThread is not None:
                return relayThread.json()
        sleep(3)
    return json.dumps({})

if __name__ == "__main__":
    try:
        run(host=sys.argv[1], port=5555)
    except:
        print("usage: ./dccapp.py <host_addr>")
