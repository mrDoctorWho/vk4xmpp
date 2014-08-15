#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v2.25
# © simpleApps, 2013 — 2014.
# Program published under MIT license.

import gc
import json
import logging
import os
import re
import select
import socket
import signal
import sys
import threading
import time

core = getattr(sys.modules["__main__"], "__file__", None)
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
SLICE_STEP = 8
USER_LIMIT = 0
DEBUG_XMPPPY = False
THREAD_STACK_SIZE = 0
MAXIMUM_FORWARD_DEPTH = 10
STANZA_SEND_INTERVAL = 0.03125

pidFile = "pidFile.txt"
logFile = "vk4xmpp.log"
crashDir = "crash"

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
## 01 - start
## 02 - shutdown
## 03 - user deletion
## 04 - captcha
Handlers = {"msg01": [], "msg02": [],
			"evt01": [], "evt02": [],
			"evt03": [], "evt04": []}

Stats = {"msgin": 0, ## from vk
		 "msgout": 0, ## to vk
		 "method": 0}

DESC = _("© simpleApps, 2013 — 2014."
	"\nYou can support developing of this project"
	" via donation by:\nYandex.Money: 410012169830956"
	"\nWebMoney: Z405564701378 | R330257574689.")

def initDatabase(filename):
	if not os.path.exists(filename):
		with Database(filename) as db:
			db("create table users (jid text, username text, token text, lastMsgID integer, rosterSet bool)")
			db.commit()
	return True

def execute(handler, list=()):
	try:
		result = handler(*list)
	except SystemExit:
		result = 1
	except Exception:
		result = -1
		crashLog(handler.func_name)
	return result

def apply(instance, args=()):
	try:
		code = instance(*args)
	except Exception:
		code = None
	return code

## TODO: execute threaded handlers
def registerHandler(type, func):
	logger.info("main: adding \"%s\" handling type %s" % (func.func_name, type))
	for handler in Handlers[type]:
		if handler.func_name == func.func_name:
			Handlers[type].remove(handler)
	Handlers[type].append(func)

def executeHandlers(type, list=()):
	for handler in Handlers[type]:
		execute(handler, list)

def runThread(func, args=(), name=None):
	thr = threading.Thread(target=execute, args=(func, args), name=name or func.func_name)
	try:
		thr.start()
	except threading.ThreadError:
		crashlog("runThread.%s" % name)

def getGatewayRev():
	revNumber, rev = 181, 0
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)

def vk2xmpp(id):
	if not isNumber(id) and "@" in id:
		id = id.split("@")[0]
		if isNumber(id):
			id = int(id)
	elif id != TransportID:
		id = u"%s@%s" % (id, TransportID)
	return id


Revision = getGatewayRev()
badChars = [x for x in xrange(32) if x not in (9, 10, 13)] + [57003, 65535]
escape = re.compile("|".join(unichr(x) for x in badChars), re.IGNORECASE | re.UNICODE | re.DOTALL).sub
sortMsg = lambda msgOne, msgTwo: msgOne.get("mid", 0) - msgTwo.get("mid", 0)
require = lambda name: os.path.exists("extensions/%s.py" % name)
isNumber = lambda obj: (not apply(int, (obj,)) is None)


