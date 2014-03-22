#!/usr/bin/python
import irc

""" irc usage example """

# IRCConnection(network, port, nick)
con = irc.IRCConnection("irc.rizon.net", 6667, "roughneck")

# Bots I use often on the rizon network
bots = ["Ginpachi-Sensei", "A|FanserviceBot"]

# Fill in keywords to search for regarding each series
# now matches as if it's a regular expression
# so be sure to include '\' in front of things like '[',']','(',')', etc...
series = [
	["\[Doki\] Anime A[^^]*\[720p\]"], # All episodes of Anime A by Doki in 720p
	["Anime X","\[Doki\]","01"], # Anime X episode 01 by Doki
	["Anime Y","\[HorribleSubs\]"]] # All episodes of Anime Y by HorribleSubs

# fanService bot requires that you join #nibl
# this call blocks until the channel is joined
con.join("nibl")

# ParseThread will parse the bot's packlist every 3 hours looking for packs that fit the keyword set
# you may parse multiple bots at once searching for the same or different files
for bot in bots:
	irc.PacklistParsingThread(con, bot, series).start()
