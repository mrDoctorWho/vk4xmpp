# coding: utf-8
# © simpleApps, 2010

import __main__
import os, sys, time, logging, traceback

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
	Reads file and returns data
	"""
	if not os.path.exists(filename):
		return "{}"
	with open(filename, "r") as file:
		return file.read()


def crashLog(name, fixme_ = True):
	"""
	Writes crashlog, ignoring duplicates
	Parameters:
		name is a crashlog name
		fixme_ needeed to know if print the "fixme" message or not
	"""
	global lastErrorBody
	logger.error("crashlog %s has been written" % name)
	if fixme_:
		fixme(name)
	try:
		file = "%s/%s.txt" % (__main__.crashDir, name)
		if not os.path.exists(__main__.crashDir):
			os.makedirs(__main__.crashDir)
		exception = wException(True)
		if exception not in ("None", lastErrorBody):
			timestamp = time.strftime("| %d.%m.%Y (%H:%M:%S) |\n")
			wFile(file, timestamp + exception + "\n", "a")
		lastErrorBody = exception
	except Exception:
		fixme("crashlog")
		wException()


def Print(text, line = True):
	"""
	This function is needed to prevent errors
	like IOError: device is not ready 
	which is probably happens when script running under screen
	"""
	if line:
		text += "\n"
	try:
		sys.stdout.write(text)
		sys.stdout.flush()
	except (IOError, OSError):
		pass


def wException(file = False):
	exception = traceback.format_exc().strip()
	if not file:
		Print(exception)
	return exception


def returnExc():
	exc = sys.exc_info()
	if all(exc):
		error = "\n%s: %s " % (exc[0].__name__, exc[1])
	else:
		error = "None"
	return error
