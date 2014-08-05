#!/usr/bin/python
import irc
""" irc usage example """

con = irc.IRCConnection(network = "irc.rizon.net:6667", nick = "roughneck")

bot = "Ginpachi-Sensei" # iroffer bot with packlist

""" A list of regular expressions used to parse the iroffer bot's packlist """
packs = [r"\[Doki\] Anime A.*\[720p\]"] # Matches "[Doki] Anime A<anything here>[720p]"

""" Use an IRCConnection object to parse a bot's packlist and download packs. """
ppt = irc.PacklistParsingThread(con, bot, packs)
ppt.start()

ppt.join() # Wait for gui thread to return before exiting
