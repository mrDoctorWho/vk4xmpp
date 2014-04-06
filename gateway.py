#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v2a1
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

from hashlib import sha1

core = getattr(sys.modules["__main__"], "__file__", None)
if core:
	core = os.path.abspath(core)
	root = os.path.dirname(core)
	if root:
		os.chdir(root)

sys.path.insert(0, "library")
reload(sys).setdefaultencoding("utf-8")

import vkapi as api
import xmpp

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

UserFeatures = [xmpp.NS_CHATSTATES]

IDentifier = {"type": "vk",
			"category": "gateway",
			"name": "VK4XMPP Transport"}

Semaphore = threading.Semaphore()

LOG_LEVEL = logging.DEBUG
SLICE_STEP = 8
USER_LIMIT = 0
DEBUG_XMPPPY = False
THREAD_STACK_SIZE = 0
MAXIMUM_FORWARD_DEPTH = 5

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

setVars(DefLang, root)


if THREAD_STACK_SIZE:
	threading.stack_size(THREAD_STACK_SIZE)

logger = logging.getLogger("vk4xmpp")
logger.setLevel(LOG_LEVEL)
loggerHandler = logging.FileHandler(logFile)
Formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s %(message)s",
				"[%d.%m.%Y %H:%M:%S]")
loggerHandler.setFormatter(Formatter)
logger.addHandler(loggerHandler)

def gatewayRev():
	revNumber, rev = 0.155, 0 # 0. means testing.
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)

OS = "{0} {2:.16} [{4}]".format(*os.uname())
Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)
Revision = gatewayRev()

Handlers = {"msg01": [], "msg02": [],
			"evt01": [], "evt02": []}

def initDatabase(filename):
	if not os.path.exists(filename):
		with Database(filename) as db:
			db("create table users (jid text, username text, token text, lastMsgID integer, rosterSet bool)")
			db.commit()
	return True

def executeFunction(handler, list = ()):
	try:
		handler(*list)
	except SystemExit:
		pass
	except Exception:
		crashLog(handler.func_name)

def startThr(thr, number = 0):
	if number > 2:
		raise RuntimeError("exit")
	try:
		thr.start()
	except threading.ThreadError:
		startThr(thr, (number + 1))

def threadRun(func, args = (), name = None):
	thr = threading.Thread(target = executeFunction, args = (func, args), name = name)
	try:
		thr.start()
	except threading.ThreadError:
		try:
			startThr(thr)
		except RuntimeError:
			thr.run()

badChars = [x for x in xrange(32) if x not in (9, 10, 13)] + [57003, 65535]
escape = re.compile("|".join(unichr(x) for x in badChars), re.IGNORECASE | re.UNICODE | re.DOTALL).sub
require = lambda name: os.path.exists("extensions/%s.py" % name)


def deleteUser(user, roster = False):
	logger.debug("User: deleting user %s from db." % user.source)
	with Database(DatabaseFile) as db:
		db("delete from users where jid=?", (user.source,))
		db.commit()
	user.existsInDB = False
	friends = getattr(user, "friends")
	if roster and friends:
		logger.debug("User: deleting me from %s roster" % user.source)
		for id in friends.keys():
			jid = vk2xmpp(id)
			sendPresence(user.source, jid, "unsubscribe")
			sendPresence(user.source, jid, "unsubscribed")
		
	elif roster:
		sendPresence(user.source, TransportID, "unsubscribe")
		sendPresence(user.source, TransportID, "unsubscribed")

	vk = getattr(user, "vk") or user
	if user.source in Transport:
		vk.Online = False
		del Transport[user.source]
	Poll.remove(user)

