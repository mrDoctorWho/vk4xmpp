# coding: utf-8
# © simpleApps, 2010

"""
Sometimes your program can crash with an error "IOError: device not ready" when it prints some text
This module is used to prevent such things
"""

import sys
import time

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
