#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v2.65
# © simpleApps, 2013 — 2015.
# Program published under the MIT license.

import gc
import httplib
import logging
import os
import re
import select
import signal
import socket
import sqlite3
import sys
import threading
import time
from argparse import ArgumentParser
from copy import deepcopy

core = getattr(sys.modules["__main__"], "__file__", None)
root = "."
if core:
	core = os.path.abspath(core)
	root = os.path.dirname(core)
	if root:
		os.chdir(root)

sys.path.insert(0, "library")
sys.path.insert(1, "modules")
reload(sys).setdefaultencoding("utf-8")

## Now we can import our own modules
import utils
import vkapi as api
import xmpp
from itypes import Database
from stext import *
from stext import _
from webtools import *

Transport = {}
jidToID = {}

WatcherList = []
WhiteList = []
ADMIN_JIDS = []

# The features transport will advertise
TransportFeatures = set([xmpp.NS_DELAY])

# The features transport's users will advertise
UserFeatures = set([xmpp.NS_CHATSTATES,
					xmpp.NS_LAST])

IDENTIFIER = {"type": "vk",
			"category": "gateway",
			"name": "VK4XMPP Transport"}

Semaphore = threading.Semaphore()

ALIVE = True

# config vairables
DEBUG_XMPPPY = False
DEBUG_POLL = False
DEBUG_API = False
LOG_LEVEL = logging.DEBUG
MAXIMUM_FORWARD_DEPTH = 10 ## We need to go deeper.
STANZA_SEND_INTERVAL = 0.03125
THREAD_STACK_SIZE = 0
USER_LIMIT = 0
VK_ACCESS = 69638

# used files
pidFile = "pidFile.txt"
logFile = "vk4xmpp.log"
crashDir = "crash"
settingsDir = "settings"

# cmd args
argParser = ArgumentParser()
argParser.add_argument("-c", "--config", help="set the general config file destination", default="Config.txt")
argParser.add_argument("-d", "--daemon", help="run in daemon mode (no auto-restart)", action="store_true")
args = argParser.parse_args()
Daemon = args.daemon
Config = args.config

# logger
logger = logging.getLogger("vk4xmpp")
logger.setLevel(LOG_LEVEL)
loggerHandler = logging.FileHandler(logFile)
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s %(message)s", "[%d.%m.%Y %H:%M:%S]")
loggerHandler.setFormatter(formatter)
logger.addHandler(loggerHandler)

# now writer can be imported
from writer import *

# config variables
PhotoSize = "photo_100"
DefLang = "ru"
evalJID = ""
AdditionalAbout = ""
ConferenceServer = ""
URL_ACCEPT_APP = "http://jabberon.ru/vk4xmpp.html#%d"
allowBePublic = True

startTime = int(time.time())

try:
	execfile(Config)
	Print("#-# Config loaded successfully.")
except Exception:
	Print("#! Error loading config file:")
	wException()
	exit()

# Compatibility with old config files
if not ADMIN_JIDS:
	ADMIN_JIDS = [evalJID]

## Trying to use faster library usjon instead of simplejson
try:
	import ujson as json
except ImportError:
	import json

# Setting variables: DefLang for language id, root for the translations directory
setVars(DefLang, root)

# Settings
GLOBAL_USER_SETTINGS = {"keep_online": {"label": "Keep my status online", "value": 1},
						"i_am_ghost": {"label": "I am a ghost", "value": 0},
						"force_vk_date": {"label": "Force VK timestamp for messages", "value": 0}}

TRANSPORT_SETTINGS = {"send_unavailable": {"label": "Send unavailable from "\
												"friends when user log off", "value": 0}}


if THREAD_STACK_SIZE:
	threading.stack_size(THREAD_STACK_SIZE)
del formatter, loggerHandler

OS = "{0} {2:.16} [{4}]".format(*os.uname())
Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)

# See extensions/.example.py for more information about handlers
Handlers = {"msg01": [], "msg02": [],
			"msg03": [], "evt01": [],
			"evt02": [], "evt03": [],
			"evt04": [], "evt05": [],
			"evt06": [], "evt07": [],
			"prs01": [], "prs02": [],
			"evt08": [], "evt09": []}

Stats = {"msgin": 0, ## from vk
		 "msgout": 0, ## to vk
		 "method": 0}

DESC = "© simpleApps, 2013 — 2015."


def runDatabaseQuery(query, args=(), set=False, many=True, semph=Semaphore):
	"""
	Executes sql to the database
	"""
	with Database(DatabaseFile, semph) as db:
		db(query, args)
		if set:
			db.commit()
			result = None
		elif many:
			result = db.fetchall()
		else:
			result = db.fetchone()
	return result


def initDatabase(filename):
	"""
	Initializes database if it doesn't exist
	"""
	if not os.path.exists(filename):
		runDatabaseQuery("create table users \
			(jid text, username text, token text, \
			lastMsgID integer, rosterSet bool)", set=True, semph=None)
	return True


def execute(handler, list=()):
	"""
	Just executes handler(*list) safely
	If weird error is happened writes a crashlog
	"""
	try:
		result = handler(*list)
	except (SystemExit, xmpp.NodeProcessed):
		result = 1
	except Exception:
		result = -1
		crashLog(handler.func_name)
	return result


