#!/usr/bin/env python3
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.web import Application
import sys

from dccapp import app

if __name__ == "__main__":

    path = "/home/olaf/Documents/key/"
    certfile = path + "apothecary_link.crt"
    keyfile = path + "server.key"
    bundlefile = path + "bundle.crt"

    https_server = HTTPServer(WSGIContainer(app),
                              ssl_options = {"certfile": certfile,
                                             "keyfile": keyfile,
                                             "ca_certs": bundlefile})
    https_server.bind(5555)
    https_server.start(1)
    IOLoop.current().start()
