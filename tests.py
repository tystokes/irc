from irc import convertSize
from nose.tools import *

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