def executeHandlers(type, list=()):
	"""
	Executes all handlers by type with list as list of args
	"""
	handlers = Handlers[type]
	for handler in handlers:
		execute(handler, list)


def registerHandler(type, func):
	"""
	Registers handlers and remove if the same is already exists
	"""
	logger.info("main: add \"%s\" to handle type %s" % (func.func_name, type))
	for handler in Handlers[type]:
		if handler.func_name == func.func_name:
			Handlers[type].remove(handler)
	Handlers[type].append(func)


def runThread(func, args=(), name=None, att=3, delay=0):
	"""
	Runs a thread with custom args and name
	Needed to reduce code
	Parameters:
		func: function you need to be running in a thread
		args: function arguments
		name: thread name
		att: number of attempts
		delay: if set, then threading.Timer will be started, not threading.Thread

	"""
	if delay:
		logger.debug("threading: starting timer for %s%s, name:%s, delay:%s" % (func.func_name, str(args), name, delay))
		thr = threading.Timer(delay, execute, (func, args))
	else:
		thr = threading.Thread(target=execute, args=(func, args))
	name = name or func.__name__
	name = str(name) + "-" + str(time.time())
	thr.name = name
	try:
		thr.start()
	except (threading.ThreadError):
		if att:
			return runThread(func, args, name, (att - 1), delay)
		crashLog("runThread.%s" % name)


def getGatewayRev():
	"""
	Gets gateway revision using git or custom revision number
	"""
	revNumber, rev = 261, 0
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)


def vk2xmpp(id):
	"""
	Converts vk ids to jabber ids and vice versa
	Returns id@TransportID if parameter "id" is int or str(int)
	Returns id if parameter "id" is id@TransportID
	Returns TransportID if "id" is TransportID
	"""
	if not utils.isNumber(id) and "@" in id:
		id = id.split("@")[0]
		if utils.isNumber(id):
			id = int(id)
	elif id != TransportID:
		id = u"%s@%s" % (id, TransportID)
	return id


Revision = getGatewayRev()

## Escape xmpp non-allowed chars
badChars = [x for x in xrange(32) if x not in (9, 10, 13)] + [57003, 65535]
escape = re.compile("|".join(unichr(x) for x in badChars), re.IGNORECASE | re.UNICODE | re.DOTALL).sub
sortMsg = lambda msgOne, msgTwo: msgOne.get("mid", 0) - msgTwo.get("mid", 0)
require = lambda name: os.path.exists("extensions/%s.py" % name)


class Settings(object):
	"""
	This class is needed to store users settings
	"""
	def __init__(self, source, user=True):
		"""
		Uses GLOBAL_USER_SETTINGS variable as default user's settings
		and updates it using settings read from the file
		"""
		self.filename = "%s/%s/settings.txt" % (settingsDir, source)
		if user:
			self.settings = deepcopy(GLOBAL_USER_SETTINGS)
		else:
			self.settings = TRANSPORT_SETTINGS
		userSettings = eval(rFile(self.filename)) or {}
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
		elif not self.settings.has_key(attr):
			return False
		else:
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


