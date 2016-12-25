# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015 — 2016.

"""
Provides a way to manage user's and transport's settings
"""

__author__ = "John Smith <mrdoctorwho@gmail.com>"

from __main__ import settingsDir, rFile, wFile
from copy import deepcopy
import os

GLOBAL_USER_SETTINGS = {"keep_online": {"label": "Keep my status online",
										"value": 1},
						"force_vk_date": {"label": "Force VK timestamp for private messages",
										"value": 0},
						"use_nicknames": {"label": "Use nicknames instead of real names",
										"value": 0}}

TRANSPORT_SETTINGS = {"send_unavailable": {"label": "Send unavailable from "
												"friends when a user logs off",
												"value": 0},
					"send_reports": {"label": "Send critical error reports",
												"value": 1}}


class Settings(object):
	"""
	This class is needed to store users settings
	"""
	def __init__(self, source, user=True):
		"""
		Uses GLOBAL_USER_SETTINGS variable as default user's settings
		and updates it using settings read from the file
		"""
		self.filename = ("%s/%s/settings.txt" % (settingsDir, source)).lower()
		if user:
			self.settings = deepcopy(GLOBAL_USER_SETTINGS)
		else:
			self.settings = TRANSPORT_SETTINGS
		userSettings = eval(rFile(self.filename)) or {}  # TODO: json
		for key, values in userSettings.iteritems():
			if key in self.settings:
				self.settings[key]["value"] = values["value"]
			else:
				self.settings[key] = values

		self.keys = self.settings.keys
		self.items = self.settings.items
		self.source = source

	save = lambda self: wFile(self.filename, str(self.settings))

	__getitem__ = lambda self, key: self.settings[key]

	def __setitem__(self, key, value):
		self.settings[key]["value"] = value
		self.save()

	def __getattr__(self, attr):
		if attr in self.settings:
			return self.settings[attr]["value"]
		elif not hasattr(self, attr):
			return False
		return object.__getattribute__(self, attr)

	def exterminate(self):
		"""
		Deletes user configuration file
		"""
		import shutil
		try:
			shutil.rmtree(os.path.dirname(self.filename))
		except (IOError, OSError):
			pass
		del shutil