class VK(object):

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
		try:
			int(self.method("isAppUser", force=True))
		except (api.VkApiError, TypeError):
			return False
		return True

	def auth(self, token=None):
		logger.debug("VK.auth %s token" % ("with" if token else "without"))
		self.engine = api.APIBinding(self.number, self.password, token=token)
		try:
			self.checkData()
		except api.AuthError as e:
			logger.error("VK.auth failed with error %s" % e.message)
			return False
		except Exception:
			crashLog("VK.auth")
			return False
		logger.debug("VK.auth completed")
		self.online = True
		runThread(self.initLongPoll, ())
		return True

	def initLongPoll(self):
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
		if not self.pollInitialzed:
			raise api.LongPollError()
		return self.engine.RIP.getOpener(self.pollServer, self.pollConfig)

	def method(self, method, args=None, nodecode=False, force=False):
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
		if self.engine.captcha:
			executeHandlers("evt04", (self,))
			Poll.remove(Transport[self.source]) ## Do not foget to add user into poll again after the captcha challenge is done 

	def disconnect(self):
		logger.debug("VK: user %s has left" % self.source)
		Poll.remove(Transport[self.source])
		self.online = False
		self.method("account.setOffline", nodecode=True) ## Maybe this one should be started in separate thread to do not let VK freeze main thread

	def getFriends(self, fields=None):
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
		values = {"out": 0, "filters": 1, "count": count}
		if mid:
			del values["count"], values["filters"]
			values["last_message_id"] = mid
		return self.method("messages.get", values)

	def getUserID(self):
		self.userID = self.method("execute.getUserID")
		if self.userID:
			jidToID[self.userID] = self.source
		return self.userID

	def getUserData(self, uid, fields=None):
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

	def __init__(self, data=(), source=""):
		self.password = None
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

	def connect(self):
		logger.debug("User: connecting (jid: %s)" % self.source)
		self.auth = False
		## TODO: Check the code below
		try:
			self.auth = self.vk.auth(self.token)
		except api.CaptchaNeeded:
			self.sendSubPresence()
			self.vk.captchaChallenge()
			return True
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


	def initialize(self, force=False, send=True, resource=None):
		runThread(makePhotoHash, (self,), "hasher-%s" % self.source)
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

	def sendInitPresence(self):
		if not self.friends:
			self.friends = self.vk.getFriends()
		logger.debug("User: sending init presence (friends %s) (jid %s)" % (("exists" if self.friends else "empty"), self.source))
		for uid, value in self.friends.iteritems():
			if value["online"]:
				sendPresence(self.source, vk2xmpp(uid), None, value["name"], caps=True, hash=self.hashes.get(uid))
		sendPresence(self.source, TransportID, None, IDENTIFIER["name"], caps=True, hash=self.hashes.get(TransportID))

	def sendOutPresence(self, target, reason=None):
		logger.debug("User: sending out presence to %s" % self.source)
		for uid in self.friends.keys() + [TransportID]:
			sendPresence(target, vk2xmpp(uid), "unavailable", reason=reason)

	def sendSubPresence(self, dist=None):
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
		try:
			data = opener.read()
		except socket.error:
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
				makePhotoHash(self, [uid])
				sendPresence(self.source, vk2xmpp(uid), nick=self.vk.getUserData(uid)["name"], caps=True, hash=self.hashes.get(uid))
			elif typ == 9: # user has left
				uid = abs(evt[0])
				sendPresence(self.source, vk2xmpp(uid), "unavailable")
			elif typ == 61: # user is typing
				if evt[0] not in self.typing:
					sendMessage(Component, self.source, vk2xmpp(evt[0]), typ="composing")
				self.typing[evt[0]] = time.time()
		return 1

	def updateTypingUsers(self, cTime):
		for user, last in self.typing.items():
			if cTime - last > 10:
				del self.typing[user]
				sendMessage(Component, self.source, vk2xmpp(user), typ="paused")

	def updateFriends(self, cTime):
		if cTime - self.last_udate > 360:
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
		logger.debug("calling reauth for user %s" % self.source)
		if not self.vk.online:
			self.connect()
		self.initialize(True)


class Poll:

	__poll = {}
	__buff = set()
	__lock = threading._allocate_lock()

	@classmethod
	def __add(cls, user):
		try:
			opener = user.vk.makePoll()
		except Exception as e:
			logger.error("longpoll: failed to make poll (jid: %s)" % user.source)
			cls.__addToBuff(user)
		else:
			cls.__poll[opener.sock] = (user, opener)

	@classmethod
	def __addToBuff(cls, user):
		cls.__buff.add(user)
		logger.debug("longpoll: adding user to watcher (jid: %s)" % user.source)
		runThread(cls.__initPoll, (user,), cls.__initPoll.__name__)

	@classmethod
	def add(cls, some_user):
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
		for x in xrange(10):
			if user.source not in Transport:
				logger.debug("longpoll: while we wasted our time, user has left (jid: %s)" % user.source)
				with cls.__lock:
					if user in cls.__buff:
						cls.__buff.remove(user)
				return None
			if Transport[user.source].vk.initLongPoll():
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


def sendPresence(target, source, pType=None, nick=None, reason=None, caps=None, hash=None):
	presence = xmpp.Presence(target, pType, frm=source, status=reason)
	if nick:
		presence.setTag("nick", namespace=xmpp.NS_NICK)
		presence.setTagData("nick", nick)
	if caps:
		presence.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": Revision}, xmpp.NS_CAPS)
	if hash:
		x = presence.setTag("x", namespace=xmpp.NS_VCARD_UPDATE)
		x.setTagData("photo", hash)
	sender(Component, presence)


