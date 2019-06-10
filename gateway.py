#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v3.6
# © simpleApps, 2013 — 2018.
# Program published under the MIT license.

# Disclamer: be aware that this program's code may hurt your eyes or feelings.
# You were warned.

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"
__license__ = "MIT"
__version__ = "3.6"

import hashlib
import logging
import os
import re
import signal
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
reload(sys)
sys.setdefaultencoding("utf-8")

# Now we can import our own modules
import xmpp
from itypes import Database
from stext import setVars, _
from defaults import *
from printer import *
from webtools import *

Users = {}
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


# not really required to be none, but the debugger requires them to be defined
# and, come on, this is much better, isn't it?
DatabaseFile = None
TransportID = None
Host = None
Server = None
Port = None
Password = None
LAST_REPORT = None


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
from settings import *
import vkapi as api
import utils

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

PYTHON_VERSION = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)

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


MAX_MESSAGES_PER_REQUEST = 20


def runDatabaseQuery(query, args=(), set=False, many=True):
	"""
	Executes the given sql to the database
	Args:
		query: the sql query to execute
		args: the query argument
		set: whether to commit after the execution
		many: whether to return more than one result
	Returns:
		The query execution result
	"""
	semph = None
	if threading.currentThread() != "MainThread":
		semph = Semaphore
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
	Args:
		filename: the database filename
	"""
	runDatabaseQuery("create table if not exists users"
		"(jid text, username text, token text, "
			"lastMsgID integer, rosterSet bool)", set=True)
	return True


def executeHandlers(type, list=()):
	"""
	Executes all handlers with the given type
	Args:
		type: the handlers type
		list: the arguments to pass to handlers
	"""
	handlers = Handlers[type]
	for handler in handlers:
		utils.execute(handler, list)


def registerHandler(type, func):
	"""
	Register a handler
	Args:
		type: the handler type
		func: the function to register
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
	number, hash = 420, 0
	shell = os.popen("git describe --always &"
		"& git log --pretty=format:''").readlines()
	if shell:
		number, hash = len(shell), shell[0]
	return "#%s-%s" % (number, hash)


