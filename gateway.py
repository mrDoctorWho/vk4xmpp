#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v2.27
# © simpleApps, 2013 — 2014.
# Program published under MIT license.

import gc
import json
import httplib
import logging
import os
import re
import select
import socket
import signal
import sys
import threading
import time
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

import xmpp
import utils

from itypes import Database
from webtools import *
from writer import *
from stext import *
from stext import _

Transport = {}
WatcherList = []
WhiteList = []
jidToID = {}

TransportFeatures = [xmpp.NS_DISCO_ITEMS,
					xmpp.NS_DISCO_INFO,
					xmpp.NS_RECEIPTS,
					xmpp.NS_REGISTER,
					xmpp.NS_GATEWAY,
					xmpp.NS_VERSION,
					xmpp.NS_CAPTCHA,
					xmpp.NS_STATS,
					xmpp.NS_VCARD,
					xmpp.NS_DELAY,
					xmpp.NS_PING,
					xmpp.NS_LAST]

UserFeatures = [xmpp.NS_CHATSTATES,
				xmpp.NS_LAST]

IDENTIFIER = {"type": "vk",
			"category": "gateway",
			"name": "VK4XMPP Transport"}

Semaphore = threading.Semaphore()

LOG_LEVEL = logging.DEBUG
USER_LIMIT = 0
DEBUG_XMPPPY = False
THREAD_STACK_SIZE = 0
MAXIMUM_FORWARD_DEPTH = 10 ## We need to go deeper.
STANZA_SEND_INTERVAL = 0.03125
VK_ACCESS = 69638
GLOBAL_USER_SETTINGS = {"groupchats": {"label": "Handle groupchats", "value": 1}, 
						"keep_onlne": {"label": "Keep my status online", "value": 1}}


pidFile = "pidFile.txt"
logFile = "vk4xmpp.log"
crashDir = "crash"
settingsDir = "settings"


from optparse import OptionParser
oParser = OptionParser(usage = "%prog [options]")
oParser.add_option("-c", "--config", dest = "Config",
				help = "general config file",
				metavar = "Config", default = "Config.txt")
(options, args) = oParser.parse_args()
Config = options.Config

PhotoSize = "photo_100"
DefLang = "ru"
evalJID = ""
AdditionalAbout = ""
ConferenceServer = ""

allowBePublic = True

startTime = int(time.time())

try:
	execfile(Config)
	Print("#-# Config loaded successfully.")
except Exception:
	Print("#! Error while loading config file:")
	wException()
	exit()

logger = logging.getLogger("vk4xmpp")
logger.setLevel(LOG_LEVEL)
loggerHandler = logging.FileHandler(logFile)
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s %(message)s",
				"[%d.%m.%Y %H:%M:%S]")
loggerHandler.setFormatter(formatter)
logger.addHandler(loggerHandler)

import vkapi as api

setVars(DefLang, root)

if THREAD_STACK_SIZE:
	threading.stack_size(THREAD_STACK_SIZE)
del formatter, loggerHandler

OS = "{0} {2:.16} [{4}]".format(*os.uname())
Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)


## Events (not finished yet so not sorted):
# 01 - start (threaded)
# 02 - shutdown (linear)
# 03 - user deletion (linear)
# 04 - captcha (linear)
# 05 - user became online (threaded)
# 06 - user became offline (linear)
## Messages: 01 outgoing (vk->xmpp), 02 incoming (xmpp)
## Presences: 01 status change, 02 - is used to modify presence (xmpp)
Handlers = {"msg01": [], "msg02": [],
			"evt01": [], "evt02": [],
			"evt03": [], "evt04": [],
			"evt05": [], "evt06": [],
			"prs01": [], "prs02": []}

Stats = {"msgin": 0, ## from vk
		 "msgout": 0, ## to vk
		 "method": 0}

