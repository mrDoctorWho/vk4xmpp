#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v3.0
# © simpleApps, 2013 — 2015.
# Program published under the MIT license.

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"
__license__ = "MIT"
__version__ = "3.0"

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

try:
	import ujson as json
except ImportError:
	import json

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

# Now we can import our own modules
import xmpp
from itypes import Database
from stext import setVars, _
from defaults import *
from printer import *
from webtools import *

Transport = {}
Semaphore = threading.Semaphore()

# command line arguments
argParser = ArgumentParser()
argParser.add_argument("-c", "--config",
	help="set the general config file destination", default="Config.txt")
argParser.add_argument("-d", "--daemon",
	help="run in daemon mode (no auto-restart)", action="store_true")
args = argParser.parse_args()
Daemon = args.daemon
Config = args.config

startTime = int(time.time())

execfile(Config)
Print("#-# Config loaded successfully.")

# logger
logger = logging.getLogger("vk4xmpp")
logger.setLevel(LOG_LEVEL)
loggerHandler = logging.FileHandler(logFile)
formatter = logging.Formatter("%(asctime)s %(levelname)s:"
	"%(name)s: %(message)s", "%d.%m.%Y %H:%M:%S")
loggerHandler.setFormatter(formatter)
logger.addHandler(loggerHandler)

# now we can import the last modules
from writer import *
from longpoll import *
from settings import *
import vkapi as api
import utils

# Compatibility with old config files
if not ADMIN_JIDS and evalJID:
	ADMIN_JIDS.append(evalJID)

# Setting variables
# DefLang for language id, root for the translations directory
setVars(DefLang, root)

if THREAD_STACK_SIZE:
	threading.stack_size(THREAD_STACK_SIZE)
del formatter, loggerHandler

if os.name == "posix":
	OS = "{0} {2:.16} [{4}]".format(*os.uname())
else:
	import platform
	OS = "Windows {0}".format(*platform.win32_ver())

Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)

# See extensions/.example.py for more information about handlers
Handlers = {"msg01": [], "msg02": [],
			"msg03": [], "evt01": [],
			"evt02": [], "evt03": [],
			"evt04": [], "evt05": [],
			"evt06": [], "evt07": [],
			"prs01": [], "prs02": [],
			"evt08": [], "evt09": []}

Stats = {"msgin": 0,  # from vk
		"msgout": 0,  # to vk
		"method": 0}


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
		runDatabaseQuery("create table users "
			"(jid text, username text, token text, "
				"lastMsgID integer, rosterSet bool)", set=True, semph=None)
	return True


def executeHandlers(type, list=()):
	"""
	Executes all handlers by type with list as list of args
	"""
	handlers = Handlers[type]
	for handler in handlers:
		utils.execute(handler, list)


def registerHandler(type, func):
	"""
	Registers handlers and remove if the same is already exists
	"""
	logger.info("main: add \"%s\" to handle type %s", func.func_name, type)
	for handler in Handlers[type]:
		if handler.func_name == func.func_name:
			Handlers[type].remove(handler)
	Handlers[type].append(func)


def getGatewayRev():
	"""
	Gets gateway revision using git or custom revision number
	"""
	number, hash = 304, 0
	shell = os.popen("git describe --always &"
		"& git log --pretty=format:''").readlines()
	if shell:
		number, hash = len(shell), shell[0]
	return "#%s-%s" % (number, hash)


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


REVISION = getGatewayRev()

# Escape xmpp non-allowed chars
badChars = [x for x in xrange(32) if x not in (9, 10, 13)] + [57003, 65535]
escape = re.compile("|".join(unichr(x) for x in badChars),
	re.IGNORECASE | re.UNICODE | re.DOTALL).sub

sortMsg = lambda first, second: first.get("mid", 0) - second.get("mid", 0)
require = lambda name: os.path.exists("extensions/%s.py" % name)
isdef = lambda var: var in globals()
findUserInDB = lambda source: runDatabaseQuery("select * from users where jid=?", (source,), many=False)

