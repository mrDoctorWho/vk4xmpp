##   debug.py
##
##   Copyright (C) 2003 Jacob Lundqvist
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU Lesser General Public License as published
##   by the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU Lesser General Public License for more details.

# $Id: debug.py, v1.41 2013/10/21 alkorgun Exp $

_version_ = "1.4.1"

import os
import sys
import time

from traceback import format_exception as traceback_format_exception

colors_enabled = os.environ.has_key("TERM")

color_none = chr(27) + "[0m"
color_black = chr(27) + "[30m"
color_red = chr(27) + "[31m"
color_green = chr(27) + "[32m"
color_brown = chr(27) + "[33m"
color_blue = chr(27) + "[34m"
color_magenta = chr(27) + "[35m"
color_cyan = chr(27) + "[36m"
color_light_gray = chr(27) + "[37m"
color_dark_gray = chr(27) + "[30;1m"
color_bright_red = chr(27) + "[31;1m"
color_bright_green = chr(27) + "[32;1m"
color_yellow = chr(27) + "[33;1m"
color_bright_blue = chr(27) + "[34;1m"
color_purple = chr(27) + "[35;1m"
color_bright_cyan = chr(27) + "[36;1m"
color_white = chr(27) + "[37;1m"

class NoDebug:

	def __init__(self, *args, **kwargs):
		self.debug_flags = []

	def show(self, *args, **kwargs):
		pass

	def Show(self, *args, **kwargs):
		pass

	def is_active(self, flag):
		pass

	colors = {}

	def active_set(self, active_flags=None):
		return 0

LINE_FEED = "\n"