DESC = _("© simpleApps, 2013 — 2014."
	"\nYou can support developing of this project"
	" via donation by:\nYandex.Money: 410012169830956"
	"\nWebMoney: Z405564701378 | R330257574689.")

def initDatabase(filename):
	"""
	Initializes database if it doesn't exists
	"""
	if not os.path.exists(filename):
		with Database(filename) as db:
			db("create table users (jid text, username text, token text, lastMsgID integer, rosterSet bool)")
			db.commit()
	return True

def execute(handler, list=()):
	"""
	Just executes handler(*list) safely
	If weird error is happened writes a crashlog
	"""
	try:
		result = handler(*list)
	except SystemExit:
		result = 1
	except Exception:
		result = -1
		crashLog(handler.func_name)
	return result

def apply(instance, args=()):
	"""
	Same as execute(), but just return none on error
	"""
	try:
		code = instance(*args)
	except Exception:
		code = None
	return code

## TODO: execute threaded handlers
def registerHandler(type, func):
	"""
	Registers handlers and remove if the same is already exists
	"""
	logger.info("main: add \"%s\" to handle type %s" % (func.func_name, type))
	for handler in Handlers[type]:
		if handler.func_name == func.func_name:
			Handlers[type].remove(handler)
	Handlers[type].append(func)

def executeHandlers(type, list=()):
	"""
	Executes all handlers by type with list as list of args
	"""
	for handler in Handlers[type]:
		execute(handler, list)

def runThread(func, args=(), name=None):
	"""
	Runs a thread with custom args and name
	Needed to reduce code
	"""
	thr = threading.Thread(target=execute, args=(func, args), name=name or func.func_name)
	try:
		thr.start()
	except threading.ThreadError:
		crashlog("runThread.%s" % name)

def getGatewayRev():
	"""
	Gets gateway revision using git or custom revision number
	"""
	revNumber, rev = 192, 0
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)

def vk2xmpp(id):
	"""
	Returns id@TransportID if parameter "id" is int or str(int)
	Returns id if parameter "id" is id@TransportID
	Returns TransportID if "id" is TransportID
	"""
	if not isNumber(id) and "@" in id:
		id = id.split("@")[0]
		if isNumber(id):
			id = int(id)
	elif id != TransportID:
		id = u"%s@%s" % (id, TransportID)
	return id


Revision = getGatewayRev()

## Escaping xmpp not-allowed chars
badChars = [x for x in xrange(32) if x not in (9, 10, 13)] + [57003, 65535]
escape = re.compile("|".join(unichr(x) for x in badChars), re.IGNORECASE | re.UNICODE | re.DOTALL).sub
sortMsg = lambda msgOne, msgTwo: msgOne.get("mid", 0) - msgTwo.get("mid", 0)
require = lambda name: os.path.exists("extensions/%s.py" % name)
isNumber = lambda obj: (not apply(int, (obj,)) is None)


