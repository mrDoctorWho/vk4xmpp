# coding: utf-8
# © simpleApps, 2010

"""
This module used to read, write files and crash logs
"""

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"

import __main__
import logging
import os
import sys
import time
import traceback

from printer import *

logger = logging.getLogger("vk4xmpp")

fixme = lambda msg: Print("\n#! [%s] fixme: \"%s\"." % (time.strftime("%H:%M:%S"), msg))

lastErrorBody = None

def wFile(filename, data, mode = "w"):
	"""
	Creates file and writes data into it.
	Makes directory if needed
	"""
	if "/" in filename:
		dir = os.path.dirname(filename)
		if not os.path.exists(dir):
			os.makedirs(dir)
	with open(filename, mode, 0) as file:
		file.write(data)


def rFile(filename):
	"""
	Reads a file and returns the data
	"""
	if not os.path.exists(filename):
		return "{}"
	with open(filename, "r") as file:
		return file.read()


def crashLog(name, fixme_=True):
	"""
	Writes crashlog, ignoring duplicates
	Args:
		name is a crashlog name
		fixme_ whether to print the "fixme" message
	Returns:
		the current traceback
	"""
	global lastErrorBody
	trace = ""
	logger.error("crashlog %s has been written" % name)
	if fixme_:
		fixme(name)
	try:
		file = "%s/%s.txt" % (__main__.crashDir, name)
		if not os.path.exists(__main__.crashDir):
			os.makedirs(__main__.crashDir)
		trace = traceback.format_exc()
		if trace and trace != lastErrorBody:
			timestamp = time.strftime("| %d.%m.%Y (%H:%M:%S) |\n")
			wFile(file, timestamp + trace + "\n", "a")
		lastErrorBody = trace
	except Exception:
		fixme("crashlog")
		Print(trace)
	return trace


def returnExc():
	exc = sys.exc_info()
	if all(exc):
		error = "\n%s: %s " % (exc[0].__name__, exc[1])
	else:
		error = "None"
	return error
