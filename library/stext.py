# coding: utf-8
# (с) simpleApps, 25.06.12; 19:58:42
# License: GPLv3.

import os

def setVars(lang, path):
	globals()["locale"] = lang
	globals()["path"] = path

def rFile(name):
	with open(name, "r") as file:
		return file.read()

def _(what):
	name = "%s/locales/locale.%s" % (path, locale)
	what = what.replace("\n", "\L")
	if locale == "en" or not os.path.exists(name):
		return what
	data = rFile(name)
	for line in data.splitlines():
		if line.startswith(what):
			return line.split("=")[1].replace("\\L", "\n")
	return what