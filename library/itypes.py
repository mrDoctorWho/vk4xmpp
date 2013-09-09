"""
Module "itypes"
itypes.py

Copyright (2010-2013) Al Korgun (alkorgun@gmail.com)

Distributed under the GNU GPLv3.
"""

try:
	import sqlite3
except ImportError:
	sqlite3 = None

	def connect(*args, **kwargs):
		raise RuntimeError("py-sqlite3 is not installed")

else:
	connect = sqlite3.connect

__all__ = [
	"Number",
	"Database"
				]

__version__ = "0.8"

class Number(object):

	def __init__(self, number = int()):
		self.number = number

	def plus(self, number = 0x1):
		self.number += number
		return self.number

	def reduce(self, number = 0x1):
		self.number -= number
		return self.number

	__int__ = lambda self: self.number.__int__()

	_int = lambda self: self.__int__()

	__str__ = __repr__ = lambda self: self.number.__repr__()

	_str = lambda self: self.__str__()

	__float__ = lambda self: self.number.__float__()

	__oct__ = lambda self: self.number.__oct__()

	__eq__ = lambda self: self.number.__eq__()

	__ne__ = lambda self: self.number.__ne__()

	__gt__ = lambda self: self.number.__gt__()

	__lt__ = lambda self: self.number.__lt__()

	__ge__ = lambda self: self.number.__ge__()

	__le__ = lambda self: self.number.__le__()

class LazyDescriptor(object): # not really lazy, but setter is not needed

	def __init__(self, function):
		self.fget = function

	__get__ = lambda self, instance, owner: self.fget(instance)

class Database(object):

	__connected = False

	def __init__(self, filename, lock = None, timeout = 8):
		self.filename = filename
		self.lock = lock
		self.timeout = timeout

	def __connect(self):

		assert not self.__connected, "already connected"

		self.db = connect(self.filename, timeout = self.timeout)
		self.cursor = self.db.cursor()
		self.__connected = True
		self.commit = self.db.commit
		self.execute = self.cursor.execute
		self.fetchone = self.cursor.fetchone
		self.fetchall = self.cursor.fetchall
		self.fetchmany = self.cursor.fetchmany

	@LazyDescriptor
	def execute(self):
		self.__connect()
		return self.execute

	__call__ = lambda self, *args: self.execute(*args)

	@LazyDescriptor
	def db(self):
		self.__connect()
		return self.db

	@LazyDescriptor
	def cursor(self):
		self.__connect()
		return self.cursor

	def close(self):

		assert self.__connected, "not connected"

		if self.cursor:
			self.cursor.close()
		if self.db.total_changes:
			self.commit()
		if self.db:
			self.db.close()

	def __enter__(self):
		if self.lock:
			self.lock.acquire()
		return self

	def __exit__(self, *args):
		if self.lock:
			self.lock.release()
		if self.__connected:
			self.close()

del LazyDescriptor
