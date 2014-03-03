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
					xmpp.NS_CHATSTATES,
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
	revNumber, rev = 0.143, 0 # 0. means testing. 
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

def startThr(thr, number = 0):
	if number > 2:
		raise RuntimeError("exit")
	try:
		thr.start()
	except threading.ThreadError:
		startThr(thr, (number + 1))

def threadRun(func, args = (), name = None):
	thr = threading.Thread(target = func, args = args, name = name)
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


class VKLogin(object):

	def __init__(self, number, password = None, jidFrom = None):
		self.number = number
		self.password = password
		self.Online = False
		self.source = jidFrom
		self.longConfig = {"mode": 66, "wait": 30, "act": "a_check"}
		self.longServer = ""
		logger.debug("VKLogin.__init__ with number:%s from jid:%s" % (number, jidFrom))

	getToken = lambda self: self.engine.token

	def auth(self, token = None):
		logger.debug("VKLogin.auth %s token" % ("with" if token else "without"))
		try:
			self.engine = api.APIBinding(self.number, self.password, token = token)
			self.checkData()
		except api.AuthError as e:
			logger.error("VKLogin.auth failed with error %s" % e.message)
			return False
		except Exception:
			crashLog("VKLogin.auth")
			return False

		logger.debug("VKLogin.auth completed")
		self.Online = True
		self.initLongPoll()  ## warning: this may take much of time.
		return self.Online

	@api.attemptTo(5, None, api.LongPollError)
	def initLongPoll(self):
		logger.debug("longpoll: requesting server address for user: %s" % self.source)
		response = self.method("messages.getLongPollServer")
		if not response:
			raise api.LongPollError()
		self.longServer = "http://%s" % response.pop("server")
		self.longConfig.update(response)
		logger.debug("longpoll: server: %s ts: %s" % (self.longServer, self.longConfig["ts"]))

	@api.attemptTo(5, None, api.LongPollError)
	def longPoll(self):
		data = self.engine.RIP.getOpener(self.longServer, self.longConfig)
		if data:
			data = json.loads(data)
		else:
			logger.error("longpoll: no data. Will ask again.")
			raise api.LongPollError()
		if "failed" in data:
			logger.debug("longpoll: failed. Searching for new server.")
			self.initLongPoll()
			raise api.LongPollError()
		self.longConfig["ts"] = data["ts"]
		return data.get("updates")

	makePoll = lambda self: self.engine.RIP.getOpener(self.longServer, self.longConfig)

	def checkData(self):
		if not self.engine.token and self.password:
			logger.debug("VKLogin.checkData: trying to login via password")
			self.engine.loginByPassword()
			self.engine.confirmThisApp()
			if not self.checkToken():
				raise api.apiError("Incorrect phone or password")

		elif self.engine.token:
			logger.debug("VKLogin.checkData: trying to use token")
			if not self.checkToken():
				logger.error("VKLogin.checkData: token invalid: " % self.engine.token)
				raise api.tokenError("Token for user %s invalid: " % (self.source, self.engine.token))
		else:
			logger.error("VKLogin.checkData: no token and password for jid:%s" % self.source)
			raise api.TokenError("%s, Where are your token?" % self.source)

	def checkToken(self):
		try:
			self.method("isAppUser")
		except api.VkApiError:
			return False
		return True

	def method(self, method, args = None):
		args = args or {}
		result = {}
		if not self.engine.captcha and self.Online:
			try:
				result = self.engine.method(method, args)
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
						Transport[self.source].deleteUser()
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
		friendsRaw = self.method("friends.get", {"fields": ",".join(fields)}) # friends.getOnline
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

	def msgMarkAsRead(self, list):
		list = str.join(",", list)
		self.method("messages.markAsRead", {"message_ids": list})

	def getMessages(self, count = 5, lastMsgID = 0):
		values = {"out": 0, "filters": 1, "count": count}
		if lastMsgID:
			del values["count"]
			values["last_message_id"] = lastMsgID
		return self.method("messages.get", values)


