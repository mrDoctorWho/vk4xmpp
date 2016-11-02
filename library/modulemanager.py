# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

"""
Manages python modules as xmpppy handlers
"""

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"
__version__ = "1.1"

import os
from writer import *
from __main__ import Component, TransportFeatures, UserFeatures


def proxy(func):
	def wrapper(type, *args):
		if type:
			for (handler, typ, ns, makefirst) in args:
				if isinstance(ns, list):
					while ns:
						func(type, handler, typ, ns.pop(), makefirst=makefirst)
				else:
					func(type, handler, typ, ns, makefirst=makefirst)
	return wrapper


@proxy
def register(*args, **kwargs):
	Component.RegisterHandler(*args, **kwargs)


@proxy
def unregister(*args, **kwargs):
	Component.UnregisterHandler(*args)


def addFeatures(features, list=TransportFeatures):
	for feature in features:
		list.add(feature)


def removeFeatures(features, list=TransportFeatures):
	for feature in features:
		if feature in list:
			list.remove(feature)


class ModuleManager(object):

	"""
	A complete module manager.
	You can easy load, reload and unload any module using it.
	Modules are different from extensions:
	While extensions works in main globals() and have their callbacks,
	modules works in their own globals() and they're not affect to the core.
	Unfortunately, most of modules are not protected from harm
		so they may have affect on the connection
	"""

	loaded = set([])

	@staticmethod
	def getFeatures(module):
		return getattr(module, "MOD_FEATURES_USER", [])

	@classmethod
	def __register(cls, module):
		register(module.MOD_TYPE, *module.MOD_HANDLERS)
		addFeatures(module.MOD_FEATURES)
		addFeatures(cls.getFeatures(module), UserFeatures)
		cls.loaded.add(module.__name__)

	@classmethod
	def __unregister(cls, module):
		unregister(module.MOD_TYPE, *module.MOD_HANDLERS)
		removeFeatures(module.MOD_FEATURES)
		removeFeatures(cls.getFeatures(module), UserFeatures)
		cls.loaded.remove(module.__name__)

	@classmethod
	def list(cls):
		modules = []
		for file in os.listdir("modules"):
			name, ext = os.path.splitext(file)
			if ext == ".py":
				modules.append(name)
		return modules

	@classmethod
	def __load(cls, name, reload_=False):
		try:
			if reload_:
				module = sys.modules[name]
				cls.__unregister(module)
				module = reload(module)
			else:
				module = __import__(name, globals(), locals())
		except Exception:
			crashLog("modulemanager.load")
			module = None
		return module

	@classmethod
	def load(cls, list=[]):
		result = []
		errors = []
		for name in list:
			loaded = name in cls.loaded
			module = cls.__load(name, loaded)
			if not module:
				errors.append(name)
				continue

			result.append(name)
			cls.__register(module)
		return (result, errors)

	@classmethod
	def unload(cls, list=[]):
		result = []
		for name in list:
			if name in sys.modules:
				cls.__unregister(sys.modules[name])
				del sys.modules[name]
				result.append(name)
		return result