class VKLogin(object):

	def __init__(self, number, password = None, source = None):
		self.number = number
		self.password = password
		self.Online = False
		self.source = source
		self.longConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.longServer = ""
		self.longInitialized = False
		logger.debug("VKLogin.__init__ with number:%s from jid:%s" % (number, source))

	getToken = lambda self: self.engine.token

	def checkData(self):
		logger.debug("VKLogin: checking data for %s" % self.source)
		if not self.engine.token and self.password:
			logger.debug("VKLogin.checkData: trying to login via password")
			self.engine.loginByPassword()
			self.engine.confirmThisApp()
			if not self.checkToken():
				raise api.VkApiError("Incorrect phone or password")

		elif self.engine.token:
			logger.debug("VKLogin.checkData: trying to use token")
			if not self.checkToken():
				logger.error("VKLogin.checkData: token invalid: %s" % self.engine.token)
				raise api.TokenError("Token for user %s invalid: %s" % (self.source, self.engine.token))
		else:
			logger.error("VKLogin.checkData: no token and password for jid:%s" % self.source)
			raise api.TokenError("%s, Where are your token?" % self.source)

	def checkToken(self):
		try:
			int(self.method("isAppUser", force = True))
		except (api.VkApiError, TypeError):
			return False
		return True

	def auth(self, token = None):
		logger.debug("VKLogin.auth %s token" % ("with" if token else "without"))
		self.engine = api.APIBinding(self.number, self.password, token = token)
		try:
			self.checkData()
		except api.AuthError as e:
			logger.error("VKLogin.auth failed with error %s" % e.message)
			return False
		except api.CaptchaNeeded:
			raise
		except Exception:
			crashLog("VKLogin.auth")
			return False
		logger.debug("VKLogin.auth completed")
		self.Online = True
		self.initLongPoll() ## Check if it could be removed in future
		return True

	def initLongPoll(self):
		self.longInitialized = False ## Maybe we called re-init and failed somewhere
		logger.debug("longpoll: requesting server address for user: %s" % self.source)
		try:
			response = self.method("messages.getLongPollServer")
		except Exception:
			return False
		if not response:
			logger.error("longpoll: no response!")
			return False
		self.longServer = "http://%s" % response.pop("server") # hope it will be ok
		self.longConfig.update(response)
		logger.debug("longpoll: server: %s ts: %s" % (self.longServer, self.longConfig["ts"]))
		self.longInitialized = True
		return True

	def makePoll(self):
		if not self.longInitialized:
			raise api.LongPollError()
		return self.engine.RIP.getOpener(self.longServer, self.longConfig)

	def method(self, method, args = None, nodecode = False, force = False):
		args = args or {}
		result = {}
		if not self.engine.captcha and (self.Online or force):
			try:
				result = self.engine.method(method, args, nodecode)
			except api.CaptchaNeeded:
				logger.error("VKLogin: running captcha challenge for %s" % self.source)
				self.captchaChallenge()
			except api.NotAllowed:
				if self.engine.lastMethod[0] == "messages.send":
					msgSend(Component, self.source, _("You're not allowed to perform this action."), vk2xmpp(args.get("user_id", TransportID)))
			except api.VkApiError as e:
				if e.message == "User authorization failed: user revoke access for this token.":
					logger.critical("VKLogin: %s" % e.message)
					try:
						deleteUser(self, True)
					except KeyError:
						pass
				elif e.message == "User authorization failed: invalid access_token.":
					msgSend(Component, self.source, _(e.message + " Please, register again"), TransportID)
				self.Online = False
				logger.error("VKLogin: apiError %s for user %s" % (e.message, self.source))
			except api.NetworkNotFound:
				logger.critical("VKLogin: network unavailable. Is vk down?")
				self.Online = False
		return result

	def captchaChallenge(self):
		if self.engine.captcha:
			logger.debug("VKLogin: sending message with captcha to %s" % self.source)
			body = _("WARNING: VK sent captcha to you."
					 " Please, go to %s and enter text from image to chat."
					 " Example: !captcha my_captcha_key. Tnx") % self.engine.captcha["img"]
			msg = xmpp.Message(self.source, body, "chat", frm = TransportID)
			xTag = msg.setTag("x", {}, xmpp.NS_OOB)
			xTag.setTagData("url", self.engine.captcha["img"])
			cTag = msg.setTag("captcha", {}, xmpp.NS_CAPTCHA)
			imgData = vCardGetPhoto(self.engine.captcha["img"], False)
			if imgData:
				imgHash = sha1(imgData).hexdigest()
				imgEncoded = imgData.encode("base64")
				form = xmpp.DataForm("form")
				form.setField("FORM_TYPE", xmpp.NS_CAPTCHA, "hidden")
				form.setField("from", TransportID, "hidden")
				field = form.setField("ocr")
				field.setLabel(_("Enter shown text"))
				field.delAttr("type")
				field.setPayload([xmpp.Node("required"),
					xmpp.Node("media", {"xmlns": xmpp.NS_MEDIA},
						[xmpp.Node("uri", {"type": "image/jpg"},
							["cid:sha1+%s@bob.xmpp.org" % imgHash])])])
				cTag.addChild(node=form)
				obTag = msg.setTag("data", {"cid": "sha1+%s@bob.xmpp.org" % imgHash, "type": "image/jpg", "max-age": "0"}, xmpp.NS_URN_OOB)
				obTag.setData(imgEncoded)
			else:
				logger.critical("VKLogin: can't add captcha image to message url:%s" % self.engine.captcha["img"])
			Sender(Component, msg)
			Presence = xmpp.protocol.Presence(self.source, frm = TransportID)
			Presence.setStatus(body)
			Presence.setShow("xa")
			Sender(Component, Presence)
		else:
			logger.error("VKLogin: captchaChallenge called without captcha for user %s" % self.source)

	def disconnect(self):
		logger.debug("VKLogin: user %s has left" % self.source)
		self.method("account.setOffline")
		self.Online = False

	def getFriends(self, fields = None):
		fields = fields or ["screen_name"]
		friendsRaw = self.method("friends.get", {"fields": ",".join(fields)}) or () # friends.getOnline
		friendsDict = {}
		for friend in friendsRaw:
			uid = friend["uid"]
			name = escape("", u"%s %s" % (friend["first_name"], friend["last_name"]))
			try:
				friendsDict[uid] = {"name": name, "online": friend["online"]}
				for key in fields:
					if key != "screen_name":
						friendsDict[uid][key] = friend.get(key)
			except KeyError:
				continue
		return friendsDict

	def getMessages(self, count = 5, lastMsgID = 0):
		values = {"out": 0, "filters": 1, "count": count}
		if lastMsgID:
			del values["count"]
			values["last_message_id"] = lastMsgID
		return self.method("messages.get", values)