class Debug:

	def __init__(self, active_flags=None, log_file=sys.stderr, prefix="DEBUG: ", sufix="\n", time_stamp=0, flag_show=None, validate_flags=False, welcome=-1):
		self.debug_flags = []
		if welcome == -1:
			if active_flags and len(active_flags):
				welcome = 1
			else:
				welcome = 0
		self._remove_dupe_flags()
		if log_file:
			if isinstance(log_file, str):
				try:
					self._fh = open(log_file, "w")
				except Exception:
					print("ERROR: can open %s for writing." % log_file)
					sys.exit(0)
			else: # assume its a stream type object
				self._fh = log_file
		else:
			self._fh = sys.stdout
		if time_stamp not in (0, 1, 2):
			raise Exception("Invalid time_stamp param", str(time_stamp))
		self.prefix = prefix
		self.sufix = sufix
		self.time_stamp = time_stamp
		self.flag_show = None # must be initialised after possible welcome
		self.validate_flags = validate_flags
		self.active_set(active_flags)
		if welcome:
			self.show("")
			caller = sys._getframe(1) # used to get name of caller
			try:
				mod_name = ":%s" % caller.f_locals["__name__"]
			except Exception:
				mod_name = ""
			self.show("Debug created for %s%s" % (caller.f_code.co_filename, mod_name))
			self.show(" flags defined: %s" % ",".join(self.active))
		if isinstance(flag_show, (str, type(None))):
			self.flag_show = flag_show
		else:
			raise Exception("Invalid type for flag_show!", str(flag_show))

	def show(self, msg, flag=None, prefix=None, sufix=None, lf=0):
		"""
		flag can be of folowing types:
			None - this msg will always be shown if any debugging is on
			flag - will be shown if flag is active
			(flag1,flag2,,,) - will be shown if any of the given flags are active

		if prefix / sufix are not given, default ones from init will be used

		lf = -1 means strip linefeed if pressent
		lf = 1 means add linefeed if not pressent
		"""
		if self.validate_flags:
			self._validate_flag(flag)
		if not self.is_active(flag):
			return None
		if prefix:
			pre = prefix
		else:
			pre = self.prefix
		if sufix:
			suf = sufix
		else:
			suf = self.sufix
		if self.time_stamp == 2:
			output = "%s%s " % (
				pre,
				trftime("%b %d %H:%M:%S",
				caltime(time.time()))
			)
		elif self.time_stamp == 1:
			output = "%s %s" % (
				time.strftime("%b %d %H:%M:%S",
				time.localtime(time.time())),
				pre
			)
		else:
			output = pre
		if self.flag_show:
			if flag:
				output = "%s%s%s" % (output, flag, self.flag_show)
			else:
				# this call uses the global default, dont print "None", just show the separator
				output = "%s %s" % (output, self.flag_show)
		output = "%s%s%s" % (output, msg, suf)
		if lf:
			# strip/add lf if needed
			last_char = output[-1]
			if lf == 1 and last_char != LINE_FEED:
				output = output + LINE_FEED
			elif lf == -1 and last_char == LINE_FEED:
				output = output[:-1]
		try:
			self._fh.write(output)
		except Exception:
			# unicode strikes again ;)
			s = unicode()
			for i in xrange(len(output)):
				if ord(output[i]) < 128:
					c = output[i]
				else:
					c = "?"
				s += c
			self._fh.write("%s%s%s" % (pre, s, suf))
		self._fh.flush()

	def is_active(self, flag):
		"""
		If given flag(s) should generate output.
		"""
		# try to abort early to quicken code
		if not self.active:
			return 0
		if not flag or flag in self.active:
			return 1
		else:
			# check for multi flag type:
			if isinstance(flag, (list, tuple)):
				for s in flag:
					if s in self.active:
						return 1
		return 0

	def active_set(self, active_flags=None):
		"""
		Returns 1 if any flags where actually set, otherwise 0.
		"""
		r = 0
		ok_flags = []
		if not active_flags:
			# no debuging at all
			self.active = []
		elif isinstance(active_flags, (tuple, list)):
			flags = self._as_one_list(active_flags)
			for t in flags:
				if t not in self.debug_flags:
					sys.stderr.write("Invalid debugflag given: %s\n" % t)
				ok_flags.append(t)

			self.active = ok_flags
			r = 1
		else:
			# assume comma string
			try:
				flags = active_flags.split(",")
			except Exception:
				self.show("***")
				self.show("*** Invalid debug param given: %s" % active_flags)
				self.show("*** please correct your param!")
				self.show("*** due to this, full debuging is enabled")
				self.active = self.debug_flags
			for f in flags:
				s = f.strip()
				ok_flags.append(s)
			self.active = ok_flags
		self._remove_dupe_flags()
		return r

	def active_get(self):
		"""
		Returns currently active flags.
		"""
		return self.active

	def _as_one_list(self, items):
		"""
		Init param might contain nested lists, typically from group flags.
		This code organises lst and remves dupes.
		"""
		if not isinstance(items, (list, tuple)):
			return [items]
		r = []
		for l in items:
			if isinstance(l, list):
				lst2 = self._as_one_list(l)
				for l2 in lst2:
					self._append_unique_str(r, l2)
			elif l == None:
				continue
			else:
				self._append_unique_str(r, l)
		return r

	def _append_unique_str(self, lst, item):
		"""
		Filter out any dupes.
		"""
		if not isinstance(item, str):
			raise Exception("Invalid item type (should be string)", str(item))
		if item not in lst:
			lst.append(item)
		return lst

	def _validate_flag(self, flags):
		"""
		Verify that flag is defined.
		"""
		if flags:
			for flag in self._as_one_list(flags):
				if not flag in self.debug_flags:
					raise Exception("Invalid debugflag given", str(flag))

	def _remove_dupe_flags(self):
		"""
		If multiple instances of Debug is used in same app,
		some flags might be created multiple time, filter out dupes.
		"""
		unique_flags = []
		for f in self.debug_flags:
			if f not in unique_flags:
				unique_flags.append(f)
		self.debug_flags = unique_flags

	colors = {}

	def Show(self, flag, msg, prefix=""):
		msg = msg.replace("\r", "\\r").replace("\n", "\\n").replace("><", ">\n  <")
		if not colors_enabled:
			pass
		elif self.colors.has_key(prefix):
			msg = self.colors[prefix] + msg + color_none
		else:
			msg = color_none + msg
		if not colors_enabled:
			prefixcolor = ""
		elif self.colors.has_key(flag):
			prefixcolor = self.colors[flag]
		else:
			prefixcolor = color_none
		if prefix == "error":
			e = sys.exc_info()
			if e[0]:
				msg = msg + "\n" + "".join(traceback_format_exception(e[0], e[1], e[2])).rstrip()
		prefix = self.prefix + prefixcolor + (flag + " " * 12)[:12] + " " + (prefix + " " * 6)[:6]
		self.show(msg, flag, prefix)

	def is_active(self, flag):
		if not self.active:
			return 0
		if not flag or flag in self.active and DBG_ALWAYS not in self.active or flag not in self.active and DBG_ALWAYS in self.active:
			return 1
		return 0

DBG_ALWAYS = "always"

# Debug=NoDebug # Uncomment this to effectively disable all debugging and all debugging overhead.