def vk2xmpp(id):
	"""
	Converts a numeric VK ID to a Jabber ID and vice versa
	Args:
		id: a Jabber or VK id
	Returns:
		id@TransportID if parameter id is a number
		id if parameter "id" is id@TransportID
		TransportID if the given id is equal to TransportID
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

sortMsg = lambda first, second: first.get("id", 0) - second.get("id", 0)
require = lambda name: os.path.exists("extensions/%s.py" % name)
isdef = lambda var: var in globals()
findUserInDB = lambda source: runDatabaseQuery("select * from users where jid=?", (source,), many=False)


class Transport(object):
	"""
	A dummy class to store settings (ATM)
	"""
	def __init__(self):
		self.settings = Settings(TransportID, user=False)


class VK(object):
	"""
	Contains methods to handle the VK stuff
	"""
	def __init__(self, token=None, source=None):
		self.token = token
		self.source = source
		self.pollConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.pollServer = ""
		self.pollInitialized = False
		self.engine = None
		self.online = False
		self.userID = 0
		self.methods = 0
		self.lists = []
		self.friends_fields = {"screen_name"}
		self.engine = None
		self.cache = {}
		self.permissions = 0
		self.timezone = 0
		logger.debug("VK initialized (jid: %s)", source)

	def __str__(self):
		return ("user id: %s; timezone: %s; online: %s; token: %s" %
			(self.userID, self.timezone, self.online, self.token))

	def init(self):
		self.getUserPreferences()
		self.getPermissions()

	getToken = lambda self: self.engine.token

	def checkToken(self):
		"""
		Checks the token
		"""
		try:
			int(self.engine.method("isAppUser"))
		except (api.VkApiError, TypeError, AttributeError):
			logger.error("unable to check user's token, error: %s (user: %s)",
				traceback.format_exc(), self.source)
			return False
		return True

	def auth(self):
		"""
		Initializes the APIBinding object
		Returns:
			True if everything went fine
		"""
		logger.debug("VK going to authenticate (jid: %s)", self.source)
		self.engine = api.APIBinding(self.token, DEBUG_API, self.source)
		if not self.checkToken():
			raise api.TokenError("The token is invalid (jid: %s, token: %s)"
				% (self.source, self.token))
		self.online = True
		return True

	def initPoll(self):
		"""
		Initializes longpoll
		Returns:
			False: if any error occurred
			True: if everything went just fine
		"""
		self.pollInitialized = False
		logger.debug("longpoll: requesting server address (jid: %s)", self.source)
		try:
			response = self.method("messages.getLongPollServer", {"use_ssl": 1, "need_pts": 0})
		except Exception:
			response = None
		if not response:
			logger.warning("longpoll: no response!")
			return False
		self.pollServer = "https://%s" % response.pop("server")
		self.pollConfig.update(response)
		logger.debug("longpoll: server: %s (jid: %s)",
			self.pollServer, self.source)
		self.pollInitialized = True
		return True

	# TODO: move it the hell outta here
	# wtf it's still doing here?
	def makePoll(self):
		"""
		Returns:
			socket connected to the poll server
		Raises api.LongPollError if poll not yet initialized (self.pollInitialized)
		"""
		if not self.pollInitialized:
			raise api.LongPollError("The Poll wasn't initialized yet")
		return api.AsyncHTTPRequest.getOpener(self.pollServer, self.pollConfig)

	def method(self, method, args=None, force=False, notoken=False):
		"""
		This is a duplicate function of self.engine.method
		Needed to handle errors properly exactly in __main__
		Args:
			method: a VK API method
			args: method arguments
			force: whether to force execution (ignore self.online and captcha)
			notoken: whether to cut the token from the request
		Returns:
			The method execution result
		See library/vkapi.py for more information about exceptions
		"""
		args = args or {}
		result = {}
		self.methods += 1
		Stats["method"] += 1
		if not self.engine.captcha and (self.online or force):
			try:
				result = self.engine.method(method, args, notoken=notoken)
			except (api.InternalServerError, api.AccessDenied) as e:
				if force:
					raise

			except api.CaptchaNeeded as e:
				executeHandlers("evt04", (self.source, self.engine.captcha))
				self.online = False

			except api.NetworkNotFound as e:
				self.online = False

			except api.NotAllowed as e:
				if self.engine.lastMethod[0] == "messages.send":
					sendMessage(self.source,
						vk2xmpp(args.get("user_id", TransportID)),
						_("You're not allowed to perform this action."))

			except api.VkApiError as e:
				# There are several types of VkApiError
				# But the user definitely must be removed.
				# The question is: how?
				# Should we completely exterminate them or just remove?
				roster = False
				m = e.message
				# TODO: Make new exceptions for each of the conditions below
				if m == "User authorization failed: user revoke access for this token.":
					roster = True
				elif m == "User authorization failed: invalid access_token.":
					sendMessage(self.source, TransportID,
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
		Stops all user handlers and removes the user from Poll
		"""
		self.online = False
		logger.debug("VK: user %s has left", self.source)
		executeHandlers("evt06", (self,))
		self.setOffline()

	def setOffline(self):
		"""
		Sets the user status to offline
		"""
		self.method("account.setOffline")

	def setOnline(self):
		"""
		Sets the user status to online
		"""
		self.method("account.setOnline")

	@staticmethod
	def formatName(data):
		"""
		Extracts a string name from a user object
		Args:
			user: a VK user object which is a dict with the first_name and last_name keys
		Returns:
			User's first and last name
		"""
		name = escape("", "%(first_name)s %(last_name)s" % data)
		del data["first_name"]
		del data["last_name"]
		return name


	def getFriends(self, fields=None):
		"""
		Executes the friends.get method and formats it in the key-value style
		Example:
			{1: {"name": "Pavel Durov", "online": False}
		Args:
			fields: a list of advanced fields to receive
		Which will be added in the result values
		"""
		fields = fields or self.friends_fields
		raw = self.method("friends.get", {"fields": str.join(",", fields)}) or {}
		raw = raw.get("items", {})
		friends = {}
		for friend in raw:
			uid = friend["id"]
			online = friend["online"]
			name = self.formatName(friend)
			friends[uid] = {"name": name, "online": online, "lists": friend.get("lists")}
			for key in fields:
				friends[uid][key] = friend.get(key)
		return friends

	@staticmethod
	def getPeerIds(conversations, source=None):
		"""
		Returns a list of peer ids that exist in the given conversations
		Args:
			conversations: list of Conversations objects
		Returns:
			A list of peer id strings
		"""
		peers = []
		if not conversations:
			logger.warning("no conversations for (jid: %s)", source)
			return peers
		for conversation in conversations:
			if isinstance(conversation, dict):
				innerConversation = conversation.get("conversation")
				if innerConversation:
					peers.append(str(innerConversation["peer"]["id"]))
		return peers

	def getMessagesBulk(self, peers, count=20, mid=0):
		"""
		Receives messages for all the conversations' peers
		25 is the maximum number of conversations we can receive in a single request
		The sky is the limit!
		Args:
			peers: a list of peer ids (strings)
			messages: a list of messages (used internally)
			count: the number of messages to receive
			uid: the last message id
		Returns:
			A list of VK Message objects
		"""
		step = 20
		messages = []
		if peers:
			cursor = 0
			for i in xrange(step, len(peers) + step, step):
				tempPeers = peers[cursor:i]
				users = ",".join(tempPeers)
				response = self.method("execute.getMessagesBulk",
					{"users": users,
					"start_message_id": mid,
					"count": count})
				if response:
					for item in response:
						item = item.get("items")
						if not item:
							continue
						messages.extend(item)
				else:
					# not sure if that's okay
					# VK is totally unpredictable now
					logger.warning("No response for execute.getMessagesBulk!"
						+" Users: %s, mid: %s (jid: %s)", users, mid, self.source)
				cursor += step
		return messages

	def getMessages(self, count=20, mid=0, uid=0, filter_="all"):
		"""
		Gets the last messages list
		Args:
			count: the number of messages to receive
			mid: the last message id
		Returns:
			A list of VK Message objects
		"""
		if uid == 0:
			conversations = self.method("messages.getConversations", {"count": count, "filter": filter_})
			conversations = conversations.get("items")
		else:
			conversations = [{"conversation": {"peer": {"id": uid}}}]
		peers = VK.getPeerIds(conversations, self.source)
		return self.getMessagesBulk(peers, count=count, mid=mid)

	# TODO: put this in the DB
	def getUserPreferences(self):
		"""
		Receives the user's id and timezone
		Returns:
			The current user id
		"""
		if not self.userID or not self.timezone:
			data = self.method("users.get", {"fields": "timezone"})
			if data:
				data = data.pop()
				self.timezone = data.get("timezone")
				self.userID = data.get("id")
		return (self.userID, self.timezone)

	def getPermissions(self):
		"""
		Update the app permissions
		Returns:
			The current permission mask
		"""
		if not self.permissions:
			self.permissions = self.method("account.getAppPermissions")
		return self.permissions

	def getLists(self):
		"""
		Receive the list of the user friends' groups
		Returns:
			a list of user friends groups
		"""
		if not self.lists:
			self.lists = self.method("friends.getLists")
		return self.lists

	@utils.cache
	def getGroupData(self, gid, fields=None):
		"""
		Gets group data (only name so far)
		Args:
			gid: the group id
			fields: a list of advanced fields to receive
		Returns:
			The group information
		"""
		fields = fields or ["name"]
		data = self.method("groups.getById", {"group_id": abs(gid), "fields": str.join(",", fields)})
		if data:
			data = data[0]
		return data

	@utils.cache
	@api.repeat(3, dict, RuntimeError)
	def getUserData(self, uid, fields=None):
		"""
		Gets user data. Such as name, photo, etc
		Args:
			uid: the user id (list or str)
			fields: a list of advanced fields to receive
		Returns:
			The user information
		"""
		if not fields:
			user = Users.get(self.source)
			if user and uid in user.friends:
				return user.friends[uid]
			fields = ["screen_name"]
		if isinstance(uid, (list, tuple)):
			uid = str.join(",", uid)
		data = self.method("users.get", {"user_ids": uid, "fields": str.join(",", fields)})
		if data:
			data = data[0]
			data["name"] = self.formatName(data)
			return data
		raise RuntimeError("Unable to get the user's name")

	def getName(self, id_):
		if id_ > 0:
			name = self.getUserData(id_).get("name", "Unknown user (id: %s)" % id_)
		else:
			name = self.getGroupData(id_).get("name", "Unknown group (id: %s)" % id_)
		return name

	def sendMessage(self, body, id, mType="user_id", more={}):
		"""
		Sends message to a VK user (or a chat)
		Args:
			body: the message body
			id: the user id
			mType: the message type (user_id is for dialogs, chat_id is for chats)
			more: for advanced fields such as attachments
		Returns:
			The result of sending the message
		"""
		Stats["msgout"] += 1
		values = {mType: id, "message": body, "type": 0}
		values.update(more)
		try:
			result = self.method("messages.send", values)
		except api.VkApiError:
			crashLog("messages.send")  # this actually never happens
			result = False
		return result