def sendPresence(target, source, pType = None, nick = None, reason = None, caps = None):
	Presence = xmpp.Presence(target, pType, frm = source, status = reason)
	if nick:
		Presence.setTag("nick", namespace = xmpp.NS_NICK)
		Presence.setTagData("nick", nick)
	if caps:
		Presence.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": Revision}, xmpp.NS_CAPS)
	Sender(Component, Presence)

class User(object):

	def __init__(self, data = (), source = ""):
		self.password = None
		if data:
			self.username, self.password = data
		self.friends = {}
		self.auth = None
		self.token = None
		self.lastMsgID = None
		self.rosterSet = None
		self.existsInDB = None
		self.last_udate = time.time()
		self.typing = {}
		self.source = source
		self.resources = []
		self.chatUsers = {}
		self.__sync = threading._allocate_lock()
		self.vk = VKLogin(self.username, self.password, self.source)
		logger.debug("initializing User for %s" % self.source)
		with Database(DatabaseFile, Semaphore) as db:
			db("select * from users where jid=?", (self.source,))
			desc = db.fetchone()
			if desc:
				if not self.token or not self.password:
					logger.debug("User: %s exists in db. Using it." % self.source)
					self.existsInDB = True
					self.source, self.username, self.token, self.lastMsgID, self.rosterSet = desc
				elif self.password or self.token: ## Warning: this may work wrong. If user exists in db we shouldn't delete him, we just should replace his token
					logger.debug("User: %s exists in db. Will be deleted." % self.source)
					threadRun(deleteUser(self))

	def __eq__(self, user):
		if isinstance(user, User):
			return user.source == self.source
		return self.source == user

	def msg(self, body, id, mType = "user_id", more = {}):
		try:
			values = {mType: id, "message": body, "type": 0}
			values.update(more)
			Message = self.vk.method("messages.send", values)
		except Exception:
			crashLog("messages.send")
			Message = None
		return Message

	def connect(self):
		logger.debug("User: connecting %s" % self.source)
		self.auth = False
		try:
			self.auth = self.vk.auth(self.token)
		except api.CaptchaNeeded:
			self.rosterSubscribe()
			self.vk.captchaChallenge()
			return True
		else:
			logger.debug("User: auth=%s for %s" % (self.auth, self.source))

		if self.auth and self.vk.getToken():
			logger.debug("User: updating db for %s because auth done " % self.source)
			if not self.existsInDB:
				with Database(DatabaseFile, Semaphore) as db:
					db("insert into users values (?,?,?,?,?)", (self.source, self.username,
						self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set token=? where jid=?", (self.vk.getToken(), self.source))

			self.getUserID()
			self.friends = self.vk.getFriends()
			self.vk.Online = True
		if not UseLastMessageID:
			self.lastMsgID = 0
		return self.vk.Online

	def getUserID(self):
		try:
			json = self.vk.method("users.get")
			self.UserID = json[0]["uid"]
		except (KeyError, TypeError):
			logger.error("User: could not recieve user id. JSON: %s" % str(json))
			self.UserID = 0

		if self.UserID:
			jidToID[self.UserID] = self.source
		return self.UserID

	def init(self, force = False, send = True):
		logger.debug("User: called init for user %s" % self.source)
		if not self.friends:
			self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("User: calling subscribe with force:%s for %s" % (force, self.source))
			self.rosterSubscribe(self.friends)
		if send: self.sendInitPresence()
		self.sendMessages(True)

## TODO: Move this function otside class

	def sendInitPresence(self):
		if not self.friends:
			self.friends = self.vk.getFriends()
		logger.debug("User: sending init presence to %s (friends %s)" %
					(self.source, "exists" if self.friends else "empty"))
		for uid, value in self.friends.iteritems():
			if value["online"]:
				sendPresence(self.source, vk2xmpp(uid), None, value["name"], caps = True)
		sendPresence(self.source, TransportID, None, IDentifier["name"], caps = True)

	def sendOutPresence(self, target, reason = None):
		logger.debug("User: sending out presence to %s" % self.source)
		for uid in self.friends.keys() + [TransportID]:
			sendPresence(target, vk2xmpp(uid), "unavailable", reason = reason)

	def rosterSubscribe(self, dist = None):
		dist = dist or {}
		for uid, value in dist.iteritems():
			sendPresence(self.source, vk2xmpp(uid), "subscribe", value["name"])
		sendPresence(self.source, TransportID, "subscribe", IDentifier["name"])
		if dist:
			self.rosterSet = True
			with Database(DatabaseFile, Semaphore) as db:
				db("update users set rosterSet=? where jid=?",
					(self.rosterSet, self.source))

	def getUserData(self, uid, fields = None):
		if not fields:
			if uid in self.friends:
				return self.friends[uid]
			fields = ["screen_name"]
		data = self.vk.method("users.get", {"fields": ",".join(fields), "user_ids": uid})
		if data:
			data = data.pop()
			data["name"] = escape("", u"%s %s" % (data.pop("first_name"), data.pop("last_name")))
		else:
			data = {}
			for key in fields:
				data[key] = "None"
		return data

	def sendMessages(self, init = False):
		with self.__sync:
			date = 0
			messages = self.vk.getMessages(200, self.lastMsgID if UseLastMessageID else 0)
			if not messages or not messages[0]:
				return None
			messages = sorted(messages[1:], msgSort)
			for message in messages:
				if message["out"] == 1:
					continue
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
					msgSend(Component, self.source, escape("", body), fromjid, date)
			if messages:
				lastMsg = messages[-1]
				self.lastMsgID = lastMsg["mid"]
				if UseLastMessageID:
					with Database(DatabaseFile, Semaphore) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.source))

	def processPollResult(self, opener):
		data = opener.read()

		if self.vk.engine.captcha:
			opener.close()
			return -1
	
		if not self.UserID:
			self.getUserID()

		if not data:
			logger.error("longpoll: no data. Will ask again.")
			return 1
		try:
			data = json.loads(data)
		except Exception:
			return 1

		if "failed" in data:
			logger.debug("longpoll: failed. Searching for new server.")
			return 0

		self.vk.longConfig["ts"] = data["ts"]
		for evt in data.get("updates", ()):
			typ = evt.pop(0)
			if typ == 4:  # message
				threadRun(self.sendMessages)
			elif typ == 8: # user online
				uid = abs(evt[0])
				sendPresence(self.source, vk2xmpp(uid), nick = self.getUserData(uid)["name"], caps = True)
			elif typ == 9: # user leaved
				uid = abs(evt[0])
				sendPresence(self.source, vk2xmpp(uid), "unavailable")
			elif typ == 61: # user typing
				if evt[0] not in self.typing:
					userTyping(self.source, vk2xmpp(evt[0]))
				self.typing[evt[0]] = time.time()
		return 1

	def updateTypingUsers(self, cTime):
		for user, last in self.typing.items():
			if cTime - last > 5:
				del self.typing[user]
				userTyping(self.source, vk2xmpp(user), "paused")

	def updateFriends(self, cTime):
		if cTime - self.last_udate > 360:
			self.vk.method("account.setOnline")
			self.last_udate = cTime
			friends = self.vk.getFriends()
			if not friends:
				logger.error("updateFriends: no friends received (user: %s)." % self.source)
				return None
			if friends and set(friends) != set(self.friends):
				for uid in friends:
					if uid not in self.friends:
						self.rosterSubscribe({uid: friends[uid]})
				for uid in self.friends:
					if uid not in friends:
						sendPresence(self.source, vk2xmpp(uid), "unsubscribe")
						sendPresence(self.source, vk2xmpp(uid), "unsubscribed")
				self.friends = friends

	def tryAgain(self):
		logger.debug("calling reauth for user %s" % self.source)
		try:
			if not self.vk.Online:
				self.connect()
			self.init(True)
		except Exception:
			crashLog("tryAgain")

