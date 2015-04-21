# coding: utf-8
# (с) simpleApps, 25.06.12; 19:58:42

"""
Provides a way to use translations
Not optimal, but still.
"""

import os
from writer import rFile

def setVars(lang, path):
	globals()["locale"] = lang
	globals()["path"] = path


def _(what):
	if what:
		name = "%s/locales/locale.%s" % (path, locale)
		what = what.replace("\n", "\\n")
		if locale != "en" and os.path.exists(name):
			data = open(name).readlines()
			for line in data:
				if line.startswith(what):
					what = line.split("=")[1].strip()
					break
		return what.replace("\\n", "\n")
		
