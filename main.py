#!/usr/bin/python
import irc
""" irc usage example """

con = irc.IRCConnection(network = "irc.rizon.net:6667", nick = "roughneck")

""" A list of regular expressions used to parse the iroffer bot's packlist. """
packs = irc.parse("packs.txt")

""" Use an IRCConnection object to parse a bot's packlist and download packs. """
con.parseBot("Ginpachi-Sensei", packs)
