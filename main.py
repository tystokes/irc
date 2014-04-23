#!/usr/bin/python
import irc

""" irc usage example """

# git stuffs, uncomment for automatic updating
# requires command line git to be installed
# commits any changes made to the main and attempts to merge with master
"""
import subprocess
from subprocess import call
from subprocess import check_output
from subprocess import Popen
import sys, os

filename = str(os.path.abspath(__file__))

autoCommit = call("git commit -am \"Auto commit main\"", shell=True)
print("autoCommit return code : " + str(autoCommit))
try:
	gitPull = check_output("git pull origin master", shell=True)
	if not "Already up-to-date" in gitPull.decode('utf-8'):
		Popen([sys.executable, filename])
		sys.exit(0)
except Exception as e:
	checkoutTheirs = call("git checkout --theirs .*", shell=True)
	print("checkoutTheirs return code : " + str(checkoutTheirs))
	checkoutOurMain = call("git checkout --ours main.py", shell=True)
	print("checkoutOurMain return code : " + str(checkoutOurMain))
	Popen([sys.executable, filename])
	sys.exit(0)
"""

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