class Settings(object):
	"""
	This class is needed to store users settings
	"""
	def __init__(self, source):
		"""
		Uses GLOBAL_USER_SETTINGS variable as default user's settings
		and updates it using settings read from the file
		"""
		self.filename = "%s/%s/settings.txt" % (settingsDir, source)
		self.settings = deepcopy(GLOBAL_USER_SETTINGS)
		self.settings.update(eval(rFile(self.filename)))
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
		if not hasattr(self, attr):
			raise AttributeError()
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
	The base class containts most of functions to work with VK
	"""
	def __init__(self, number, password=None, source=None):
		self.number = number
		self.password = password
		self.source = source
		self.pollConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.pollServer = ""
		self.pollInitialzed = False
		self.online = False
		self.userID = 0
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
				raise api.TokenError("Token is invalid: %s (jid: %s)" % (self.source, self.engine.token))
		else:
			logger.error("VK.checkData: no token and no password (jid: %s)" % self.source)
			raise api.TokenError("%s, Where the hell is your token?" % self.source)

	## TODO: this function must be rewritten. We have dict from self.method, so trying make int using dict is bad idea.
	def checkToken(self):
		"""
		Checks token
		"""
		try:
			int(self.method("isAppUser", force=True))
		except (api.VkApiError, TypeError):
			return False
		return True

	def auth(self, token=None, raise_exc=False):
		"""
		Initializes self.engine object
		Calls self.checkData() and initializes longPoll if all is ok
		"""
		logger.debug("VK.auth %s token" % ("with" if token else "without"))
		self.engine = api.APIBinding(self.number, self.password, token=token)
		try:
			self.checkData()
		except api.AuthError as e:
			logger.error("VK.auth failed with error %s" % e.message)
			if raise_exc:
				raise
			return False
		except Exception:
			crashLog("VK.auth")
			return False
		logger.debug("VK.auth completed")
		self.online = True
		runThread(self.initPoll, ())
		return True

	def initPoll(self):
		"""
		Initaalizes longpoll
		Returns False if error occurred
		"""
		self.pollInitialzed = False
		logger.debug("longpoll: requesting server address (jid: %s)" % self.source)
		try:
			response = self.method("messages.getLongPollServer")
		except Exception:
			return False
		if not response:
			logger.error("longpoll: no response!")
			return False
		self.pollServer = "http://%s" % response.pop("server")
		self.pollConfig.update(response)
		logger.debug("longpoll: server: %s" % (self.pollServer))
		self.pollInitialzed = True
		return True

	def makePoll(self):
		"""
		Raises api.LongPollError if poll not yet initialized (self.pollInitialzed)
		Else returns socket object connected to poll server
		"""
		if not self.pollInitialzed:
			raise api.LongPollError()
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
		Returns method result
		"""
		args = args or {}
		result = {}
		Stats["method"] += 1
		if not self.engine.captcha and (self.online or force):
			try:
				result = self.engine.method(method, args, nodecode)
			except api.CaptchaNeeded:
				logger.error("VK: running captcha challenge (jid: %s)" % self.source)
				self.captchaChallenge()
				result = 0
			except api.NotAllowed:
				if self.engine.lastMethod[0] == "messages.send":
					sendMessage(Component, self.source, vk2xmpp(args.get("user_id", TransportID)), _("You're not allowed to perform this action."))
			except api.VkApiError as e:
				roster = False
				if e.message == "User authorization failed: user revoke access for this token.":
					logger.critical("VK: %s" % e.message)
					roster = True
				elif e.message == "User authorization failed: invalid access_token.":
					sendMessage(Component, self.source, TransportID, _(e.message + " Please, register again"))
				removeUser(Transport.get(self.source, self), roster, False)

				self.online = False
				logger.error("VK: apiError %s for user %s" % (e.message, self.source))
			except api.NetworkNotFound:
				logger.critical("VK: network is unavailable. Is vk down?")
				self.online = False
		return result

	def captchaChallenge(self):
		"""
		Runs all handlers registered to event 04 (captcha)
		Removes user from poll until the challenge is done
		"""
		if self.engine.captcha:
			executeHandlers("evt04", (self,))
			if self.source in Transport:
				Poll.remove(Transport[self.source]) ## Do not foget to add user into poll again after the captcha challenge is done 

	def disconnect(self):
		"""
		Stops all user handlers and removes himself from Poll
		"""
		logger.debug("VK: user %s has left" % self.source)
		if self.source in Transport:
			Poll.remove(Transport[self.source])
		self.online = False
		executeHandlers("evt06")
		runThread(self.method, ("account.setOffline", None, True)) ## Maybe this one should be started in separate thread to do not let VK freeze main thread

	def getFriends(self, fields=None):
		"""
		Executes friends.get and formats it in key-values style
		Example: {1: {"name": "Pavel Durov", "online": False}
		Parameter fields is needed to receive advanced fields which will be added in result values
		"""
		fields = fields or ["screen_name"]
		raw = self.method("friends.get", {"fields": str.join(chr(44), fields)}) or ()
		friends = {}
		for friend in raw:
			uid = friend["uid"]
			online = friend["online"]
			name = escape("", str.join(chr(32), (friend["first_name"], friend["last_name"])))
			friends[uid] = {"name": name, "online": online}
			for key in fields:
				if key != "screen_name":
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
		user = Transport[self.source]
		if not fields:
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
			body: obviously message's body
			id: user id
			mType: message type (user_id is for dialogs, chat_id is for chats)
			more: for advanced features such as photos (attachments)
		"""
		try:
			Stats["msgout"] += 1
			values = {mType: id, "message": body, "type": 0}
			values.update(more)
			Message = self.method("messages.send", values)
		except Exception:
			crashLog("messages.send")
			Message = None
		return Message


class User(object):
	"""
	Main class contain the functions to connect xmpp & VK
	"""

	def __init__(self, data=(), source=""):
		self.password = None
		self.username = None
		if data:
			self.username, self.password = data
		self.source = source
		self.auth = None
		self.token = None
		self.exists = None
		self.rosterSet = None
		self.lastMsgID = 0
		self.typing = {}
		self.friends = {}
		self.chatUsers = {}
		self.hashes = {}
		self.resources = []
		self.settings = Settings(source)
		self.last_udate = time.time()
		self.__sync = threading._allocate_lock()
		self.vk = VK(self.username, self.password, self.source)
		logger.debug("initializing User (jid: %s)" % self.source)
		with Database(DatabaseFile, Semaphore) as db:
			db("select * from users where jid=?", (self.source,))
			data = db.fetchone()
		if data:
			if not self.token or not self.password:
				logger.debug("User exists in database. Using his information (jid: %s)" % self.source)
				self.exists = True
				self.source, self.username, self.token, self.lastMsgID, self.rosterSet = data
			elif self.password or self.token:
				logger.debug("User: %s exists in database. Record would be deleted." % self.source)
				runThread(removeUser, (self,))

	def __eq__(self, user):
		if isinstance(user, User):
			return user.source == self.source
		return self.source == user

	def connect(self, raise_exc=False):
		"""
		Calls VK.auth() and calls captchaChallenge on captcha
		Updates db if auth() is done
		Raises exception if needed -1 if an exception if raise_exc == True
		"""
		logger.debug("User: connecting (jid: %s)" % self.source)
		self.auth = False
		## TODO: Check the code below
		if self.username and self.password:
			self.vk.username = self.username
			self.vk.password = self.password
		try:
			self.auth = self.vk.auth(self.token, raise_exc=raise_exc)
		except api.CaptchaNeeded:
			self.sendSubPresence()
			self.vk.captchaChallenge()
			return True
		except api.AuthError:
			raise
		else:
			logger.debug("User: auth=%s (jid: %s)" % (self.auth, self.source))

		if self.auth and self.vk.getToken():
			logger.debug("User: updating database because auth done (jid: %s)" % self.source)
			if not self.exists:
				with Database(DatabaseFile, Semaphore) as db:
					db("insert into users values (?,?,?,?,?)", (self.source, "",
						self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set token=? where jid=?", (self.vk.getToken(), self.source))
			self.friends = self.vk.getFriends()
			self.vk.online = True
		return self.vk.online


	def initialize(self, force=False, send=True, resource=None, raise_exc=False):
		"""
		Initializes user after self.connect() is done:
			1. Receives friends list and set 'em to self.friends
			2. If #1 is done and roster is not yet set (self.rosterSet) then sends subscr presence
			3. Calls sendInitPresnece() if parameter send is True
			4. Adds resource if resource parameter exists
		Parameters:
			force: force sending subscribe presence
			send: needed to know if need to send init presence or not
			resource: add resource in self.resources to prevent unneeded stanza sending
		"""
		logger.debug("User: called init for user %s" % self.source)
		if not self.friends:
			self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("User: sending subscribe presence with force:%s (jid: %s)" % (force, self.source))
			self.sendSubPresence(self.friends)
		if send: self.sendInitPresence()
		if resource: self.resources.append(resource)
		runThread(self.vk.getUserID)
		Poll.add(self)
		self.sendMessages(True)
		runThread(executeHandlers, ("evt05", (self,)))

	def sendInitPresence(self):
		"""
		Sends init presence (available) to user from all his online friends
		"""
		if not self.friends:
			self.friends = self.vk.getFriends()
		logger.debug("User: sending init presence (friends %s) (jid %s)" % (("exists" if self.friends else "empty"), self.source))
		for uid, value in self.friends.iteritems():
			if value["online"]:
				sendPresence(self.source, vk2xmpp(uid), None, value["name"], caps=True)
		sendPresence(self.source, TransportID, None, IDENTIFIER["name"], caps=True)

	def sendOutPresence(self, destination, reason=None):
		"""
		Sends out presence (unavailable) to destination and set reason if exists
		Parameters:
			destination: to whom send the stanzas
			reason: offline status message
		"""
		logger.debug("User: sending out presence to %s" % self.source)
		for uid in self.friends.keys() + [TransportID]:
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
			with Database(DatabaseFile, Semaphore) as db:
				db("update users set rosterSet=? where jid=?",
					(self.rosterSet, self.source))

	def sendMessages(self, init=False):
		"""
		Sends messages from vk to xmpp and call message01 handlers
		Paramteres:
			init: needed to know if function called at init (add time or not)
		Plugins notice (msg01):
			If plugin returs None then message will not be sent by transport's core, it shall be sent by plugin itself
			Otherwise, if plugin returns string, it will be send by transport's core
		"""
		with self.__sync:
			date = 0
			messages = self.vk.getMessages(20, self.lastMsgID)
			if not messages or not messages[0]:
				return None
			messages = sorted(messages[1:], sortMsg)
			for message in messages:
				if message["out"]:
					continue
				Stats["msgin"] += 1
				fromjid = vk2xmpp(message["uid"])
				body = uHTML(message["body"])
				iter = Handlers["msg01"].__iter__()
				for func in iter:
					try:
						result = func(self, message)
					except Exception:
						result = None
						crashLog("handle.%s" % func.__name__)
					if result is None:
						for func in iter:
							apply(func, (self, message))
						break
					else:
						body += result
				else:
					if init:
						date = message["date"]
					sendMessage(Component, self.source, fromjid, escape("", body), date)
			if messages:
				self.lastMsgID = messages[-1]["mid"]
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.source))
		if not self.vk.userID:
			self.vk.getUserID()

	def processPollResult(self, opener):
		"""
		Processes poll result
		Retur codes:
			0 mean need to reinit poll (add user to poll buffer)
			1 mean all is fine (request again)
			-1 mean do nothing
		"""
		try:
			data = opener.read()
		except (httplib.BadStatusLine, socket.error):
			return 1

		if self.vk.engine.captcha:
			opener.close()
			return -1

		if not data:
			logger.error("longpoll: no data. Will request again")
			return 1
		try:
			data = json.loads(data)
		except Exception:
			return 1

		if "failed" in data:
			logger.debug("longpoll: failed. Searching for new server")
			return 0

		self.vk.pollConfig["ts"] = data["ts"]
		for evt in data.get("updates", ()):
			typ = evt.pop(0)
			if typ == 4:  # new message
				runThread(self.sendMessages)
			elif typ == 8: # user has joined
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
		if cTime - self.last_udate > 360:
			if self.settings.keep_onlne:
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

## TODO: rename to retry
	def tryAgain(self):
		"""
		Tries to execute self.initialize() again and connect() if needed
		Usually needed after captcha challenge is done
		"""
		logger.debug("calling reauth for user %s" % self.source)
		if not self.vk.online:
			self.connect()
		self.initialize(True)


class Poll:
	"""
	Class used to handle longpoll
	"""
	__poll = {}
	__buff = set()
	__lock = threading._allocate_lock()

	@classmethod
	def __add(cls, user):
		"""
		Issues readable socket to use it in select()
		Adds user in buffer on error occurred
		Adds user in self.__poll if no errors
		"""
		try:
			opener = user.vk.makePoll()
		except Exception as e:
			logger.error("longpoll: failed to make poll (jid: %s)" % user.source)
			cls.__addToBuff(user)
		else:
			cls.__poll[opener.sock] = (user, opener)

	@classmethod
	def __addToBuff(cls, user):
		"""
		Adds user to list of "bad" users
		The list is mostly contain users whose poll request was failed for some reasons
		"""
		cls.__buff.add(user)
		logger.debug("longpoll: adding user to watcher (jid: %s)" % user.source)
		runThread(cls.__initPoll, (user,), cls.__initPoll.__name__)

	@classmethod
	def add(cls, some_user):
		"""
		Adds the User class object to poll
		"""
		with cls.__lock:
			if some_user in cls.__buff:
				return None
			for sock, (user, opener) in cls.__poll.iteritems():
				if some_user == user:
					break
			else:
				cls.__add(some_user)

	@classmethod
	def remove(cls, some_user):
		"""
		Removes the User class object from poll
		"""
		with cls.__lock:
			if some_user in cls.__buff:
				return cls.__buff.remove(some_user)
			for sock, (user, opener) in cls.__poll.iteritems():
				if some_user == user:
					del cls.__poll[sock]
					opener.close()
					break

	clear = staticmethod(__poll.clear)

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
		while True:
			socks = cls.__poll.keys()
			if not socks:
				time.sleep(0.02)
				continue
			try:
				ready, error = select.select(socks, [], socks, 2)[::2]
			except (select.error, socket.error):
				continue

			for sock in error:
				with cls.__lock:
					try:
						cls.__add(cls.__poll.pop(sock)[0])
					except KeyError:
						continue
			for sock in ready:
				with cls.__lock:
					try:
						user, opener = cls.__poll.pop(sock)
					except KeyError:
						continue
					user = Transport.get(user.source)
					if not user:
						continue
					result = execute(user.processPollResult, (opener,))
					if result == -1:
						continue
					elif result:
						cls.__add(user)
					else:
						cls.__addToBuff(user)


def sendPresence(destination, source, pType=None, nick=None, reason=None, caps=None):
	"""
	Sends presence to destination from source
	Parameters:
		destination: to whom send the presence
		source: from who send the presence
		pType: a presence type
		nick: needed to add <nick> tag to stanza
		reason: needed to set status message
		caps: needed to know if need to add caps into stanza
	"""
	presence = xmpp.Presence(destination, pType, frm=source, status=reason)
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
		typ: xmpp chatstates (XEP-0085)
	"""
	msg = xmpp.Message(destination, body, "chat", frm=source)
	msg.setTag(typ, namespace=xmpp.NS_CHATSTATES)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	sender(cl, msg)


