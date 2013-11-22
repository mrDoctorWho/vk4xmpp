# /* coding: utf-8 */
# © simpleApps, 2010

import os, sys, time, logging, traceback

logger = logging.getLogger("vk4xmpp")

fixme = lambda msg: Print("\n#! fixme: \"%s\"." % msg)

lastErrorBody = None

def wFile(filename, data, mode = "w"):
	with open(filename, mode, 0) as file:
		file.write(data)

def rFile(filename):
	with open(filename, "r") as file:
		return file.read()

def crashLog(name, text = 0, fixMe = True):
	global lastErrorBody
	logger.error("writing crashlog %s" % name)
	if fixMe:
		fixme(name)
	try:
		File = "crash/%s.txt" % name
		if not os.path.exists("crash"): 
			os.makedirs("crash")
		exception = wException(True)
		if exception not in ("None", lastErrorBody):
			Timestamp = time.strftime("| %d.%m.%Y (%H:%M:%S) |\n")
			wFile(File, Timestamp + exception + "\n", "a")
		lastErrorBody = exception
	except:
		fixme("crashlog")
		wException()

def Print(text, line = True):
	try:
		if line:
			print text
		else:
			sys.stdout.write(text)
			sys.stdout.flush()
	except (IOError, OSError):
		pass

def wException(File = False):
	try:
		exception = traceback.format_exc().strip()
		if not File:
			Print(exception)
		return exception
	except (IOError, OSError):
		pass

def returnExc():
	exc = sys.exc_info()
	if any(exc):
		error = "\n%s: %s " % (exc[0].__name__, exc[1])
	else:
		error = `None`
	return error