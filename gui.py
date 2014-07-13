import curses
from curses import wrapper
from threading import Thread

class IRCWindow(Thread):
    def __init__(self, event):
        Thread.__init__(self)
        self.event = event

    def run(self):
        wrapper(self.main)
        curses.endwin()
    
    def pad(self, string):
        return string + " " * (self.width - 1 - len(string))

    def addLine(self, string, style = 0):
        self.scroll.addstr(string, style)
        self.scrollPosMax = self.scroll.getyx()[0] - (self.height - 4)
        if self.scrollPosMax < 0:
            self.scrollPosMax = 0
        self.scrollPos = self.scrollPosMax
        self.refresh()

    def addInput(self, string, style = 0):
        self.inputLine.addstr(0, 0, self.pad(string), style)
        self.refresh()

    def main(self, stdscr):
        self.stdscr = stdscr; self.scrollPosMax = int(-1)
        self.scrollPos = int(0); self.maxScroll = 100
        self.height, self.width = stdscr.getmaxyx()

        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_BLUE, curses.COLOR_BLACK)

        self.yellowBG = curses.color_pair(1)
        self.blueBG = curses.color_pair(2)
        self.cyanText = curses.color_pair(3)
        self.greenText = curses.color_pair(4)
        self.yellowText = curses.color_pair(5)
        self.magentaText = curses.color_pair(6)
        self.redText = curses.color_pair(7)
        self.blueText = curses.color_pair(8)

        curses.mouseinterval(0)
        curses.mousemask(curses.BUTTON4_PRESSED | curses.BUTTON2_PRESSED)
        
        self.scroll = curses.newpad(self.maxScroll, self.width)
        self.scroll.scrollok(True)
        self.scroll.idlok(True)
        self.scroll.keypad(True)

        self.topLine = stdscr.subwin(1, self.width, 0, 0)
        self.infoLine = stdscr.subwin(1, self.width, self.height - 2, 0)
        self.inputLine = stdscr.subwin(1, self.width, self.height - 1, 0)
        self.event.set()
        self.getInput()

    def getInput(self):
        while True:
            self.refresh()
            key = self.inputLine.getch()
            if key == ord('q'):
                return
            elif key == curses.KEY_PPAGE:
                self.scrollPos -= (self.height - 3)//2
            elif key == curses.KEY_NPAGE:
                self.scrollPos += (self.height - 3)//2

            if self.scrollPos < 0:
                self.scrollPos = 0
            elif self.scrollPos > self.scrollPosMax:
                self.scrollPos = self.scrollPosMax

    def refresh(self):
        self.scroll.refresh(self.scrollPos, 0, 1, 0, self.height - 3, self.width)
        self.topLine.addstr(0, 0, self.pad("scrollPosMax: " + str(self.scrollPosMax)), self.blueBG)
        self.topLine.refresh()
        self.infoLine.addstr(0, 0, self.pad("scrollPos: " + str(self.scrollPos)), self.blueBG)
        self.infoLine.refresh()
        self.inputLine.refresh()

# Test Case
"""
win = IRCWindow()
win.start()

for i in range(1, 125):
    win.addLine("test" + str(i)+ "\n")
"""