class tUser(object):

	def __init__(self, data = (), source = ""):
		self.password = None
		if data:
			self.username, self.password = data
		self.friends = {}
		self.auth = None
		self.token = None
		self.lastMsgID = None
		self.lastMsgDate = 0
		self.rosterSet = None
		self.existsInDB = None
		self.last_udate = time.time()
		self.typing = {}
		self.source = source
		self.resources = []
		self.chatUsers = {}
		self.__sync = threading._allocate_lock()
		self.vk = VKLogin(self.username, self.password, self.source)
		logger.debug("initializing tUser for %s" % self.source)
		with Database(DatabaseFile, Semaphore) as db:
			db("select * from users where jid=?", (self.source,))
			desc = db.fetchone()
			if desc:
				if not self.token or not self.password:
					logger.debug("tUser: %s exists in db. Using it." % self.source)
					self.existsInDB = True
					self.source, self.username, self.token, self.lastMsgID, self.rosterSet = desc
				elif self.password or self.token:
					logger.debug("tUser: %s exists in db. Will be deleted." % self.source)
					threadRun(self.deleteUser)

	def __eq__(self, user):
		if isinstance(user, tUser):
			return user.source == self.source
		return self.source == user

## TODO: Move this function otside class
	def deleteUser(self, roster = False):
		logger.debug("tUser: deleting user %s from db." % self.source)
		with Database(DatabaseFile) as db:
			db("delete from users where jid=?", (self.source,))
			db.commit()
		self.existsInDB = False
		if roster and self.friends:
			logger.debug("tUser: deleting me from %s roster" % self.source)
			for id in self.friends.keys():
				jid = vk2xmpp(id)
				self.sendPresence(self.source, jid, "unsubscribe")
				self.sendPresence(self.source, jid, "unsubscribed")
			self.vk.Online = False
		if self.source in Transport:
			del Transport[self.source]
		Poll.remove(self)

	def msg(self, body, uID, mType = "user_id"):
		try:
			Message = self.vk.method("messages.send", {mType: uID, "message": body, "type": 0})
		except Exception:
			crashLog("messages.send")
			Message = False
		return Message

	def connect(self):
		logger.debug("tUser: connecting %s" % self.source)
		self.auth = False
		try:
			self.auth = self.vk.auth(self.token)
		except api.CaptchaNeeded:
			self.rosterSubscribe()
			self.vk.captchaChallenge()
			return True
		except api.TokenError as e:
			if e.message == "User authorization failed: user revoke access for this token.":
				logger.critical("tUser: %s" % e.message)
				self.deleteUser()
			elif e.message == "User authorization failed: invalid access_token.":
				msgSend(Component, self.source, _(e.message + " Please, register again"), TransportID)
			self.vk.Online = False
		except Exception:
			crashLog("tUser.Connect")
			return False
		else:
			logger.debug("tUser: auth=%s for %s" % (self.auth, self.source))

		if self.auth and self.vk.getToken():
			logger.debug("tUser: updating db for %s because auth done " % self.source)
			if not self.existsInDB:
				with Database(DatabaseFile, Semaphore) as db:
					db("insert into users values (?,?,?,?,?)", (self.source, self.username,
						self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set token=? where jid=?", (self.vk.getToken(), self.source))
			try:
				json = self.vk.method("users.get")
				self.UserID = json[0]["uid"]
			except (KeyError, TypeError):
				logger.error("tUser: could not recieve user id. JSON: %s" % str(json))
				self.UserID = 0

			jidToID[self.UserID] = self.source
			self.friends = self.vk.getFriends()
			self.vk.Online = True
		if not UseLastMessageID:
			self.lastMsgID = 0
		return self.vk.Online

	def init(self, force = False, send = True):
		logger.debug("tUser: called init for user %s" % self.source)
		self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("tUser: calling subscribe with force:%s for %s" % (force, self.source))
			self.rosterSubscribe(self.friends)
		if send: self.sendInitPresence()
		self.sendMessages()

## TODO: Move this function otside class
	def sendPresence(self, target, jidFrom, pType = None, nick = None, reason = None):
		Presence = xmpp.Presence(target, pType, frm = jidFrom, status = reason)
		if nick:
			Presence.setTag("nick", namespace = xmpp.NS_NICK)
			Presence.setTagData("nick", nick)
		Sender(Component, Presence)

	def sendInitPresence(self):
		self.friends = self.vk.getFriends() ## too too bad way to do it again. But it's a guarantee of the availability of friends.
		logger.debug("tUser: sending init presence to %s (friends %s)" %\
					(self.source, "exists" if self.friends else "empty"))
		for uid, value in self.friends.iteritems():
			if value["online"]:
				self.sendPresence(self.source, vk2xmpp(uid), None, value["name"])
		self.sendPresence(self.source, TransportID, None, IDentifier["name"])

	def sendOutPresence(self, target, reason = None):
		logger.debug("tUser: sending out presence to %s" % self.source)
		for uid in self.friends.keys() + [TransportID]:
			self.sendPresence(target, vk2xmpp(uid), "unavailable", reason = reason)

	def rosterSubscribe(self, dist = None):
		dist = dist or {}
		for uid, value in dist.iteritems():
			self.sendPresence(self.source, vk2xmpp(uid), "subscribe", value["name"])
		self.sendPresence(self.source, TransportID, "subscribe", IDentifier["name"])
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

	def sendMessages(self):
		with self.__sync:
			messages = self.vk.getMessages(200, self.lastMsgID if UseLastMessageID else 0)
			if not messages:
				return None
			if not messages[0]:
				return None
			messages = sorted(messages[1:], msgSort)
			read = []
			for message in messages:
#				if message["date"] <= self.lastMsgDate:
#					continue
				read.append(str(message["mid"]))
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
					msgSend(Component, self.source, escape("", body), fromjid, message["date"])
			if read:
				lastMsg = messages[-1]
				self.lastMsgID = lastMsg["mid"]
				self.lastMsgDate = lastMsg["date"]
				self.vk.msgMarkAsRead(read)
				if UseLastMessageID:
					with Database(DatabaseFile, Semaphore) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.source))

	def processPollResult(self, opener):
		data = opener.read()
		if not data:
			logger.error("longpoll: no data. Will ask again.")
			return None
		data = json.loads(data)
		if "failed" in data:
			logger.debug("longpoll: failed. Searching for new server.")
			self.vk.initLongPoll()
			return None
		self.vk.longConfig["ts"] = data["ts"]
		for evt in data.get("updates", ()):
			typ = evt.pop(0)
			if typ == 4:  # message
				threadRun(self.sendMessages)
			elif typ == 8: # user online
				uid = abs(evt[0])
				self.sendPresence(self.source, vk2xmpp(uid), nick = self.getUserData(uid)["name"])
			elif typ == 9: # user leaved
				uid = abs(evt[0])
				self.sendPresence(self.source, vk2xmpp(uid), "unavailable")
			elif typ == 61: # user typing
				if evt[0] not in self.typing:
					userTyping(self.source, vk2xmpp(evt[0]))
				self.typing[evt[0]] = time.time()

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
			if set(friends) != set(self.friends):
				for uid in friends:
					if uid not in self.friends:
						self.rosterSubscribe({uid: friends[uid]})
				for uid in self.friends:
					if uid not in friends:
						self.sendPresence(self.source, vk2xmpp(uid), "unsubscribe")
						self.sendPresence(self.source, vk2xmpp(uid), "unsubscribed")
				self.friends = friends

	def tryAgain(self):
		logger.debug("calling reauth for user %s" % self.source)
		try:
			if not self.vk.Online:
				self.connect()
			self.init(True)
		except Exception:
			crashLog("tryAgain")