msgSort = lambda msgOne, msgTwo: msgOne.get("mid", 0) - msgTwo.get("mid", 0)

def Sender(cl, stanza):
	try:
		cl.send(stanza)
	except Exception:
		crashLog("Sender")

def msgSend(cl, destination, body, source, timestamp = 0):
	msg = xmpp.Message(destination, body, "chat", frm = source)
	msg.setTag("active", namespace = xmpp.NS_CHATSTATES)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	Sender(cl, msg)

def apply(instance, args = ()):
	try:
		code = instance(*args)
	except Exception:
		code = None
	return code

isNumber = lambda obj: (not apply(int, (obj,)) is None)

def vk2xmpp(id):
	if not isNumber(id) and "@" in id:
		id = id.split("@")[0]
		if isNumber(id):
			id = int(id)
	elif id != TransportID:
		id = u"%s@%s" % (id, TransportID)
	return id

DESC = _("© simpleApps, 2013 — 2014."
	"\nYou can support developing of this project"
	" via donation by:\nYandex.Money: 410012169830956"
	"\nWebMoney: Z405564701378 | R330257574689.")

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

## TODO: remove this function and add it's code into msgSend.
def userTyping(target, instance, typ = "composing"):
	message = xmpp.Message(target, typ = "chat", frm = instance)
	message.setTag(typ, namespace = xmpp.NS_CHATSTATES)
	Sender(Component, message)