class User(object):
	"""
	Handles XMPP and VK stuff
	"""
	def __init__(self, source=""):
		self.friends = {}
		self.typing = {}
		self.msgCacheByUser = {}  # the cache of associations vk mid: xmpp mid
		self.lastMsgByUser = {}  # the cache of last messages sent to user (user id: msg id)
		self.source = source  # TODO: rename to jid

		self.lastMsgID = 0
		self.rosterSet = None
		self.username = None

		self.resources = set([])
		self.settings = Settings(source)
		self.last_udate = time.time()
		self.sync = threading.Lock()
		logger.debug("User initialized (jid: %s)", self.source)

	def sendMessage(self, body, id, mType="user_id", more={}, mid=0):
		result = self.vk.sendMessage(body, id, mType, more)
		if mid:
			self.msgCacheByUser[int(id)] = {"xmpp": mid, "vk": result}
		return result

	def connect(self, username=None, password=None, token=None):
		"""
		Initializes a VK() object and tries to make an authorization if no token provided
		Args:
			username: the user's phone number or e-mail for password authentication
			password: the user's account password
			token: the user's token
		Returns:
			True if everything went fine
		"""
		logger.debug("User connecting (jid: %s)", self.source)
		exists = False
		user = findUserInDB(self.source)  # check if user registered
		if user:
			exists = True
			logger.debug("User was found in the database... (jid: %s)", self.source)
			if not token:
				logger.debug("... but no token was given. Using the one from the database (jid: %s)", self.source)
				_, _, token, self.lastMsgID, self.rosterSet = user

		if not (token or password):
			logger.warning("User wasn't found in the database and no token or password was given!")
			raise RuntimeError("Either no token or password was given!")

		if password:
			logger.debug("Going to authenticate via password (jid: %s)", self.source)
			pwd = api.PasswordLogin(username, password).login()
			token = pwd.confirm()

		self.vk = vk = VK(token, self.source)
		try:
			vk.auth()
		except api.CaptchaNeeded:
			self.sendSubPresence()
			logger.error("User: running captcha challenge (jid: %s)", self.source)
			executeHandlers("evt04", (self.source, self.vk.engine.captcha))
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
			vk.init()
			# TODO: move friends to VK() and check last update timeout?
			# Currently, every time we request friends a new object is being created
			# As we request it very frequently, it might be better to move
			# getFriends() to vk.init() and every time check if the list is due for the update
			self.friends = vk.getFriends()
		return vk.online

	def markRosterSet(self):
		"""
		Marks the user's roster as already set, so the gateway won't need to send it again
		"""
		self.rosterSet = True
		runDatabaseQuery("update users set rosterSet=? where jid=?",
			(self.rosterSet, self.source), True)

	def initialize(self, force=False, send=True, resource=None, first=False):
		"""
		Initializes user after the connection has been completed
		Args:
			force: force sending subscription presence
			send: whether to send the init presence
			resource: add resource in self.resources to prevent unneeded stanza sending
			first: whether to initialize the user for the first time (during registration)
		"""
		logger.debug("User: beginning user initialization (jid: %s)", self.source)
		Users[self.source] = self
		if not self.friends:
			self.friends = self.vk.getFriends()
		if force or not self.rosterSet:
			logger.debug("User: sending subscription presence with force:%s (jid: %s)",
				force, self.source)
			import rostermanager
			rostermanager.Roster.checkRosterx(self, resource)
		if send:
			self.sendInitPresence()
		if resource:
			self.resources.add(resource)
		utils.runThread(self.vk.getUserPreferences)
		if first:
			self.sendMessages(True, filter_="unread")
		else:
			self.sendMessages(True)
		Poll.add(self)
		utils.runThread(executeHandlers, ("evt05", (self,)))

	def sendInitPresence(self):
		"""
		Sends available presence to the user from all online friends
		"""
		if not self.vk.engine.captcha:
			if not self.friends:
				self.friends = self.vk.getFriends()
			logger.debug("User: sending init presence (friends count: %s) (jid %s)",
				len(self.friends), self.source)
			for uid, value in self.friends.iteritems():
				if value["online"]:
					sendPresence(self.source, vk2xmpp(uid), hash=USER_CAPS_HASH)
			sendPresence(self.source, TransportID, hash=TRANSPORT_CAPS_HASH)

	def sendOutPresence(self, destination, reason=None, all=False):
		"""
		Sends the unavailable presence to destination. Defines a reason if set.
		Args:
			destination: to whom send the stanzas
			reason: the reason why going offline
			all: send the unavailable presence from all the friends or only the ones who's online
		"""
		logger.debug("User: sending out presence to %s", self.source)
		friends = self.friends.keys()
		if not all and friends:
			friends = filter(lambda key: self.friends[key]["online"], friends)

		for uid in friends + [TransportID]:
			sendPresence(destination, vk2xmpp(uid), "unavailable", reason=reason)

	def sendSubPresence(self, dist=None):
		"""
		Sends the subscribe presence to self.source
		Args:
			dist: friends list
		"""
		dist = dist or {}
		for uid, value in dist.iteritems():
			sendPresence(self.source, vk2xmpp(uid), "subscribe", value["name"])
		sendPresence(self.source, TransportID, "subscribe", IDENTIFIER["name"])
		# TODO: Only mark roster set when we received authorized/subscribed event from the user
		if dist:
			self.markRosterSet()

	def sendMessages(self, init=False, messages=None, mid=0, uid=0, filter_="all"):
		"""
		Sends messages from vk to xmpp and call message01 handlers
		Args:
			init: needed to know if function called at init (add time or not)
		Plugins notice (msg01):
			If plugin returns None then message will not be sent by transport's core,
				it shall be sent by plugin itself
			Otherwise, if plugin returns string,
				the message will be sent by transport's core
		"""
		with self.sync:
			date = 0
			if not messages:
				messages = self.vk.getMessages(MAX_MESSAGES_PER_REQUEST, mid or self.lastMsgID, uid, filter_)
			if not messages:
				return None
			messages = sorted(messages, sortMsg)
			for message in messages:
				# check if message wasn't sent by our user
				if not message["out"]:
					Stats["msgin"] += 1
					frm = message["user_id"]
					mid = message["id"]
					if frm in self.typing:
						del self.typing[frm]
					fromjid = vk2xmpp(frm)
					body = message["body"]
					body = uhtml(body)
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
						self.lastMsgByUser[frm] = mid
						sendMessage(self.source, fromjid, escape("", body), date, mid=mid)
		if messages:
			newLastMsgID = messages[-1]["id"]
			if self.lastMsgID < newLastMsgID:
				self.lastMsgID = newLastMsgID
				runDatabaseQuery("update users set lastMsgID=? where jid=?",
					(newLastMsgID, self.source), True)

	def updateTypingUsers(self, cTime):
		"""
		Sends "paused" message event to stop user from composing a message
		Sends only if last typing activity in VK was more than 7 seconds ago
		Args:
			cTime: current time
		"""
		with self.sync:
			for user, last in self.typing.items():
				if cTime - last > 7:
					del self.typing[user]
					sendMessage(self.source, vk2xmpp(user), typ="paused")

	def updateFriends(self, cTime):
		"""
		Updates friends list.
		Compares the current friends list to the new list
		Takes a corresponding action if any difference found
		"""
		if (cTime - self.last_udate) > 300 and not self.vk.engine.captcha:
			if self.settings.keep_online:
				self.vk.setOnline()
			else:
				self.vk.setOffline()
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
		logger.debug("calling reauth for user (jid: %s)", self.source)
		if not self.vk.online:
			self.connect()
		self.initialize()

	def captchaChallenge(self, key):
		"""
		Sets the captcha key and sends it to VK
		Args:
			key: the captcha text
		"""
		engine = self.vk.engine
		engine.captcha["key"] = key
		logger.debug("retrying for user (jid: %s)", self.source)
		if engine.retry():
			self.reauth()