msgSort = lambda msgOne, msgTwo: msgOne["mid"] - msgTwo["mid"]

def Sender(cl, stanza):
	try:
		cl.send(stanza)
	except Exception:
		crashLog("Sender")

def msgSend(cl, jidTo, body, jidFrom, timestamp = 0):
	msg = xmpp.Message(jidTo, body, "chat", frm = jidFrom)
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
	elif id == TransportID:
		return id
	else:
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
	__lock = threading._allocate_lock()

	@classmethod
	def __add(cls, user):
		opener = user.vk.makePoll()
		cls.__poll[opener.sock] = (user, opener)

	@classmethod
	def add(cls, some_user):
		with cls.__lock:
			for sock, (user, opener) in cls.__poll.iteritems():
				if some_user == user:
					break
			else:
				cls.__add(some_user)

	@classmethod
	def remove(cls, some_user):
		with cls.__lock:
			for sock, (user, opener) in cls.__poll.iteritems():
				if some_user == user:
					del cls.__poll[sock]
					opener.close()
					break

	clear = staticmethod(__poll.clear)

	@classmethod
	def process(cls):
		while True:
			socks = cls.__poll.keys()
			if not socks:
				time.sleep(0.02)
			ready, error = select.select(socks, [], socks, 2)[::2]
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
					user.processPollResult(opener)
					cls.__add(user)

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
			for event in Handlers["evt01"]:
				threadRun(event)
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
			Component.iter(1)
		except AttributeError:
			disconnectHandler(False)
		except xmpp.StreamError:
			crashLog("Component.iter")
		except:
			logger.critical("DISCONNECTED")
			crashLog("Component.iter")
			disconnectHandler(False)