def watcherMsg(text):
	for jid in WatcherList:
		msgSend(Component, jid, text, TransportID)

def disconnectHandler(crash = True):
	if crash:
		crashLog("main.disconnect")
	Poll.clear()
	try:
		if Component.isConnected():
			Component.disconnect()
	except (NameError, AttributeError):
		pass
	for event in Handlers["evt02"]:
		event()
	Print("Reconnecting...")
	time.sleep(5)
	os.execl(sys.executable, sys.executable, *sys.argv)

## Public transport's list: http://anakee.ru/vkxmpp
def makeMeKnown():
	if WhiteList:
		WhiteList.append("anon.anakee.ru")
	if TransportID.split(".")[1] != "localhost":
		RIP = api.RequestProcessor()
		RIP.post("http://anakee.ru/vkxmpp/hosts.php", {"add": TransportID})
		Print("#! Information about myself successfully published.")

def garbageCollector():
	while True:
		time.sleep(60)
		gc.collect()

class Poll:

	__poll = {}
	__buff = set()
	__lock = threading._allocate_lock()

	@classmethod
	def __add(cls, user):
		try:
			opener = user.vk.makePoll()
		except Exception as e:
			logger.error("longpoll: failed make poll for user %s" % user.source)
			cls.__addToBuff(user)
		else:
			cls.__poll[opener.sock] = (user, opener)

	@classmethod
	def __addToBuff(cls, user):
		cls.__buff.add(user)
		logger.debug("longpoll: adding user %s to watcher" % user.source)
		threadRun(cls.__initPoll, (user,), cls.__initPoll.__name__)

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
				logger.debug("longpoll: while we wasted our time user %s has left" % user.source)
				with cls.__lock:
					if user in cls.__buff:
						cls.__buff.remove(user)
				return None
			if Transport[user.source].vk.initLongPoll():
				with cls.__lock:
					logger.debug("longpoll: %s successfully initialized longpoll" % user.source)
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
			logger.error("longpoll: failed to add %s to poll in 8 retries" % user.source)

	@classmethod
	def process(cls):
		while True:
			socks = cls.__poll.keys()
			if not socks:
				time.sleep(0.02)
				continue
			try:
				ready, error = select.select(socks, [], socks, 2)[::2]
			except (select.error, socket.error) as e:
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
					result = user.processPollResult(opener)
					if result == -1:
						continue
					elif result:
						cls.__add(user)
					else:
						cls.__addToBuff(user)