def sendPresence(destination, source, pType=None, nick=None,
	reason=None, hash=None, show=None):
	"""
	Sends a presence to destination from source
	Args:
		destination: whom send the presence to
		source: who send the presence from
		pType: the presence type
		nick: add <nick> tag
		reason: set status message
		hash: add caps hash
		show: add status show
	"""
	presence = xmpp.Presence(destination, pType,
		frm=source, status=reason, show=show)
	if nick:
		presence.setTag("nick", namespace=xmpp.NS_NICK)
		presence.setTagData("nick", nick)
	if hash:
		presence.setTag("c", {"node": CAPS_NODE, "ver": hash, "hash": "sha-1"}, xmpp.NS_CAPS)
	executeHandlers("prs02", (presence, destination, source))
	sender(Component, presence)


def sendMessage(destination, source, body=None, timestamp=0, typ="active", mtype="chat", mid=0):
	"""
	Sends message to destination from source
	Args:
		destination: to whom send the message
		source: from who send the message
		body: message body
		timestamp: message timestamp (XEP-0091)
		typ: xmpp chatstates type (XEP-0085)
		mtype: the message type
	"""
	msg = xmpp.Message(destination, body, mtype, frm=source)
	msg.setTag(typ, namespace=xmpp.NS_CHATSTATES)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	if mid:
		msg.setID(mid)
	executeHandlers("msg03", (msg, destination, source))
	sender(Component, msg)