class VK(object):
	"""
	The base class containts the functions which directly works with VK
	"""
	def __init__(self, number=None, password=None, source=None):
		self.number = number
		self.password = password
		self.source = source
		self.pollConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.pollServer = ""
		self.pollInitialzed = False
		self.online = False
		self.userID = 0
		self.friends_fields = set(["screen_name"])
		logger.debug("VK.__init__ with number:%s from jid:%s" % (number, source))

	getToken = lambda self: self.engine.token

	def checkData(self):
		"""
		Checks the token or authorizes by password
		Raises api.TokenError if token is invalid or missed in hell
		Raises api.VkApiError if phone/password is invalid
		"""
		logger.debug("VK: checking data (jid: %s)" % self.source)
		if not self.engine.token and self.password:
			logger.debug("VK.checkData: trying to login via password")
			self.engine.loginByPassword()
			self.engine.confirmThisApp()
			if not self.checkToken():
				raise api.VkApiError("Incorrect phone or password")

		elif self.engine.token:
			logger.debug("VK.checkData: trying to use token")
			if not self.checkToken():
				logger.error("VK.checkData: token invalid: %s" % self.engine.token)
				raise api.TokenError("Token is invalid: %s (jid: %s)" % (self.engine.token, self.source))
		else:
			logger.error("VK.checkData: no token and no password (jid: %s)" % self.source)
			raise api.TokenError("%s, Where the hell is your token?" % self.source)

	## TODO: this function must be rewritten. We have dict from self.method, so trying make int using dict is bad idea.
	def checkToken(self):
		"""
		Checks the api token
		"""
		try:
			int(self.method("isAppUser", force=True))
		except (api.VkApiError, TypeError):
			return False
		return True

	def auth(self, token=None, raise_exc=False, initpoll=True):
		"""
		Initializes self.engine object
		Calls self.checkData() and initializes longPoll if all is ok
		"""
		logger.debug("VK.auth %s token (jid: %s)" % ("with" if token else "without", self.source))
		self.engine = api.APIBinding(self.number, self.password, token=token, debug=DEBUG_API)
		try:
			self.checkData()
		except api.CaptchaNeeded:
			raise
		except api.AuthError as e:
			logger.error("VK.auth failed with error %s (jid: %s)" % (e.message, self.source))
			if raise_exc:
				raise
			return False
		except api.TokenError:
			raise
		except Exception:
			crashLog("VK.auth")
			if raise_exc:
				raise
			return False
		logger.debug("VK.auth completed")
		if initpoll:
			self.online = True
			runThread(self.initPoll, (), "__initPoll-%s" % self.source)
		return True

	def initPoll(self):
		"""
		Initializes longpoll
		Returns False if error occurred
		"""
		self.pollInitialzed = False
		logger.debug("longpoll: requesting server address (jid: %s)" % self.source)
		try:
			response = self.method("messages.getLongPollServer")
		except Exception:
			return False
		if not response:
			logger.warning("longpoll: no response!")
			return False
		self.pollServer = "http://%s" % response.pop("server")
		self.pollConfig.update(response)
		logger.debug("longpoll: server: %s (jid: %s)" % (self.pollServer, self.source))
		self.pollInitialzed = True
		return True

	def makePoll(self):
		"""
		Raises api.LongPollError if poll not yet initialized (self.pollInitialzed)
		Else returns socket object connected to poll server
		"""
		if not self.pollInitialzed:
			raise api.LongPollError("The Poll wasn't initialized yet")
		return self.engine.RIP.getOpener(self.pollServer, self.pollConfig)

	def method(self, method, args=None, nodecode=False, force=False):
		"""
		This is a duplicate function of self.engine.method
		Needed to handle errors properly exactly in __main__
		Parameters:
			method: obviously VK API method
			args: method aruments
			nodecode: decode flag (make json.loads or not)
			force: says that method will be executed even the captcha and not online
		See library/vkapi.py for more information about exceptions
		Returns method execition result
		"""
		args = args or {}
		result = {}
		Stats["method"] += 1
		if not self.engine.captcha and (self.online or force):
			try:
				result = self.engine.method(method, args, nodecode)
			except (api.InternalServerError, api.AccessDenied) as e:
				# To prevent returning True from checkData()
				if force:
					raise

			except api.NetworkNotFound as e:
				self.online = False

			except api.CaptchaNeeded as e:
				logger.error("VK: running captcha challenge (jid: %s)" % self.source)
				self.captchaChallenge()
				result = 0 ## why?

			except api.NotAllowed as e:
				if self.engine.lastMethod[0] == "messages.send":
					sendMessage(Component, self.source, vk2xmpp(args.get("user_id", TransportID)), _("You're not allowed to perform this action."))

			except api.VkApiError as e:
				# There are several types of VkApiError
				# But the user defenitely must be removed. The question is: how? Is he should have been completely exterminated or just removed?
				roster = False
				if e.message == "User authorization failed: user revoke access for this token.":
					roster = True
				elif e.message == "User authorization failed: invalid access_token.":
					sendMessage(Component, self.source, TransportID, _(e.message + " Please, register again"))
				runThread(removeUser, (self.source, roster))
				logger.error("VK: apiError %s (jid: %s)" % (e.message, self.source))
				self.online = False
			else:
				return result
			logger.error("VK: error %s occurred while executing method(%s) (%s) (jid: %s)" % (e.__class__.__name__, method, e.message, self.source))
			return False

	def captchaChallenge(self):
		"""
		Runs all handlers registered to event 04 (captcha)
		Removes user from poll until the challenge is done
		"""
		if self.engine.captcha:
			executeHandlers("evt04", (self,))
			self.online = False

	def disconnect(self):
		"""
		Stops all user handlers and removes himself from Poll
		"""
		logger.debug("VK: user %s has left" % self.source)
		self.online = False
		runThread(executeHandlers, ("evt06", (self,)))
		runThread(self.method, ("account.setOffline", None, True, True))

	def getFriends(self, fields=None):
		"""
		Executes friends.get and formats it in key-value style
		Example: {1: {"name": "Pavel Durov", "online": False}
		Parameter fields is needed to receive advanced fields which will be added in result values
		"""
		fields = fields or self.friends_fields
		raw = self.method("friends.get", {"fields": str.join(chr(44), fields)}) or ()
		friends = {}
		for friend in raw:
			uid = friend["uid"]
			online = friend["online"]
			name = escape("", str.join(chr(32), (friend["first_name"], friend["last_name"])))
			friends[uid] = {"name": name, "online": online}
			for key in fields:
				if key != "screen_name": # screen_name is the default
					friends[uid][key] = friend.get(key)
		return friends

	def getMessages(self, count=5, mid=0):
		"""
		Gets last messages list count 5 with last id mid
		"""
		values = {"out": 0, "filters": 1, "count": count}
		if mid:
			del values["count"], values["filters"]
			values["last_message_id"] = mid
		return self.method("messages.get", values)

	def getUserID(self):
		"""
		Gets user id and adds his id into jidToID
		"""
		self.userID = self.method("execute.getUserID")
		if self.userID:
			jidToID[self.userID] = self.source
		return self.userID

	def getUserData(self, uid, fields=None):
		"""
		Gets user data. Such as name, photo, etc
		If user exists in friends and if no advanced fields issued will return friends[uid]
		Otherwise will request method users.get
		Default fields is ["screen_name"]
		"""
		if not fields:
			if self.source in Transport:
				user = Transport[self.source]
				if uid in user.friends:
					return user.friends[uid]
			fields = ["screen_name"]
		data = self.method("users.get", {"fields": ",".join(fields), "user_ids": uid}) or {}
		if not data:
			data = {"name": "None"}
			for key in fields:
				data[key] = "None"
		else:
			data = data.pop()
			data["name"] = escape("", str.join(chr(32), (data.pop("first_name"), data.pop("last_name"))))
		return data

	def sendMessage(self, body, id, mType="user_id", more={}):
		"""
		Sends message to VK id
		Parameters:
			body: obviously the message body
			id: user id
			mType: message type (user_id is for dialogs, chat_id is for chats)
			more: for advanced features such as photos (attachments)
		"""
		Stats["msgout"] += 1
		values = {mType: id, "message": body, "type": 0}
		values.update(more)
		result = None
		try:
			result = self.method("messages.send", values)
		except api.VkApiError:
			crashLog("messages.send")
		return result


