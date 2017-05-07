# coding: utf-8
# © simpleApps, 2010

"""
Provides a “safe” way to print a text
"""

import os
import sys
import time

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"

# Bold + Inensity
BIYellow = "\x1b[1;93m" # Yellow
BICyan = "\x1b[1;96m"  # Cyan
BIRed = "\x1b[1;91m"  # Red
BIGreen = "\x1b[1;92m"  # Green

Nocolor = "\x1b[0m"


def use_lsd(text):
	import random
	line = ""
	for char in text:
		style = random.choice((0, 1, 4, 5))
		background = random.randrange(41, 48)
		style = "%s;30;%s" % (style, background)
		line += "\x1b[%sm%s \x1b[0m" % (style, char)
	return line


def Print(text, line=True):
	"""
	This function is needed to prevent errors
	like IOError: device is not ready
	which is probably happens when script running under screen
	"""
	if (time.gmtime().tm_mon, time.gmtime().tm_mday) == (4, 1):
		text = use_lsd(text)
	if line:
		text += "\n"
	try:
		sys.stdout.write(text)
		sys.stdout.flush()
	except (IOError, OSError):
		pass


def colorizeJSON(data):
	if os.name != "nt":
		text = ""
		iter = list(repr(data)).__iter__()
		for c in iter:
			if c == "'":
				text += BIYellow + c
				for x in iter:
					text += x
					if x == "'":
						text += Nocolor
						break
			elif c.isdigit():
				text += BICyan + c
				for x in iter:
					if x.isdigit():
						text += x
					else:
						text += Nocolor + x
						break
			else:
				text += c
		return text
	return data