def sendChatMarker(destination, source, mid, typ="displayed"):
	msg = xmpp.Message(destination, typ="chat",frm=source)
	msg.setTag(typ, {"id": mid}, xmpp.NS_CHAT_MARKERS)
	sender(Component, msg)


def report(message):
	"""
	Critical error reporter
	"""
	global LAST_REPORT
	if Transport.settings.send_reports and message != LAST_REPORT:
		LAST_REPORT = message
		message = "Critical failure:\n%s" % message
		for admin in ADMIN_JIDS:
			sendMessage(admin, TransportID, message)


def computeCapsHash(features=TransportFeatures):
	"""
	Computes a hash which will be placed in all presence stanzas
	Args:
		features: the list of features to compute hash from
	"""
	result = "%(category)s/%(type)s//%(name)s<" % IDENTIFIER
	features = sorted(features)
	result += str.join("<", features) + "<"
	return hashlib.sha1(result).digest().encode("base64")


# TODO: rename me
def sender(cl, stanza, cb=None, args={}):
	"""
	Sends stanza. Writes a crashlog on error
	Parameters:
		cl: the xmpp.Client object
		stanza: the xmpp.Node object
		cb: callback function
		args: callback function arguments
	"""
	if cb:
		cl.SendAndCallForResponse(stanza, cb, args)
	else:
		try:
			cl.send(stanza)
		except Exception:
			disconnectHandler()


