#!/usr/bin/python
import irc
""" irc usage example """

# IRCConnection(network, port, nick, gui)
con = irc.IRCConnection("irc.rizon.net", 6667, "roughneck", gui = True)

# Add bots that offer packlists here:
bots = ["Ginpachi-Sensei"]

# Fill in keywords to search for regarding each series
# now matches as if it's a regular expression
# so be sure to include '\' in front of things like '[',']','(',')', etc...
series = [[r"\[Doki\] Anime A.*\[720p\]"]] # All episodes of Anime A by Doki in 720p

# ParseThread will parse the bot's packlist every 3 hours looking for packs that fit the keyword set
# you may parse multiple bots at once searching for the same or different files
for bot in bots:
    ppt = irc.PacklistParsingThread(con, bot, series)
    ppt.daemon = True
    ppt.start()

# Program exits if IRCWindow thread returns
con.gui.join()