class User(object):
	"""
	Main class contains the functions to connect xmpp & VK
	"""
	def __init__(self, source=""):
		
		self.auth = None
		self.exists = None

		self.friends = {}
		self.hashes = {}
		
		self.lastMsgID = 0
		self.password = None
		self.rosterSet = None
		
		self.source = source
		self.token = None
		self.typing = {}
		self.username = None
	
		self.resources = set([])
		self.settings = Settings(source)
		self.last_udate = time.time()
		self.sync = threading._allocate_lock()
		logger.debug("initializing User (jid: %s)" % self.source)

	def __eq__(self, user):
		if isinstance(user, User):
			return user.source == self.source
		return self.source == user

	def connect(self, raise_exc=False):
		"""
		Calls VK.auth() and calls captchaChallenge on captcha
		Updates db if auth() is done
		Raises exception if raise_exc == True
		"""
		self.vk = VK(self.username, self.password, self.source)
		data = runDatabaseQuery("select * from users where jid=?", (self.source,), many=False)
		if data:
			if not self.token and not self.password:
				logger.debug("User exists in database. Using his information (jid: %s)" % self.source)
				self.exists = True
				self.source, self.username, self.token, self.lastMsgID, self.rosterSet = data
			elif self.password or self.token:
				logger.debug("User: %s exists in database. The record will be deleted." % self.source)
				runThread(removeUser, (self,))

		logger.debug("User: connecting (jid: %s)" % self.source)
		self.auth = None
		## TODO: Check the code below
		## what the hell is going on down here?
		if self.username and self.password:
			self.vk.username = self.username
			self.vk.password = self.password
		try:
			self.auth = self.vk.auth(self.token, raise_exc=raise_exc)
		except api.CaptchaNeeded:
			self.sendSubPresence()
			self.vk.captchaChallenge()
			return True
		except (api.TokenError, api.AuthError):
			if raise_exc:
				raise
			return False
		else:
			logger.debug("User: auth=%s (jid: %s)" % (self.auth, self.source))

		if self.auth and self.vk.getToken():
			logger.debug("User: updating database because auth done (jid: %s)" % self.source)
			# User isn't exists so we gonna make a new record in the db
			if not self.exists:
				runDatabaseQuery("insert into users values (?,?,?,?,?)", (self.source, "", self.vk.getToken(), self.lastMsgID, self.rosterSet), True)

			elif self.password:
				runDatabaseQuery("update users set token=? where jid=?", (self.vk.getToken(), self.source), True)
			executeHandlers("evt07", (self,))
			self.vk.online = True
			self.friends = self.vk.getFriends()
		return self.vk.online

	def initialize(self, force=False, send=True, resource=None, raise_exc=False):
		"""
		Initializes user after self.connect() is done:
			1. Receives friends list and set 'em to self.friends
			2. If #1 is done and roster is not yet set (self.rosterSet) then sends subscribe presence
			3. Calls sendInitPresnece() if parameter send is True
			4. Adds resource if resource parameter exists
		Parameters:
			force: force sending subscribe presence
			send: needed to know if need to send init presence or not
			resource: add resource in self.resources to prevent unneeded stanza sending
		"""
		logger.debug("User: called init for user %s" % self.source)
		Transport[self.source] = self
		if not self.friends:
			self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("User: sending subscribe presence with force:%s (jid: %s)" % (force, self.source))
			self.sendSubPresence(self.friends)
		if send: self.sendInitPresence()
		if resource: self.resources.add(resource)
		runThread(self.vk.getUserID)
		Poll.add(self)
		self.sendMessages(True)
		runThread(executeHandlers, ("evt05", (self,)))

	def sendInitPresence(self):
		"""
		Sends init presence (available) to user from all his online friends
		"""
		if not self.settings.i_am_ghost:
			if not self.friends:
				self.friends = self.vk.getFriends()
			count = len(self.friends)
			logger.debug("User: sending init presence (friends count: %s) (jid %s)" % (count, self.source))
			for uid, value in self.friends.iteritems():
				if value["online"]:
					sendPresence(self.source, vk2xmpp(uid), None, value["name"], caps=True)
		if not self.vk.engine.captcha:
			sendPresence(self.source, TransportID, None, IDENTIFIER["name"], caps=True)

	def sendOutPresence(self, destination, reason=None, all=False):
		"""
		Sends out presence (unavailable) to destination and set reason if exists
		Parameters:
			destination: to whom send the stanzas
			reason: offline status message
			all: send an unavailable from all friends or only the ones who's online
		"""
		logger.debug("User: sending out presence to %s" % self.source)
		friends = self.friends.keys()
		if not all and friends:
			friends = filter(lambda key: self.friends[key]["online"], friends)

		for uid in friends + [TransportID]:
			sendPresence(destination, vk2xmpp(uid), "unavailable", reason=reason)

	def sendSubPresence(self, dist=None):
		"""
		Sends subsribe presence to self.source
		Parameteres:
			dist: friends list
		"""
		dist = dist or {}
		for uid, value in dist.iteritems():
			sendPresence(self.source, vk2xmpp(uid), "subscribe", value["name"])
		sendPresence(self.source, TransportID, "subscribe", IDENTIFIER["name"])
		if dist:
			self.rosterSet = True
			runDatabaseQuery("update users set rosterSet=? where jid=?", (self.rosterSet, self.source), True)

	def sendMessages(self, init=False):
		"""
		Sends messages from vk to xmpp and call message01 handlers
		Paramteres:
			init: needed to know if function called at init (add time or not)
		Plugins notice (msg01):
			If plugin returs None then message will not be sent by transport's core, it shall be sent by plugin itself
			Otherwise, if plugin returns string, the message will be sent by transport's core
		"""
		with self.sync:
			date = 0
			messages = self.vk.getMessages(20, self.lastMsgID)
			if not messages or not messages[0]:
				return None
			messages = sorted(messages[1:], sortMsg)
			for message in messages:
				# If message wasn't sent by our user
				if not message["out"]:
					Stats["msgin"] += 1
					fromjid = vk2xmpp(message["uid"])
					body = uhtml(message["body"])
					iter = Handlers["msg01"].__iter__()
					for func in iter:
						try:
							result = func(self, message)
						except Exception:
							result = ""
							crashLog("handle.%s" % func.__name__)

						if result is None:
							for func in iter:
								utils.apply(func, (self, message))
							break
						else:
							body += result
					else:
						if self.settings.force_vk_date:
							date = message["date"]
						sendMessage(Component, self.source, fromjid, escape("", body), date)
		if messages:
			self.lastMsgID = messages[-1]["mid"]
			runDatabaseQuery("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.source), True)

		if not self.vk.userID:
			self.vk.getUserID()

	def processPollResult(self, opener):
		"""
		Processes poll result
		Retur codes:
			0: need to reinit poll (add user to the poll buffer)
			1: all is fine (request again)
			-1: just continue iteration, ignoring this user (user won't be added for the next iteration)
		"""
		if DEBUG_POLL:
			logger.debug("longpoll: processing result (jid: %s)" % self.source)

		if self.vk.engine.captcha:
			return -1

		try:
			data = opener.read()
		except (httplib.BadStatusLine, socket.error):
			return 1

		if not data:
			logger.error("longpoll: no data. Will request again")
			return 1

		data = json.loads(data)

		if "failed" in data:
			logger.debug("longpoll: failed. Searching for new server (jid: %s)" % self.source)
			return 0

		self.vk.pollConfig["ts"] = data["ts"]
		for evt in data.get("updates", ()):
			typ = evt.pop(0)

			if typ == 4:  # new message
				runThread(self.sendMessages, name="sendMessages-%s" % self.source)

			elif typ == 8: # user has joined
				if not self.settings.i_am_ghost:
					uid = abs(evt[0])
					sendPresence(self.source, vk2xmpp(uid), nick=self.vk.getUserData(uid)["name"], caps=True)

			elif typ == 9: # user has left
				uid = abs(evt[0])
				sendPresence(self.source, vk2xmpp(uid), "unavailable")

			elif typ == 61: # user is typing
				if evt[0] not in self.typing:
					sendMessage(Component, self.source, vk2xmpp(evt[0]), typ="composing")
				self.typing[evt[0]] = time.time()
		return 1


	def updateTypingUsers(self, cTime):
		"""
		Sends "paused" message event to stop user from composing a message
		Sends only if last typing activity in VK was >10 secs ago
		"""
		for user, last in self.typing.items():
			if cTime - last > 10:
				del self.typing[user]
				sendMessage(Component, self.source, vk2xmpp(user), typ="paused")

	def updateFriends(self, cTime):
		"""
		Updates friends list
		Sends subscribe presences if new friends found
		Sends unsubscribe presences if some friends disappeared
		"""
		if (cTime - self.last_udate) > 360 and not self.vk.engine.captcha:
			if not self.settings.i_am_ghost:
				if self.settings.keep_online:
					self.vk.method("account.setOnline")
				self.last_udate = cTime
				friends = self.vk.getFriends()
				if not friends:
					logger.error("updateFriends: no friends received (jid: %s)." % self.source)
					return None
				if friends:
					for uid in friends:
						if uid not in self.friends:
							self.sendSubPresence({uid: friends[uid]})
					for uid in self.friends:
						if uid not in friends:
							sendPresence(self.source, vk2xmpp(uid), "unsubscribe")
							sendPresence(self.source, vk2xmpp(uid), "unsubscribed")
					self.friends = friends

	def tryAgain(self):
		"""
		Tries to execute self.initialize() again and connect() if needed
		Usually needed after captcha challenge is done
		"""
		logger.debug("calling reauth for user %s" % self.source)
		if not self.vk.online:
			self.token = None # we reset the token to prevent user deletion from the database
			self.connect()
		self.initialize(True)


class Poll:
	"""
	Class used to handle longpoll
	"""
	__list = {}
	__buff = set()
	__lock = threading._allocate_lock()


	@classmethod
	def __add(cls, user):
		"""
		Issues readable socket to use it in select()
		Adds user in buffer on error occurred
		Adds user in self.__list if no errors
		"""
		try:
			# Getting socket for polling it by select()
			opener = user.vk.makePoll()
		except Exception as e:
			if not isinstance(e, api.LongPollError):
				crashLog("poll.add")
			logger.error("longpoll: failed to make poll (jid: %s)" % user.source)
			cls.__addToBuff(user)
			return False
		else:
			cls.__list[opener.sock] = (user, opener)
		return opener

	@classmethod
	def __addToBuff(cls, user):
		"""
		Adds user to the list of "bad" users
		The list is mostly contain users whose poll request was failed for some reasons
		"""
		cls.__buff.add(user)
		logger.debug("longpoll: adding user to watcher (jid: %s)" % user.source)
		runThread(cls.__initPoll, (user,), "__initPoll-%s" % user.source)

	@classmethod
	def add(cls, some_user):
		"""
		Adds the User class object to poll
		"""
		with cls.__lock:
			if some_user in cls.__buff:
				return None
			for sock, (user, opener) in cls.__list.iteritems():
				if some_user == user:
					break
			else:
				cls.__add(some_user)

	clear = staticmethod(__list.clear)

	@classmethod
	def __initPoll(cls, user):
		"""
		Tries to reinitialize poll if needed in 10 times (each 10 seconds)
		As soon as poll initialized user will be removed from buffer
		"""
		for x in xrange(10):
			if user.source not in Transport:
				logger.debug("longpoll: while we wasted our time, user has left (jid: %s)" % user.source)
				with cls.__lock:
					if user in cls.__buff:
						cls.__buff.remove(user)
				return None
			if Transport[user.source].vk.initPoll():
				with cls.__lock:
					logger.debug("longpoll: successfully initialized longpoll (jid: %s)" % user.source)
					if user not in cls.__buff:
						return None
					cls.__buff.remove(user)
					cls.__add(Transport[user.source])
					break
			time.sleep(10)
		else:
			with cls.__lock:
				if user not in cls.__buff:
					return None
				cls.__buff.remove(user)
			logger.error("longpoll: failed to add user to poll in 10 retries (jid: %s)" % user.source)

	@classmethod
	def process(cls):
		"""
		Processes poll sockets by select.select()
		As soon as socket will be ready to be read, will be called user.processPollResult()
		Read processPollResult.__doc__ to learn more about status codes
		"""
		while ALIVE:
			socks = cls.__list.keys()
			if not socks:
				time.sleep(0.02)
				continue
			try:
				ready, error = select.select(socks, [], socks, 2)[::2]
			except (select.error, socket.error) as e:
				logger.error("longpoll: %s" % (e.message)) ## debug?

			for sock in error:
				with cls.__lock:
					# We will just re-add the user to poll in case if anything wrong happen to socket
					try:
						cls.__add(cls.__list.pop(sock)[0])
					except KeyError:
						continue

			for sock in ready:
				# We need to handle all synchronously
				with cls.__lock:
					try:
						user, opener = cls.__list.pop(sock)
					except KeyError:
						continue

					user = Transport.get(user.source) # WHAT?
					if not user:
						continue
					## We need to check if the user hasn't left yet
					if not user.vk.online:
						continue
					runThread(cls.processResult, (user, opener), "poll.processResult-%s" % user.source)

			with cls.__lock:
				for sock, (user, opener) in cls.__list.items():
					if not user.vk.online:
						logger.debug("longpoll: user is not online, so removing their from poll (jid: %s)" % user.source)
						try:
							del cls.__list[sock]
						except KeyError:
							pass

	@classmethod
	def processResult(cls, user, opener):
		"""
		Processes the select result (see above)
		Handles answers from user.processPollResult()
		Decides neiter if need to add user to poll or not
		"""
		result = execute(user.processPollResult, (opener,))
		if DEBUG_POLL:
			logger.debug("longpoll: result=%d (jid: %s)" % (result, user.source))
		if result == -1:
			return None
		# if mark user.vk.Pollinitialized as False
		# then there will be an exception
		# after that, user will be reinitialized
		if not result:
			user.vk.pollInitialzed = False
		cls.add(user)


def sendPresence(destination, source, pType=None, nick=None, reason=None, caps=None, show=None):
	"""
	Sends presence to destination from source
	Parameters:
		destination: to whom send the presence
		source: from who send the presence
		pType: the presence type
		nick: add <nick> tag to stanza or not
		reason: set status message or not
		caps: add caps into stanza or not
		show: add status show
	"""
	presence = xmpp.Presence(destination, pType, frm=source, status=reason, show=show)
	if nick:
		presence.setTag("nick", namespace=xmpp.NS_NICK)
		presence.setTagData("nick", nick)
	if caps:
		presence.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": Revision}, xmpp.NS_CAPS)
	executeHandlers("prs02", (presence, destination, source))
	sender(Component, presence)


def sendMessage(cl, destination, source, body=None, timestamp=0, typ="active"):
	"""
	Sends message to destination from source
	Parameters:
		cl: xmpp.Client object
		destination: to whom send the message
		source: from who send the message
		body: obviously message body
		timestamp: message timestamp (XEP-0091)
		typ: xmpp chatstates type (XEP-0085)
	"""
	msg = xmpp.Message(destination, body, "chat", frm=source)
	msg.setTag(typ, namespace=xmpp.NS_CHATSTATES)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	executeHandlers("msg03", (msg, destination, source))
	sender(cl, msg)


def sender(cl, stanza, cb=None, args={}):
	"""
	Sends stanza. Writes a crashlog on error
	Parameters:
		cl: xmpp.Client object
		stanza: xmpp.Node object
		cb: callback function
		args: callback function arguments
	"""
	if cb:
		cl.SendAndCallForResponse(stanza, cb, args)
	else:
		try:
			cl.send(stanza)
		except Exception:
			crashLog("sender")
			disconnectHandler(True)


def updateCron():
	"""
	Calls the functions to update friends and typing users list
	"""
	while ALIVE:
		for user in Transport.values():
			cTime = time.time()
			user.updateTypingUsers(cTime)
			user.updateFriends(cTime)
		time.sleep(2)


def calcStats():
	"""
	Returns count(*) from users database
	"""
	countOnline = len(Transport)
	countTotal = runDatabaseQuery("select count(*) from users", many=False)[0]
	return [countTotal, countOnline]


def removeUser(user, roster=False, notify=True):
	"""
	Removes user from database
	Parameters:
		user: User class object or jid without resource
		roster: remove vk contacts from user's roster (only if User class object was in first param)
	"""
	if isinstance(user, (str, unicode)): # unicode is default, but... who knows
		source = user
	else:
		source = user.source
	user = Transport.get(source) ## here's probability it's not the User object
	if notify:
		sendMessage(Component, source, TransportID, _("The record in database about you was EXTERMINATED! If you weren't asked for it, then let us know."), -1) ## Will russians understand this joke?
	logger.debug("User: removing user from db (jid: %s)" % source)
	runDatabaseQuery("delete from users where jid=?", (source,), True)
	logger.debug("User: deleted (jid: %s)" % source)
	if source in Transport:
		del Transport[source]
	if roster and user:
		friends = user.friends
		user.exists = False ## Make the Daleks happy
		if friends:
			logger.debug("User: removing myself from roster (jid: %s)" % source)
			for id in friends.keys() + [TransportID]:
				jid = vk2xmpp(id)
				sendPresence(source, jid, "unsubscribe")
				sendPresence(source, jid, "unsubscribed")
			user.settings.exterminate()
			executeHandlers("evt03", (user,))
		user.vk.online = False


def getPid():
	"""
	Gets new PID and kills the previous PID
	by signals 15 and then 9
	"""
	pid = os.getpid()
	if os.path.exists(pidFile):
		oldPid = rFile(pidFile)
		if oldPid:
			Print("#-# Killing old transport instance: ", False)
			oldPid = int(oldPid)
			if pid != oldPid:
				try:
					os.kill(oldPid, 15)
					time.sleep(3)
					os.kill(oldPid, 9)
				except OSError:
					pass
				Print("%d killed.\n" % oldPid, False)
	wFile(pidFile, str(pid))


def loadExtensions(dir):
	"""
	Read and exec files located in dir
	"""
	for file in os.listdir(dir):
		if not file.startswith("."):
			execfile("%s/%s" % (dir, file), globals())


def getModulesList():
	"""
	Makes a list of modules could be found in modules folder
	"""
	modules = []
	for file in os.listdir("modules"):
		name, ext = os.path.splitext(file)
		if ext == ".py":
			modules.append(name)
	return modules


class ModuleLoader:

	"""
	A complete proxy for modules. You can easy load, reload and unload any module using this.
	Modules are different from extensions.
	While extensions works in main globals() and have their callbacks,
	modules works in their own globals() and they're not affect to the core.
	Unfortunately, most of modules are not protected from harm and they may have affect on the connection
	"""

	loaded = set([])
	def register(self, module):
		if hasattr(module, "load"):
			module.load()
		loaded.add(module)

	def unregister(self, module):
		if hasattr(module, "unload"):
			module.unload()
		loaded.remove(module)

	@classmethod
	def load(cls, list=[]):
		result =[]
		for name in list:
			try:
				module = __import__(name, globals(), locals())
			except Exception:
				crashlog("module_loader")
			else:
				result.append(name)
				cls.register(module)
		return result

	@classmethod
	def unload(cls, list=[]):
		result = []
		for name in list:
			if name in sys.modules:
				cls.unregister(sys.modules[name])
				del sys.modules[name]
				result.append(name)
		return result

	@classmethod
	def reload(cls, list=[]):
		result = []
		for name in list:
			if name in sys.modules:
				module = sys.modules[name]
				cls.unregister(module)
				try:
					cls.register(reload(module))
				except Exception:
					crashlog("module_loader")
				else:
					result.append(name)
		return result


def connect():
	"""
	Just makes a connection to the jabber-server
	Returns False if faled, True if completed
	"""
	global Component
	Component = xmpp.Component(Host, debug=DEBUG_XMPPPY)
	Print("\n#-# Connecting: ", False)
	if not Component.connect((Server, Port)):
		Print("fail.\n", False)
		return False
	else:
		Print("ok.\n", False)
		Print("#-# Auth: ", False)
		if not Component.auth(TransportID, Password):
			Print("failed (%s/%s)!\n" % (Component.lastErr, Component.lastErrCode), True)
			return False
		else:
			Print("ok.\n", False)
			Component.RegisterDisconnectHandler(disconnectHandler)
			Component.set_send_interval(STANZA_SEND_INTERVAL)
	return True


def initializeUsers():
	"""
	Initializes users by sending them "probe" presence
	"""
	Print("#-# Initializing users", False)
	users = runDatabaseQuery("select jid from users", semph=None)
	for user in users:
		Print(".", False)
		sender(Component, xmpp.Presence(user[0], "probe", frm=TransportID))
	Print("\n#-# Finished.")


def runMainActions():
	"""
	Running main actions to make transport work
	"""
	if allowBePublic:
		makeMeKnown()
	for num, event in enumerate(Handlers["evt01"]):
		runThread(event, (), "extension-%d" % num)
	runThread(Poll.process, (), "longPoll")
	runThread(updateCron, (), "updateCron")
	ModuleLoader.load(getModulesList())


def main():
	"""
	Running main actions to start the transport
	Such as pid, db, connect
	"""
	getPid()
	initDatabase(DatabaseFile)
	if connect():
		initializeUsers()
		runMainActions()
	else:
		disconnectHandler(False)


def disconnectHandler(crash=True):
	"""
	Handles disconnect
	And writes a crashlog if crash parameter is equals True
	"""
	logger.debug("disconnectHandler has been called!")
	executeHandlers("evt02")
	if crash:
		crashLog("main.disconnect")
	## In case to catch some weird errors right here
	logger.critical("Disconnecting from the server")
	try:
		Component.disconnect()
	except AttributeError:
		pass
	except Exception:
		crashLog("disconnect_handler")
	global ALIVE
	ALIVE = False
	logger.info("Disconnected successfully!")
	if not Daemon:
		logger.warning("The trasnport is going to be restarted!")
		Print("Reconnecting...")
		time.sleep(5)
		os.execl(sys.executable, sys.executable, *sys.argv)
	else:
		logger.info("The transport is shutting down!")
		sys.exit(-1)


def makeMeKnown():
	"""
	That's such a weird function just makes post request
	to the vk4xmpp monitor which is located on http://xmppserv.ru/xmpp-monitor
	You can check out the source of The VK4XMPP Monitor utilty over there: https://github.com/aawray/xmpp-monitor
	"""
	if WhiteList:
		WhiteList.append(VK4XMPP_MONITOR_SERVER)
	if TransportID.split(".")[1] != "localhost":
		RIP = api.RequestProcessor()
		RIP.post(VK4XMPP_MONITOR_URL, {"add": TransportID})
		Print("#! Information about this transport has been successfully published.")


def exit(signal=None, frame=None):
	"""
	Just stops the transport and sends unavailable presence
	"""
	status = "Shutting down by %s" % ("SIGTERM" if signal == 15 else "SIGINT")
	Print("#! %s" % status, False)
	for user in Transport.itervalues():
		user.sendOutPresence(user.source, status, all=True)
		Print("." * len(user.friends), False)
	Print("\n")
	executeHandlers("evt02")
	try:
		os.remove(pidFile)
	except OSError:
		pass
	os._exit(1)


if __name__ == "__main__":
	signal.signal(signal.SIGTERM, exit)
	signal.signal(signal.SIGINT, exit)
	loadExtensions("extensions")
	transportSettings = Settings(TransportID, user=False)
	main()
	while ALIVE:
		try:
			Component.iter(6)
		except Exception:
			logger.critical("disconnected")
			crashLog("component.iter")
			disconnectHandler(True)


# This is the end!