def updateCron():
	"""
	Calls the functions to update friends and typing users list
	"""
	while ALIVE:
		for user in Users.values():
			cTime = time.time()
			user.updateTypingUsers(cTime)
			user.updateFriends(cTime)
		time.sleep(2)

def calcStats():
	"""
	Returns count(*) from users database
	"""
	countOnline = len(Users)
	countTotal = runDatabaseQuery("select count(*) from users", many=False)[0]
	return [countTotal, countOnline]


def removeUser(user, roster=False, notify=True):
	"""
	Removes user from the database
	Args:
		user: User class object or jid without resource
		roster: remove vk contacts from user's roster
			(only if User class object was in the first param)
		notify: whether to let the user know that they're being exterminated
	"""
	if isinstance(user, (str, unicode)):  # unicode is the default, but... who knows
		source = user
	elif user:
		source = user.source
	else:
		raise RuntimeError("Invalid user argument: %s" % str(user))
	if notify:
		sendMessage(source, TransportID,
			_("Your record was EXTERMINATED from the database."
				" Let us know if you feel exploited."), -1)
	logger.debug("User: removing user from db (jid: %s)" % source)
	runDatabaseQuery("delete from users where jid=?", (source,), True)
	logger.debug("User: deleted (jid: %s)", source)

	user = Users.get(source)
	if user:
		del Users[source]
		if roster:
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