class VK(object):
	"""
	A base class for VK
	Contain functions which directly work with VK
	"""
	def __init__(self, token=None, source=None):
		self.token = token
		self.source = source
		self.pollConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.pollServer = ""
		self.pollInitialzed = False
		self.online = False
		self.userID = 0
		self.lists = []
		self.friends_fields = set(["screen_name"])
		self.cache = {}
		logger.debug("VK initialized (jid: %s)", source)

	getToken = lambda self: self.engine.token

	def checkToken(self):
		"""
		Checks the api token
		"""
		try:
			int(self.engine.method("isAppUser"))
		except (api.VkApiError, TypeError, AttributeError):
			return False
		return True

	def auth(self, username=None, password=None):
		logger.debug("VK going to authenticate (jid: %s)", self.source)
		self.engine = api.APIBinding(self.token, DEBUG_API, self.source)
		if not self.checkToken():
			raise api.TokenError("The token is invalid (jid: %s, token: %s)" % (self.source, self.token))
		self.online = True
		return True

	def initPoll(self):
		"""
		Initializes longpoll
		Returns False if error occurred
		"""
		self.pollInitialzed = False
		logger.debug("longpoll: requesting server address (jid: %s)", self.source)
		try:
			response = self.method("messages.getLongPollServer")
		except Exception:
			return False
		if not response:
			logger.warning("longpoll: no response!")
			return False
		self.pollServer = "http://%s" % response.pop("server")
		self.pollConfig.update(response)
		logger.debug("longpoll: server: %s (jid: %s)",
			self.pollServer, self.source)
		self.pollInitialzed = True
		return True

	def makePoll(self):
		"""
		Raises api.LongPollError if poll not yet initialized (self.pollInitialzed)
		Else returns socket object connected to poll server
		"""
		if not self.pollInitialzed:
			raise api.LongPollError("The Poll wasn't initialized yet")
		opener = api.AsyncHTTPRequest.getOpener(self.pollServer, self.pollConfig)
		if not opener:
			raise api.LongPollError("Poll request failed")
		return opener

	def method(self, method, args=None, force=False):
		"""
		This is a duplicate function of self.engine.method
		Needed to handle errors properly exactly in __main__
		Parameters:
			method: obviously VK API method
			args: method aruments
			nodecode: decode flag (make json.loads or not)
			force: says that method will be executed even the captcha and not online
		See library/vkapi.py for more information about exceptions
		Returns method execution result
		"""
		args = args or {}
		result = {}
		Stats["method"] += 1
		if not self.engine.captcha and (self.online or force):
			try:
				result = self.engine.method(method, args)
			except (api.InternalServerError, api.AccessDenied) as e:
				if force:
					raise

			except api.CaptchaNeeded as e:
				executeHandlers("evt04", (self, self.engine.captcha["img"]))
				self.online = False

			except api.NetworkNotFound as e:
				self.online = False

			except api.NotAllowed as e:
				if self.engine.lastMethod[0] == "messages.send":
					sendMessage(Component, self.source,
						vk2xmpp(args.get("user_id", TransportID)),
						_("You're not allowed to perform this action."))

			except api.VkApiError as e:
				# There are several types of VkApiError
				# But the user defenitely must be removed.
				# The question is: how?
				# Are they should be completely exterminated or just removed?
				roster = False
				m = e.message
				# Probably should be done in vkapi.py by status codes
				if m == "User authorization failed: user revoke access for this token.":
					roster = True
				elif m == "User authorization failed: invalid access_token.":
					sendMessage(Component, self.source, TransportID,
						m + " Please, register again")
				utils.runThread(removeUser, (self.source, roster))
				logger.error("VK: apiError %s (jid: %s)", m, self.source)
				self.online = False
			else:
				return result
			logger.error("VK: error %s occurred while executing"
				" method(%s) (%s) (jid: %s)",
				e.__class__.__name__, method, e.message, self.source)
			return result

	@utils.threaded
	def disconnect(self):
		"""
		Stops all user handlers and removes them from Poll
		"""
		self.online = False
		logger.debug("VK: user %s has left", self.source)
		executeHandlers("evt06", (self,))
		self.method("account.setOffline")

	def getFriends(self, fields=None):
		"""
		Executes friends.get and formats it in key-value style
		Example: {1: {"name": "Pavel Durov", "online": False}
		Parameter fields is needed to receive advanced fields
		Which will be added in the result values
		"""
		fields = fields or self.friends_fields
		raw = self.method("friends.get", {"fields": str.join(chr(44), fields)}) or ()
		friends = {}
		for friend in raw:
			uid = friend["uid"]
			online = friend["online"]
			name = escape("", str.join(chr(32), (friend["first_name"],
				friend["last_name"])))
			friends[uid] = {"name": name, "online": online, "lists": friend.get("lists")}
			for key in fields:
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
		Gets user id
		"""
		if not self.userID:
			self.userID = self.method("execute.getUserID")
		return self.userID

	def getLists(self):
		if not self.lists:
			self.lists = self.method("friends.getLists")
		return self.lists

	def getUserData(self, uid, fields=None):
		"""
		Gets user data. Such as name, photo, etc
		If the user exists in friends list,
		And if no advanced fields issued will return friends[uid]
		Otherwise will request method users.get
		Default fields are ["screen_name"]
		"""
		if not fields:
			user = Transport.get(self.source)
			if user and uid in user.friends:
				return user.friends[uid]
			if uid in self.cache:
				return self.cache[uid]
			fields = ["screen_name"]
		data = self.method("users.get",
			{"fields": str.join(chr(44), fields), "user_ids": uid}) or {}
		if data:
			data = data.pop()
			data["name"] = escape("", str.join(chr(32),
				(data.pop("first_name"), data.pop("last_name"))))
		else:
			data = {"name": "None"}
			for key in fields:
				data[key] = "None"
		self.cache[uid] = data
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
		try:
			result = self.method("messages.send", values)
		except api.VkApiError:
			crashLog("messages.send")
			result = False
		return result


class User(object):
	"""
	Main class.
	Makes a “bridge” between VK & XMPP.
	"""
	def __init__(self, source=""):
		self.friends = {}
		self.typing = {}
		self.source = source

		self.lastMsgID = 0
		self.rosterSet = None
		self.username = None

		self.resources = set([])
		self.settings = Settings(source)
		self.last_udate = time.time()
		self.sync = threading._allocate_lock()
		logger.debug("User initialized (jid: %s)", self.source)

	def connect(self, username=None, password=None, token=None):
		"""
		Calls VK.auth() and calls captchaChallenge on captcha
		Updates db if auth() is done
		"""
		logger.debug("User connecting (jid: %s)", self.source)
		exists = False
		# check if user registered
		user = findUserInDB(self.source)
		if user:
			exists = True
			_, _, token, self.lastMsgID, self.rosterSet = user
			logger.debug("User was found in the database. (jid: %s)", self.source)

		if not (token or password):
			logger.warning("User wasn't found in the database and no token or password was given!")
			raise RuntimeError("Either no token or password was given!")

		if password:
			pwd = api.PasswordLogin(username, password).login()
			token = pwd.confirm()

		self.vk = vk = VK(token, self.source)
		try:
			auth = vk.auth()
		except api.CaptchaNeeded:
			self.sendSubPresence()
			logger.error("User: running captcha challenge (jid: %s)", self.source)
			executeHandlers("evt04", (self, vk.engine.captcha["img"]))
			return True
		else:
			logger.debug("User seems to be authenticated (jid: %s)", self.source)
			if exists:
				# Anyways, it won't hurt anyone
				runDatabaseQuery("update users set token=? where jid=?",
					(vk.getToken(), self.source), True)
			else:
				runDatabaseQuery("insert into users (jid, token, lastMsgID, rosterSet) values (?,?,?,?)",
					(self.source, vk.getToken(),
						self.lastMsgID, self.rosterSet), True)
			executeHandlers("evt07", (self,))
			self.friends = vk.getFriends()
		return vk.online

	def markRosterSet(self):
		self.rosterSet = True
		runDatabaseQuery("update users set rosterSet=? where jid=?",
			(self.rosterSet, self.source), True)

	def initialize(self, force=False, send=True, resource=None):
		"""
		Initializes user after self.connect() is done:
			1. Receives friends list and set 'em to self.friends
			2. If #1 is done and roster is not yet set (self.rosterSet)
				then sends a subscription presence
			3. Calls sendInitPresnece() if parameter send is True
			4. Adds resource if resource parameter exists
		Parameters:
			force: force sending subscription presence
			send: needed to know if need to send init presence or not
			resource: add resource in self.resources to prevent unneeded stanza sending
		"""
		logger.debug("User: beginning user initialization (jid: %s)", self.source)
		Transport[self.source] = self
		if not self.friends:
			self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("User: sending subscription presence with force:%s (jid: %s)",
				force, self.source)
			import rostermanager
			rostermanager.Roster.checkRosterx(self, resource)
		if send:
			self.sendInitPresence()
		if resource:
			self.resources.add(resource)
		utils.runThread(self.vk.getUserID)
		self.sendMessages(True)
		Poll.add(self)
		utils.runThread(executeHandlers, ("evt05", (self,)))

	def sendInitPresence(self):
		"""
		Sends init presence (available) to the user from all them online friends
		"""
		if not self.settings.i_am_ghost and not self.vk.engine.captcha:
			if not self.friends:
				self.friends = self.vk.getFriends()
			logger.debug("User: sending init presence (friends count: %s) (jid %s)",
				len(self.friends), self.source)
			key = "name"
			if self.settings.use_nicknames:
				key = "screen_name"
			for uid, value in self.friends.iteritems():
				if value["online"]:
					sendPresence(self.source, vk2xmpp(uid), None,
						value.get(key, "Unknown"), caps=True)
			sendPresence(self.source, TransportID, None, IDENTIFIER["name"], caps=True)

	def sendOutPresence(self, destination, reason=None, all=False):
		"""
		Sends out presence (unavailable) to destination. Defines a reason, if set.
		Parameters:
			destination: to whom send the stanzas
			reason: offline status message
			all: send an unavailable from all friends or only the ones who's online
		"""
		logger.debug("User: sending out presence to %s", self.source)
		friends = self.friends.keys()
		if not all and friends:
			friends = filter(lambda key: self.friends[key]["online"], friends)

		for uid in friends + [TransportID]:
			sendPresence(destination, vk2xmpp(uid), "unavailable", reason=reason)

	def sendSubPresence(self, dist=None):
		"""
		Sends subscribe presence to self.source
		Parameteres:
			dist: friends list
		"""
		dist = dist or {}
		for uid, value in dist.iteritems():
			sendPresence(self.source, vk2xmpp(uid), "subscribe", value["name"])
		sendPresence(self.source, TransportID, "subscribe", IDENTIFIER["name"])
		if dist:
			self.markRosterSet()

	def sendMessages(self, init=False, messages=None):
		"""
		Sends messages from vk to xmpp and call message01 handlers
		Paramteres:
			init: needed to know if function called at init (add time or not)
		Plugins notice (msg01):
			If plugin returs None then message will not be sent by transport's core,
				it shall be sent by plugin itself
			Otherwise, if plugin returns string,
				the message will be sent by transport's core
		"""
		with self.sync:
			date = 0
			if not messages:
				messages = self.vk.getMessages(200, self.lastMsgID)
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
								utils.execute(func, (self, message))
							break
						else:
							body += result
					else:
						if self.settings.force_vk_date or init:
							date = message["date"]
						sendMessage(Component, self.source, fromjid, escape("", body), date)
		if messages:
			self.lastMsgID = messages[-1]["mid"]
			runDatabaseQuery("update users set lastMsgID=? where jid=?",
				(self.lastMsgID, self.source), True)


	def processPollResult(self, opener):
		"""
		Processes poll result
		Retur codes:
			0: need to reinit poll (add user to the poll buffer)
			1: all is fine (request again)
			-1: just continue iteration, ignoring this user
				(user won't be added for the next iteration)
		"""
		if DEBUG_POLL:
			logger.debug("longpoll: processing result (jid: %s)", self.source)

		if self.vk.engine.captcha:
			return -1

		data = None
		try:
			data = opener.read()
		except (httplib.BadStatusLine, socket.error, socket.timeout) as e:
			logger.warning("longpoll: got error `%s` (jid: %s)", e.__class__.__name__,
				self.source)
			return 0
		try:
			data = json.loads(data)
		except ValueError:
			return 1

		if not data:
			logger.error("longpoll: no data. Gonna request again (jid: %s)",
				self.source)
			return 1

		if "failed" in data:
			logger.debug("longpoll: failed. Searching for a new server (jid: %s)",
				self.source)
			return 0

		self.vk.pollConfig["ts"] = data["ts"]

		for evt in data.get("updates", ()):
			typ = evt.pop(0)

			if DEBUG_POLL:
				logger.debug("longpoll: got updates, processing event %s with arguments %s (jid: %s)", typ, str(evt), self.source)

			if typ == 4:  # new message
				if len(evt) == 7:
					message = None
					mid, flags, uid, date, subject, body, attachments = evt
					out = flags & 2 == 2
					chat = flags & 16 == 16
					if not attachments and not chat and not out:
						message = [1, {"out": 0, "uid": uid, "mid": mid, "date": date, "body": body}]
					utils.runThread(self.sendMessages, (None, message), "sendMessages-%s" % self.source)
				else:
					logger.warning("longpoll: incorrect events number while trying to process arguments %s (jid: %s)", str(evt), self.source)

			elif typ == 8:  # user has joined
				if not self.settings.i_am_ghost:
					uid = abs(evt[0])
					key = "name"
					if self.settings.use_nicknames:
						key = "screen_name"
					sendPresence(self.source, vk2xmpp(uid),
						nick=self.vk.getUserData(uid)[key], caps=True)

			elif typ == 9:  # user has left
				uid = abs(evt[0])
				sendPresence(self.source, vk2xmpp(uid), "unavailable")

			elif typ == 61:  # user is typing
				if evt[0] not in self.typing:
					sendMessage(Component, self.source, vk2xmpp(evt[0]), typ="composing")
				self.typing[evt[0]] = time.time()
		return 1

	def updateTypingUsers(self, cTime):
		"""
		Sends "paused" message event to stop user from composing a message
		Sends only if last typing activity in VK was more than 10 seconds ago
		"""
		for user, last in self.typing.items():
			if cTime - last > 7:
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
					logger.error("updateFriends: no friends received (jid: %s).",
						self.source)
					return None

				for uid in friends:
					if uid not in self.friends:
						self.sendSubPresence({uid: friends[uid]})
				for uid in self.friends:
					if uid not in friends:
						sendPresence(self.source, vk2xmpp(uid), "unsubscribe")
				self.friends = friends

	def reauth(self):
		"""
		Tries to execute self.initialize() again and connect() if needed
		Usually needed after captcha challenge is done
		"""
		logger.debug("calling reauth for user %s", self.source)
		if not self.vk.online:
			self.connect()
		self.initialize(True)

	def captchaChallenge(self, key):
		engine = self.vk.engine
		engine.captcha["key"] = key
		logger.debug("retrying for user %s", self.source)
		if engine.retry():
			self.reauth()


def sendPresence(destination, source, pType=None, nick=None,
	reason=None, caps=None, show=None):
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
	presence = xmpp.Presence(destination, pType,
		frm=source, status=reason, show=show)
	if nick:
		presence.setTag("nick", namespace=xmpp.NS_NICK)
		presence.setTagData("nick", nick)
	if caps:
		presence.setTag("c",
			{"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": REVISION},
			xmpp.NS_CAPS)
	executeHandlers("prs02", (presence, destination, source))
	sender(Component, presence)


def sendMessage(cl, destination, source, body=None, timestamp=0, typ="active"):
	"""
	Sends message to destination from source
	Parameters:
		cl: xmpp.Client object
		destination: to whom send the message
		source: from who send the message
		body: message body
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
		roster: remove vk contacts from user's roster
			(only if User class object was in the first param)
	"""
	if isinstance(user, (str, unicode)):  # unicode is default, but... who knows
		source = user
	elif user:
		source = user.source
	else:
		raise ValueError("No user or source was given")
	user = Transport.get(source)
	if notify:
		# Would russians understand the joke?
		sendMessage(Component, source, TransportID,
			_("Your record was EXTERMINATED from the database."
				" Let us know if you feel exploited."), -1)
	logger.debug("User: removing user from db (jid: %s)" % source)
	runDatabaseQuery("delete from users where jid=?", (source,), True)
	logger.debug("User: deleted (jid: %s)", source)
	if source in Transport:
		del Transport[source]
	if roster and user:
		friends = user.friends
		user.exists = False  # Make the Daleks happy
		if friends:
			logger.debug("User: removing myself from roster (jid: %s)", source)
			for id in friends.keys() + [TransportID]:
				jid = vk2xmpp(id)
				sendPresence(source, jid, "unsubscribe")
				sendPresence(source, jid, "unsubscribed")
			user.settings.exterminate()
			executeHandlers("evt03", (user,))
		user.vk.online = False


def getPid():
	"""
	Gets a new PID and kills the previous PID
	by signals 15 and 9
	"""
	pid = os.getpid()
	if os.path.exists(pidFile):
		old = rFile(pidFile)
		if old:
			Print("#-# Killing the previous instance: ", False)
			old = int(old)
			if pid != old:
				try:
					os.kill(old, 15)
					time.sleep(3)
					os.kill(old, 9)
				except OSError as e:
					if e.errno != 3:
						Print("%d %s.\n" % (old, e.message), False)
				else:
					Print("%d killed.\n" % old, False)
	wFile(pidFile, str(pid))


def loadExtensions(dir):
	"""
	Loads extensions
	"""
	for file in os.listdir(dir):
		if not file.startswith(".") and file.endswith(".py"):
			execfile("%s/%s" % (dir, file), globals())


def connect():
	"""
	Just makes a connection to the jabber server
	Returns False if failed, True if completed
	"""
	global Component
	Component = xmpp.Component(Host, debug=DEBUG_XMPPPY)
	Print("\n#-# Connecting: ", False)
	if not Component.connect((Server, Port)):
		Print("failed.\n", False)
		return False
	else:
		Print("ok.\n", False)
		Print("#-# Auth: ", False)
		if not Component.auth(TransportID, Password):
			Print("failed (%s/%s)!\n"
				% (Component.lastErr, Component.lastErrCode), True)
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
	Print("\n#-# Transport %s initialized well." % TransportID)


def runMainActions():
	"""
	Running the main actions to make the transport work
	"""
	if allowBePublic:
		makeMeKnown()
	for num, event in enumerate(Handlers["evt01"]):
		utils.runThread(event, (), "extension-%d" % num)
	utils.runThread(Poll.process, (), "longPoll")
	utils.runThread(updateCron, (), "updateCron")
	import modulemanager
	Manager = modulemanager.ModuleManager
	Manager.load(Manager.list())


def main():
	"""
	Running main actions to start the transport
	Such as pid, db, connect
	"""
	if RUN_AS:
		import pwd
		uid = pwd.getpwnam(RUN_AS).pw_uid
		logger.warning("switching to user %s:%s", RUN_AS, uid)
		os.setuid(uid)

	getPid()
	initDatabase(DatabaseFile)
	if connect():
		initializeUsers()
		runMainActions()
		logger.info("transport initialized at %s", TransportID)
	else:
		disconnectHandler(False)


def disconnectHandler(crash=True):
	"""
	Handles disconnect
	And writes a crashlog if crash parameter equals True
	"""
	executeHandlers("evt02")
	if crash:
		crashLog("main.disconnect")
	logger.critical("disconnecting from the server")
	try:
		Component.disconnect()
	except AttributeError:
		pass
	global ALIVE
	ALIVE = False
	if not Daemon:
		logger.warning("the trasnport is going to be restarted!")
		Print("Restarting...")
		time.sleep(5)
		os.execl(sys.executable, sys.executable, *sys.argv)
	else:
		logger.info("the transport is shutting down!")
		sys.exit(-1)


def makeMeKnown():
	"""
	That's such a weird function just makes a post request
	to the vk4xmpp monitor which is located on http://xmppserv.ru/xmpp-monitor
	You can check out the source of The VK4XMPP Monitor utilty
		over there: https://github.com/aawray/xmpp-monitor
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