def sender(cl, stanza):
	"""
	Send stanza. Write crashlog on error
	"""
	try:
		cl.send(stanza)
	except Exception:
		crashLog("sender")


## TODO: make it as extension
def watcherMsg(text):
	"""
	Send message to jids in watchers list
	"""
	for jid in WatcherList:
		sendMessage(Component, jid, TransportID, text)


def updateCron():
	"""
	Calls functions for update friends and typing users list
	"""
	while True:
		for user in Transport.values():
			cTime = time.time()
			user.updateTypingUsers(cTime)
			user.updateFriends(cTime)
		time.sleep(2)


def calcStats():
	"""
	Returns count(*) from users database
	"""
	countTotal = 0
	countOnline = len(Transport)
	with Database(DatabaseFile, Semaphore) as db:
		db("select count(*) from users")
		countTotal = db.fetchone()[0]
	return [countTotal, countOnline]


def removeUser(user, roster=False, semph=Semaphore): ## todo: maybe call all the functions in format verbSentence?
	"""
	Removes user from database
	Parameters:
		user: User class object or jid without resource
		roster: remove vk contacts from user's roster (only if User class object was in first param)
		semph: use semaphore if needed
	"""
	source = user
	if isinstance(user, User):
		source = user.source
	logger.debug("User: removing user from db (jid: %s)" % source)
	with Database(DatabaseFile, semph) as db:
		db("delete from users where jid=?", (source,))
		db.commit()

	if source in Transport:
		user = Transport[source]
		user.exists = False
		friends = getattr(user, "friends", {})
		if roster and friends:
			logger.debug("User: removing myself from roster (jid: %s)" % source)
			for id in friends.keys():
				jid = vk2xmpp(id)
				sendPresence(source, jid, "unsubscribe")
				sendPresence(source, jid, "unsubscribed")
			
		elif roster:
			sendPresence(source, TransportID, "unsubscribe")
			sendPresence(source, TransportID, "unsubscribed")
			user.settings.exterminate()
			executeHandlers("evt03", (user,))
		Poll.remove(user)
		vk = getattr(user, "vk", user)
		vk.online = False
		del Transport[source]
		


