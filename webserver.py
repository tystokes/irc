#!/usr/bin/env python3
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.web import Application
import sys

from dccapp import app

if __name__ == "__main__":
    http_server = HTTPServer(WSGIContainer(app))
    http_server.bind(5555)
    http_server.start(1)
    IOLoop.current().start()