def checkPID():
	"""
	Gets a new PID and kills the previous PID
	by signal 15 and then by 9
	"""
	pid = os.getpid()
	if os.path.exists(pidFile):
		old = rFile(pidFile)
		if old:
			Print("#-# Killing the previous instance: ", False)
			old = int(old)
			if pid != old:
				try:
					os.kill(old, signal.SIGTERM)
					time.sleep(3)
					os.kill(old, signal.SIGKILL)
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
	Makes a connection to the jabber server
	Returns:
		False if failed
		True if completed
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
	users = runDatabaseQuery("select jid from users")
	for user in users:
		Print(".", False)
		sendPresence(user[0], TransportID, "probe")
	Print("\n#-# Yay! Component %s initialized well." % TransportID)


def runMainActions():
	"""
	Runs the actions for the gateway to work well
	Initializes extensions, longpoll and modules
	Computes required hashes
	"""
	for num, event in enumerate(Handlers["evt01"]):
		utils.runThread(event, name=("extension-%d" % num))
	utils.runThread(Poll.process, name="longPoll")
	utils.runThread(updateCron)
	import modulemanager
	Manager = modulemanager.ModuleManager
	Manager.load(Manager.list())
	global USER_CAPS_HASH, TRANSPORT_CAPS_HASH
	USER_CAPS_HASH = computeCapsHash(UserFeatures)
	TRANSPORT_CAPS_HASH = computeCapsHash(TransportFeatures)


def main():
	"""
	Runs the init actions
	Checks if any other copy running and kills it
	"""
	logger.info("gateway started")
	if RUN_AS:
		import pwd
		uid = pwd.getpwnam(RUN_AS).pw_uid
		logger.warning("switching to user %s:%s", RUN_AS, uid)
		os.setuid(uid)
	checkPID()
	initDatabase(DatabaseFile)
	if connect():
		initializeUsers()
		runMainActions()
		logger.info("gateway initialized at %s", TransportID)
	else:
		disconnectHandler(False)


def disconnectHandler(crash=True):
	"""
	Handles disconnect
	Writes a crash log if the crash parameter is True
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
		logger.warning("the gateway is going to be restarted!")
		Print("Restarting...")
		time.sleep(5)
		os.execl(sys.executable, sys.executable, *sys.argv)
	else:
		logger.info("the gateway is shutting down!")
		os._exit(-1)


def exit(sig=None, frame=None):
	"""
	Just stops the gateway and sends unavailable presence
	"""
	status = "Shutting down by %s" % ("SIGTERM" if sig == signal.SIGTERM else "SIGINT")
	Print("#! %s" % status, False)
	for user in Users.itervalues():
		user.sendOutPresence(user.source, status, all=True)
		Print("." * len(user.friends), False)
	Print("\n")
	executeHandlers("evt02")
	try:
		os.remove(pidFile)
	except OSError:
		pass
	os._exit(0)


def loop():
	"""
	The main loop which is used to call the stanza parser
	"""
	while ALIVE:
		try:
			Component.iter(1)
		except Exception:
			logger.critical("disconnected")
			crashLog("component.iter")
			disconnectHandler(True)


if __name__ == "__main__":
	signal.signal(signal.SIGTERM, exit)
	signal.signal(signal.SIGINT, exit)
	loadExtensions("extensions")
	Transport = Transport()
	from longpoll import *
	try:
		main()
		Poll.init()
	except Exception:
		crashLog("main")
		os._exit(1)
	loop()

# This is the end!
