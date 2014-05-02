import curses, sys, math, re
from curses import wrapper
from threading import Thread

class IRCWindow(Thread):
	def __init__(self):
		Thread.__init__(self)
		#wrapper(self.main)

	def run(self):
		wrapper(self.main)
		curses.endwin()
	
	def pad(self, string):
		return string + " " * ( self.width - 1 - len(string) )

	def addLine(self, string, style = 0):
		self.scroll.addstr(string, style)
		self.scrollPosMax = self.scroll.getyx()[0] - 1
		if (self.scrollPosMax - (self.height - 3) > 0):
			self.scrollPos = self.scrollPosMax
		else:
			self.scrollPos = 0
		self.refresh()

	def main(self, stdscr):
		self.stdscr = stdscr; self.scrollPosMax = int(-1)
		self.scrollPos = int(0); self.maxScroll = 30
		self.height, self.width = stdscr.getmaxyx()

		curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
		curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
		curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
		curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)

		self.yellowBG = curses.color_pair(1)
		self.blueBG = curses.color_pair(2)
		self.cyanText = curses.color_pair(3)
		self.greenText = curses.color_pair(4)

		curses.mouseinterval(0)
		curses.mousemask(curses.BUTTON4_PRESSED | curses.BUTTON2_PRESSED)
		
		self.scroll = curses.newpad(self.maxScroll, self.width)
		self.scroll.scrollok(True)
		self.scroll.idlok(True)
		self.scroll.keypad(True)

		"""
		for i in range(1, 20):
			self.addLine("test" + str(i)+ "\n")
		"""

		self.topLine = stdscr.subwin(1, self.width, 0, 0)
		self.infoLine = stdscr.subwin(1, self.width, self.height - 2, 0)
		self.inputLine = stdscr.subwin(1, self.width, self.height - 1, 0)
		self.getInput()

	def getInput(self):
		while True:
			self.scroll.refresh(self.scrollPos, 0, 1, 0, self.height - 3, self.width)
			self.topLine.addstr(0, 0, self.pad(str(self.scrollPosMax)), self.blueBG)
			self.topLine.refresh()
			self.infoLine.addstr(0, 0, self.pad(str(self.scrollPos)), self.blueBG)
			self.infoLine.refresh()
			self.inputLine.refresh()
			key = self.inputLine.getch()
			if key == ord('q'):
				return
			elif key == curses.KEY_PPAGE:
				if (self.scrollPos > 0):
					self.scrollPos += -1
			elif key == curses.KEY_NPAGE:
				if (self.scrollPosMax != self.scrollPos and self.scrollPos < self.scrollPosMax ):
					self.scrollPos += 1
	def refresh(self):
		self.scroll.refresh(self.scrollPos, 0, 1, 0, self.height - 3, self.width)
		self.topLine.addstr(0, 0, self.pad(str(self.scrollPosMax)), self.blueBG)
		self.topLine.refresh()
		self.infoLine.addstr(0, 0, self.pad(str(self.scrollPos)), self.blueBG)
		self.infoLine.refresh()
		self.inputLine.refresh()
#IRCWindow().start()