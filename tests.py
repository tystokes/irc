#!/usr/bin/python
from irc import *
from nose.tools import *
from os import remove
from os.path import isfile
from time import sleep
from random import randint

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

@timed(15)
def test_connect_strings():
    for connect_string in ["truly.red", "truly.red:6667"]:
        con = IRCConnection(connect_string,
                            "testroughneck" + str(randint(1000, 9999)))
        sleep(3)
        con.disconnect()

@timed(45)
def test_packlist():
    if isfile('xdcc.txt'):
        remove('xdcc.txt')
    con = IRCConnection("truly.red", "testroughneck"+ str(randint(1000, 9999)))
    con.parseBot("xdcc", [r'a file that doesnt exist'])
    if isfile('xdcc.txt'):
        remove('xdcc.txt')
    else:
        raise Exception('Packlist did not download properly.')
    con.disconnect()

@timed(45)
def test_parsing():
    if isfile('test.txt'):
        remove('test.txt')
    con = IRCConnection("truly.red", "testroughneck"+ str(randint(1000, 9999)))
    con.parseBot("xdcc", [r'test\.txt'])
    if isfile('test.txt'):
        remove('test.txt')
    else:
        raise Exception('test.txt did not download properly.')
    con.disconnect()
