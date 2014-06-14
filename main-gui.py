#!/usr/bin/python
import irc, gui

""" irc usage example """

# git stuffs, uncomment for automatic updating
# requires command line git to be installed
# commits any changes made to the main and attempts to merge with master
"""
from subprocess import call, check_output, Popen
import sys, os, re

filename = str(os.path.abspath(__file__))
filename = re.sub(r"[^\\^/^.^:^A-Z^a-z^0-9^_^-]" , "", filename)
print("stripped filename = " + filename)

autoCommit = call("git commit -am \"Auto commit main\"", shell=True)
print("autoCommit return code : " + str(autoCommit))
try:
	gitPull = check_output("git pull origin master", shell=True)
	if not "Already up-to-date" in gitPull.decode('utf-8'):
		Popen([sys.executable, filename], shell=True)
		sys.exit(0)
except Exception as e:
	checkoutTheirs = call("git checkout --theirs .*", shell=True)
	print("checkoutTheirs return code : " + str(checkoutTheirs))
	checkoutOurMain = call("git checkout --ours main.py", shell=True)
	print("checkoutOurMain return code : " + str(checkoutOurMain))
	checkoutOurMainGUI = call("git checkout --ours main-gui.py", shell=True)
	print("checkoutOurMainGUI return code : " + str(checkoutOurMainGUI))
	Popen([sys.executable, filename], shell=True)
	sys.exit(0)
"""

# GUI stuff
# All threads must be daemons so they exit if the main exits
window = gui.IRCWindow()
window.daemon = True
window.start()

# The window parameter is an optional IRCWindow object to attach to
# otherwise runs headless
con = irc.IRCConnection("irc.rizon.net", 6667, "roughneck", window)

# Bots I use often on the rizon network
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
window.join()
