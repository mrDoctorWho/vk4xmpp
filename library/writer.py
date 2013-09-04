# /* encoding: utf-8 */
# © simpleApps, 2010

import sys, traceback

def Print(text, line = True):
	try:
		if line:
			print text
		else:
			sys.stdout.write(text)
			sys.stdout.flush()
	except:
		pass

fixme = lambda msg: Print("\n#! fixme: \"%s\"." % msg)

def wException(limit = None, file = None):
	try:
		traceback.print_exc(limit, file) # May cause IOError/OSError and maybe something more
	except:
		pass