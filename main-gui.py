#!/usr/bin/python
import irc
""" irc usage example """

con = irc.IRCConnection(network = "irc.rizon.net:6667", nick = "roughneck", gui = True)

""" A list of regular expressions used to parse the iroffer bot's packlist. """
packs = [r"\[Doki\] Anime A.*\[720p\]"] # Matches "[Doki] Anime A<anything here>[720p]"

""" Use an IRCConnection object to parse a bot's packlist and download packs. """
con.parseBot("Ginpachi-Sensei", packs, repeat = True, blocking = False) # parse bot for packs

con.gui.join() # Wait for gui to close before exiting