def getPid():
	"""
	Getting new PID and kills previous PID
	by signals 15 and then 9
	"""
	nowPid = os.getpid()
	if os.path.exists(pidFile):
		oldPid = rFile(pidFile)
		if oldPid:
			Print("#-# Killing old transport instance: ", False)
			oldPid = int(oldPid)
			if nowPid != oldPid:
				try:
					os.kill(oldPid, 15)
					time.sleep(3)
					os.kill(oldPid, 9)
				except OSError:
					pass
				Print("%d killed.\n" % oldPid, False)
	wFile(pidFile, str(nowPid))


def loadExtensions(dir):
	"""
	Read and exec files located in dir
	"""
	for file in os.listdir(dir):
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


def loadModules(reload_=False):
	"""
	Loading modules from list made by getModulesList()
	Parameter "reload_" is needed to reload the modules
	"""
	modules = getModulesList()
	for name in modules:
		try:
			module = __import__(name, globals(), locals())
			if reload_:
				reload(module)
			if hasattr(module, "load"):
				module.load()
		except Exception:
			crashLog("loadmodules")


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
	with Database(DatabaseFile) as db:
		users = db("select jid from users").fetchall()
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
	loadModules()


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
	Handles disconnects
	And write crashlog if crash parameter is equals True
	"""
	if crash:
		crashLog("main.disconnect")
	try:
		Component.disconnect()
	except AttributeError:
		pass
	executeHandlers("evt02")
	Print("Reconnecting...")
	os.execl(sys.executable, sys.executable, sys.argv[0])
## until get it fixed
##	while not connect():
##		time.sleep(1)
##		disconnectHandler(crash)
##	else:
##		loadModules(True)


def makeMeKnown():
	"""
	That's such a weird function just makes post request
	to the vk4xmpp monitor which is located on http://xmppserv.ru/xmpp-monitor
	"""
	if WhiteList:
		WhiteList.append("anon.xmppserv.ru")
	if TransportID.split(".")[1] != "localhost":
		RIP = api.RequestProcessor()
		RIP.post("http://xmppserv.ru/xmpp-monitor/hosts.php", {"add": TransportID})
		Print("#! Information about this transport has been successfully published.")


def exit(signal=None, frame=None):
	"""
	Just stops the transport and sends unavailable presence
	"""
	status = "Shutting down by %s" % ("SIGTERM" if signal == 15 else "SIGINT")
	Print("#! %s" % status, False)
	for user in Transport.itervalues():
		user.sendOutPresence(user.source, status)
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
	main()
	while True:
		try:
			Component.iter(6)
		except Exception:
			logger.critical("disconnected")
			crashLog("component.iter")
			disconnectHandler(True)