def sendMessage(cl, destination, source, body=None, timestamp=0, typ="active"):
	msg = xmpp.Message(destination, body, "chat", frm=source)
	msg.setTag(typ, namespace=xmpp.NS_CHATSTATES)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	sender(cl, msg)


def sender(cl, stanza):
	try:
		cl.send(stanza)
	except Exception:
		crashLog("sender")


## TODO: make it as extension
def watcherMsg(text):
	for jid in WatcherList:
		sendMessage(Component, jid, TransportID, text)


def updateCron():
	while True:
		for user in Transport.values():
			cTime = time.time()
			user.updateTypingUsers(cTime)
			user.updateFriends(cTime)
		time.sleep(2)


def makePhotoHash(user, list=None):
	if not list:
		list = user.vk.method("friends.getOnline")
		user.hashes = {}
		photos = [{"uid": TransportID, "photo": URL_VCARD_NO_IMAGE}]
	else:
		photos = []

	list = ",".join((str(x) for x in list))
	data = user.vk.method("execute.getPhotos", {"users": list, "size": PhotoSize}) or []
	photos = photos + data

	for key in photos:
		user.hashes[key["uid"]] = sha1(utils.getLinkData(key["photo"], False)).hexdigest()


def removeUser(user, roster=False, semph=Semaphore): ## todo: maybe call all the functions in format verbSentence?
	logger.debug("User: removing user from db (jid: %s)" % user.source)
	with Database(DatabaseFile, semph) as db:
		db("delete from users where jid=?", (user.source,))
		db.commit()
	user.exists = False
	friends = getattr(user, "friends", {})
	if roster and friends:
		logger.debug("User: removing myself from roster (jid: %s)" % user.source)
		for id in friends.keys():
			jid = vk2xmpp(id)
			sendPresence(user.source, jid, "unsubscribe")
			sendPresence(user.source, jid, "unsubscribed")
		
	elif roster:
		sendPresence(user.source, TransportID, "unsubscribe")
		sendPresence(user.source, TransportID, "unsubscribed")
		executeHandlers("evt03", (user,))

	vk = getattr(user, "vk", user)
	if user.source in Transport:
		vk.online = False
		del Transport[user.source]
	Poll.remove(user)


def getPid():
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
	for file in os.listdir(dir):
		execfile("%s/%s" % (dir, file), globals())


def getModulesList():
	modules = []
	for file in os.listdir("modules"):
		modules.append(file[:-3])
	return modules


def loadModules(reload_=False):
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
	Print("#-# Initializing users", False)
	with Database(DatabaseFile) as db:
		users = db("select jid from users").fetchall()
		for user in users:
			Print(".", False)
			sender(Component, xmpp.Presence(user[0], "probe", frm=TransportID))
	Print("\n#-# Finished.")


def runMainActions():
	if allowBePublic:
		makeMeKnown()
	for num, event in enumerate(Handlers["evt01"]):
		runThread(event, (), "extension-%d" % num)
	runThread(Poll.process, (), "longPoll")
	runThread(updateCron, (), "updateCron")
	loadModules()


def main():
	getPid()
	initDatabase(DatabaseFile)
	if connect():
		initializeUsers()
		runMainActions()
	else:
		disconnectHandler(False)


def disconnectHandler(crash=True):
	if crash:
		crashLog("main.disconnect")
	try:
		Component.disconnect()
	except AttributeError:
		pass
	executeHandlers("evt02")
	Print("Reconnecting...")
	while not connect():
		time.sleep(1)
		disconnectHandler(crash)
	else:
		loadModules(True)


def makeMeKnown():
	if WhiteList:
		WhiteList.append("anon.xmppserv.ru")
	if TransportID.split(".")[1] != "localhost":
		RIP = api.RequestProcessor()
		RIP.post("http://xmppserv.ru/xmpp-monitor/hosts.php", {"add": TransportID})
		Print("#! Information about this transport has been successfully published.")


def exit(signal=None, frame=None):
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
		except xmpp.StreamError:
			pass
		except Exception:
			logger.critical("disconnected")
			crashLog("component.iter")
			disconnectHandler(True)