def updateCron():
	while True:
		for user in Transport.values():
			cTime = time.time()
			user.updateTypingUsers(cTime)
			user.updateFriends(cTime)
		time.sleep(2)

def main():
	global Component
	getPid()
	initDatabase(DatabaseFile)
	Component = xmpp.Component(Host, debug = DEBUG_XMPPPY)
	Print("\n#-# Connecting: ", False)
	if not Component.connect((Server, Port)):
		Print("fail.\n", False)
	else:
		Print("ok.\n", False)
		Print("#-# Auth: ", False)
		if not Component.auth(TransportID, Password):
			Print("fail (%s/%s)!\n" % (Component.lastErr, Component.lastErrCode), True)
			disconnectHandler(False)
		else:
			Print("ok.\n", False)
			Component.RegisterHandler("iq", iqHandler)
			Component.RegisterHandler("presence", prsHandler)
			Component.RegisterHandler("message", msgHandler)
			Component.RegisterDisconnectHandler(disconnectHandler)
			Component.set_send_interval(0.03125) # 32 messages per second
			Print("#-# Initializing users", False)
			with Database(DatabaseFile) as db:
				users = db("select jid from users").fetchall()
				for user in users:
					Print(".", False)
					Sender(Component, xmpp.Presence(user[0], "probe", frm = TransportID))
			Print("\n#-# Finished.")
			if allowBePublic:
				makeMeKnown()
			for num, event in enumerate(Handlers["evt01"]):
				threadRun(event, (), "extension-%d" % num)
			threadRun(garbageCollector, (), "gc")
			threadRun(Poll.process, (), "longPoll")
			threadRun(updateCron, (), "updateCron")

def exit(signal = None, frame = None):
	status = "Shutting down by %s" % ("SIGTERM" if signal == 15 else "SIGINT")
	Print("#! %s" % status, False)
	for user in Transport.itervalues():
		user.sendOutPresence(user.source, status)
		Print("." * len(user.friends), False)
	Print("\n")
	for event in Handlers["evt02"]:
		event()
	try:
		os.remove(pidFile)
	except OSError:
		pass
	os._exit(1)

def loadSomethingMore(dir):
	for something in os.listdir(dir):
		execfile("%s/%s" % (dir, something), globals())

if __name__ == "__main__":
	signal.signal(signal.SIGTERM, exit)
	signal.signal(signal.SIGINT, exit)
	loadSomethingMore("extensions")
	loadSomethingMore("handlers")
	main()
	while True:
		try:
			Component.iter(6)
		except AttributeError:
			disconnectHandler(False)
		except xmpp.StreamError:
			crashLog("Component.iter")
		except:
			logger.critical("DISCONNECTED")
			crashLog("Component.iter")
			disconnectHandler(False)
