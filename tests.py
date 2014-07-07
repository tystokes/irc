#!/usr/bin/python
from irc import *
from nose.tools import *
from os import remove
from os.path import isfile
from time import sleep

def test_cs():
    assert(convertSize(0) == "0 B")
    assert(convertSize(512) == "512 B")
    assert(convertSize(1024) == "1.0 KiB")
    assert(convertSize(1024**2) == "1.0 MiB")
    assert(convertSize(1024**3) == "1.0 GiB")
    for x in range(0, 10):
        tmp = convertSize(1024**4 + 1024**4*x/10)
        assert(tmp == ("1.%i TiB" % x))
    assert_raises(ValueError, convertSize, -1)

@timed(10)
def test_packlist():
    if isfile('xdcc.txt'):
        remove('xdcc.txt')
    con = IRCConnection("didyouseeitornot.com", 6667, "test-roughneck")
    bot = "xdcc"
    series = [[r'a file that doesnt exist']]
    def kill():
        ppt.kill()
    ppt = PacklistParsingThread(con, bot, series, 30, kill)
    ppt.start()
    ppt.join()
    print('packlist')
    if isfile('xdcc.txt'):
        remove('xdcc.txt')
    else:
        raise Exception('Packlist did not download properly.')

@timed(10)
def test_parsing():
    if isfile('test.txt'):
        remove('test.txt')
    con = IRCConnection("didyouseeitornot.com", 6667, "test-roughneck2")
    bot = "xdcc"
    series = [[r'test\.txt']]
    def kill():
        ppt.kill()
    ppt = PacklistParsingThread(con, bot, series, 30, kill)
    ppt.start()
    ppt.join()
    print('parsing')
    if isfile('test.txt'):
        remove('test.txt')
    else:
        raise Exception('test.txt did not download properly.')
