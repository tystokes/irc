# irc

Lightweight irc client for xdcc (and maybe more!)

## running the code

Open main.py or main-gui.py for example usages.

## user interface

In order to use the text-based user interface the curses module must be installed.
UNIX-based python versions should have this by default.
Windows users can download curses [here](http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses).
Make sure to download for the correct python version and system architecture.

## auto-updating

- Get command line git.

- In terminal change to desired download directory.

- Run these commands:

```bash
git init .
git remote add origin https://github.com/tystokes/irc.git
git pull origin master
```

- Now edit your main.py removing the commented git auto-update block.

- Edit the main to your liking.

- Your code should now auto update with every run of main.py.
