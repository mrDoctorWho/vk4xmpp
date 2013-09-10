#!/usr/bin/python
# coding:utf-8

# vk4xmpp gateway, v1.7
# © simpleApps, 01.08.2013
# Program published under MIT license.

import os, sys, time, json, signal, urllib, socket, traceback, threading
from datetime import datetime
from math import ceil
if not hasattr(sys, "argv") or not sys.argv[0]:
	sys.argv = ["."]

try:
	__file__ = os.path.dirname(os.path.abspath(sys.argv[0]))
	os.chdir(__file__)
except OSError:
	print "#! Incorrect launch!"
	time.sleep(6)

sys.path.insert(0, "library")
reload(sys).setdefaultencoding("utf-8")
socket.setdefaulttimeout(10)

import gc
gc.enable()

## xmpppy.
import xmpp

## other.
from itypes import Database
from webtools import *
from writer import *
from stext import *
from stext import _
from hashlib import sha1
import vk_api as api

Transport = {}
TransportsList = []
WatcherList = []
WhiteList = []

TransportFeatures = [ xmpp.NS_DISCO_ITEMS,
					  xmpp.NS_DISCO_INFO,
					  xmpp.NS_REGISTER,
					  xmpp.NS_GATEWAY,
					  xmpp.NS_VERSION,
					  xmpp.NS_CAPTCHA,
					  xmpp.NS_STATS,
					  xmpp.NS_VCARD, 
					  xmpp.NS_LAST ]

IDentifier = { "type": "vk",
			   "category": "gateway",
			   "name": "VK4XMPP Transport" }

Semaphore = threading.Semaphore()

SLICE_STEP = 8
pidFile = "pidFile.txt"
Config = "Config.txt"
DefLang = "ru"

DEBUG_XMPPPY = False

startTime = int(time.time())

if os.path.exists(Config):
	try:
		execfile(Config)
		Print("#-# Config loaded successfully.")
	except:
		crashLog("config.load")
else:
	Print("#-# Config file doesn't exists.")
setVars(DefLang, __file__)

import logging

logger = logging.getLogger("vk4xmpp")
logger.setLevel(logging.DEBUG)
loggerHandler = logging.FileHandler("vk4xmpp.log")
Formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s %(message)s", "[%d.%m.%Y %H:%M:%S]")
loggerHandler.setFormatter(Formatter)
logger.addHandler(loggerHandler)

def gatewayRev():
	revNumber, rev = 0, 0
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)

OS = "{0} {2:.16} [{4}]".format(*os.uname())
Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)
Revision = gatewayRev()

def initDatabase(filename):
	if not os.path.exists(filename):
		with Database(filename) as db:
			db("create table users (jid text, username text, token text, lastMsgID integer, rosterSet bool)")
			db.commit()
	return True


def startThr(Thr, Number = 0):
	if Number > 2:
		raise RuntimeError("exit")
	try:
		Thr.start()
	except threading.ThreadError:
		startThr(Thr, (Number + 1))
	except:
		crashLog("startThr")

def threadRun(func, args = (), name = None):
	Thr = threading.Thread(target = func, args = args, name = name)
	if name:
		logger.debug("starting thread with name %s" % name)
	try:
		Thr.start()
	except threading.ThreadError:
		try:
			startThr(Thr)
		except RuntimeError:
			try:
				Thr.run()
			except KeyboardInterrupt:
				raise KeyboardInterrupt("Interrupt (Ctrl+C)")
	except:
		logger.debug("failed run thread called %s: %s(%s)" % (name, func.func_name, str(args)))
		crashLog("threadRun")

class VKLogin(object):

	def __init__(self, number, password = None, jidFrom = None):
		self.number = number
		self.password = password
		self.Online = False
		self.lastMethod = None
		self.jidFrom = jidFrom
		logger.debug("VKLogin.__init__ with number:%s from jid:%s"  % (number, jidFrom))

	def auth(self, token = None):
		logger.debug("VKLogin.auth %s token" % ("with" if token else "without"))
		try:
			self.engine = api.VkApi(self.number, self.password, token = token)
			self.checkData()
		except api.authError as e:
			logger.error("VKLogin.auth failed with error %s" % e.message)
			return False
		except:
			crashLog("VKLogin.auth")
		logger.debug("VKLogin.auth completed")
		self.Online = True
		self.onlineMe(900)
		return self.Online

	def checkData(self):
		if not self.engine.token and self.password:
			logger.debug("VKLogin.checkData: trying to login via password")
			self.engine.vk_login()
			self.engine.api_login()
			if not self.checkToken():
				raise api.apiError("Incorrect phone or password")

		elif self.engine.token:
			logger.debug("VKLogin.checkData: trying to use token")
			if not self.checkToken():
				logger.error("VKLogin.checkData: token invalid: " % self.engine.token)
				raise api.tokenError("Token for user %s invalid: " % (self.jidFrom, self.engine.token))
		else: 
			logger.error("VKLogin.checkData: no token and password for jid:%s" % self.jidFrom)
			raise api.tokenError("%s, Where are your token?" % self.jidFrom)

	def checkToken(self):
		try:
			self.method("isAppUser")
		except api.apiError:
			return False
		return True

	def executeMe(self, func, method, args = {}):
		try:
			return func(method, args)
		except api.apiError as e:
			if e.message == "Logged out":
				return {}
			logger.error("VKLogin: apiError %s for user %s" % (e.message, self.jidFrom))
		except api.captchaNeeded:
			logger.error("VKLogin: running captcha challenge for %s" % self.jidFrom)
			self.captchaChallenge()
			return {}

	def method(self, method, args = {}, force = False):
		result = {}
		if not self.engine.captcha or force:
			result = self.executeMe(self.engine.method, method, args)
		return result

	def captchaChallenge(self):
		if self.engine.captcha:
			logger.debug("VKLogin: sending message with captcha to %s" % self.jidFrom)
			body = _("WARNING: VK sent captcha to you."\
					 " Please, go to %s and enter text from image to chat."\
					 " Example: !captcha my_captcha_key. Tnx") % self.engine.captcha["img"]
			Types = (dict(type = "form"), dict(type = "hidden", var = "form"))
			msg = xmpp.Message(self.jidFrom, body, "chat", frm = TransportID)
			msg.setTag("x", {}, xmpp.NS_OOB)
			xTag = msg.getTag("x", {}, xmpp.NS_OOB)
			xTag.setTagData("url", self.engine.captcha["img"])
			msg.setTag("captcha", {}, xmpp.NS_CAPTCHA)
			cTag = msg.getTag("captcha", {}, xmpp.NS_CAPTCHA)
			cTag.setTag("x", Types[0], xmpp.NS_DATA)
			imgData = vCardGetPhoto(self.engine.captcha["img"], False)
			imgHash = sha1(imgData).hexdigest()
			imgEncoded = imgData.encode("base64")
			cxTag = cTag.setTag("x", Types[0], xmpp.NS_DATA)
			cxTag.addChild("field", dict(type = "hidden", var = "FORM_TYPE"), 
									[xmpp.Node("value", payload = [xmpp.NS_CAPTCHA])])
			cxTag.addChild("field", dict(type = "hidden", var = "from"),
									[xmpp.Node("value", payload = [TransportID])])
			cxTag.addChild("field", {"label": _("Enter shown text"), "var": "ocr"}, 
									[xmpp.Node("required"),	xmpp.Node("media", {"xmlns": xmpp.NS_MEDIA}, 
									[xmpp.Node("uri", {"type": "image/jpg"}, ["cid:sha1+%s@bob.xmpp.org" % imgHash])])])
			msg.setTag("data", {"cid": "sha1+%s@bob.xmpp.org" % imgHash, "type":"image/jpg", "max-age":"0"}, xmpp.NS_URN_OOB)
			obTag = msg.getTag("data", {"cid": "sha1+%s@bob.xmpp.org" % imgHash, "type": "image/jpg", "max-age": "0"}, xmpp.NS_URN_OOB)
			obTag.setData(imgEncoded)
			Sender(Component, msg)
		else:
			logger.error("VKLogin: captchaChallenge called without captcha for user %s" % self.jidFrom)

	def disconnect(self):
		logger.debug("VKLogin: user %s is gone!" % self.jidFrom)
		self.method("account.setOffline")
		self.Online = False

	def getToken(self):
		return self.engine.token

	def getFriends(self, fields = "screen_name"):
		friendsRaw = self.method("friends.get", {"fields": fields}) # friends.getOnline
		friendsDict = {}
		if friendsRaw:
			for friend in friendsRaw:
				id = friend["uid"]
				name = u"%s %s" % (friend["first_name"], friend["last_name"])
				try:
					friendsDict[id] = {"name": name, "online": friend["online"]}
					friendsDict[id]["photo"] = friend.get("photo_200_orig", URL_VCARD_NO_IMAGE)
				except KeyError:
					crashLog("vk.getFriend")
					continue
		return friendsDict

	def msgMarkAsRead(self, list):
		list = str.join(",", list)
		self.method("messages.markAsRead", {"message_ids": list})

	def getMessages(self, lastjoinTime = 0, count = 5, lastMsgID = 0):
		values = {"out": 0, "time_offset": lastjoinTime, 
							"filters": 1, "count": count}
		if lastMsgID:
			del values["count"]
			del values["time_offset"]
			values["last_message_id"] = lastMsgID
		return self.method("messages.get", values)

	def onlineMe(self, timeout = 900):
		self.method("account.setOnline")
		gc.collect(	)					# only this line is needed part of all transport code. ITS A MAGIC DUDE!
		if self.Online:					# config
			threading.Timer(timeout, self.onlineMe, (timeout,)).start()

class tUser(object):

	def __init__(self, cl, data = [], source = ""):
		self.password = False
		if data:
			self.username, self.password = data
		self.cl = cl
		self.friends = {}
		self.auth = False
		self.token = False
		self.fullJID = False
		self.lastStatus = False
		self.lastMsgID = False
		self.rosterSet = False
		self.existsInDB = False
		self.last_activity = time.time()
		if len(source) == 2:							# Is it 
			self.fullJID, self.jUser = source			# really
		else:
			self.jUser = source							# needed?
		self.vk = VKLogin(self.username, self.password, self.jUser)
		logger.debug("initializing tUser for %s" % self.jUser)
		with Database(DatabaseFile, Semaphore) as db:
			base = db("select * from users where jid=?", (self.jUser,))
			desc = db.fetchone()
			if desc:
				if not self.token or not self.password:
					logger.debug("tUser: %s exists in db. Using it." % self.jUser)
					self.existsInDB = True
					self.jUser, self.username, self.token, self.lastMsgID, self.rosterSet = desc
				elif self.password or self.token:
					logger.debug("tUser: %s exists in db. Will be deleted." % self.jUser)
					threadRun(self.deleteUser)

	def deleteUser(self, roster = False):
		logger.debug("tUser: deleting user %s from db." % self.jUser)
		with Database(DatabaseFile) as db:
			db("delete from users where jid=?", (self.jUser,))
			db.commit()
		if roster and self.friends:
			logger.debug("tUser: deleting me from %s roster" % self.jUser)
			for id in self.friends.keys():
				jid = vk2xmpp(id)
				unSub = xmpp.Presence(self.fullJID, "unsubscribe", frm = jid)
				Sender(self.cl, unSub)
				unSubed = xmpp.Presence(self.fullJID, "unsubscribed", frm = jid)
				Sender(self.cl, unSubed)
			self.vk.Online = False
		if self.jUser in Transport:
			del Transport[self.jUser]
			updateTransportsList(self, False)


	def msg(self, body, uID):
		try:
			self.last_activity = time.time()
			self.vk.method("account.setOnline")
			Message = self.vk.method("messages.send", {"user_id": uID, "message": body, "type": 0})
		except:
			crashLog("messages.send")
			Message = False
		return Message

	def connect(self):
		logger.debug("tUser: connecting %s" % self.jUser)
		self.auth = False
		try:
			self.auth = self.vk.auth(self.token)
			logger.debug("tUser: auth=%s for %s" % (self.auth, self.jUser))
		except api.tokenError:
			crashLog("tUser.Connect")
			self.deleteUser()
		except api.captchaNeeded:
			self.rosterAdd()
			self.vk.captchaChallenge()
			return True
		except:
			crashLog("tUser.connect")
			return False
		if self.auth and self.vk.getToken(): #!
			logger.debug("tUser: updating db for %s because auth done " % self.jUser)
			if not self.existsInDB:
				with Database(DatabaseFile, Semaphore) as db:
					db("insert into users values (?,?,?,?,?)", (self.jUser, self.username, 
						self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set token=? where jid=?", (self.vk.getToken(), self.jUser))
			self.friends = self.vk.getFriends()
			self.vk.Online = True
		return self.vk.Online

	def init(self, force = False):
		logger.debug("tUser: called init for user %s" % self.jUser)
		self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("tUser: calling subscribe with force:%s for %s" % (force, self.jUser))
			self.rosterSubscribe(self.friends)
		threadRun(self.sendInitPresence)
		threadRun(self.sendMessages) # is it valid?

	def sendInitPresence(self):
		logger.debug("tUser: sending init presence to %s (friends %s)" % (self.jUser, "exists" if self.friends else "null"))
		Sender(self.cl, xmpp.protocol.Presence(self.jUser, frm = TransportID))
		if self.friends:
			for uid in self.friends.keys():
				jid = vk2xmpp(uid)
				pType = "unavailable" if not self.friends[uid]["online"] else None
				nickName = self.friends[uid]["name"]
				Presence = xmpp.protocol.Presence(self.jUser, pType, frm = jid)
				Presence.setTag("nick", namespace = xmpp.NS_NICK)
				Presence.setTagData("nick", nickName)
				Sender(self.cl, Presence)

	def sendMessages(self):
		messages = self.vk.getMessages(None, 200, lastMsgID = 0)#self.lastMsgID) # messages.getLastActivity
		if messages:
			messages = messages[1:]
			messages = sorted(messages, lambda a, b: a["date"] - b["date"])
			if messages:
				self.lastMsgID = messages[-1]["mid"]
				read = list()
				for message in messages:
					read.append(str(message.get("mid", 0)))
					fromjid = "%s@%s" % (message["uid"], TransportID)
					body = uHTML(message["body"])
					if message.has_key("attachments"):
						body += _("\nAttachments:")
						attachments = message["attachments"]
						for att in attachments:
							key = att.get("type")
							if key == "wall":
								continue	
							elif key == "photo":
								keys = ("src_big", "url", "src_xxxbig", "src_xxbig", "src_xbig", "src", "src_small")
								for dKey in keys:
									if att[key].has_key(dKey):
										body += "\n" + att[key][dKey]
										break
							elif key == "video":
								body += "\nVideo: http://vk.com/video%(owner_id)s_%(vid)s — %(title)s"
							elif key == "audio":
								body += "\nAudio: %(performer)s — %(title)s — %(url)s"
							elif key == "doc":
								body += "\nDocument: %(title)s — %(url)s"
							else:
								body += "\nUnknown attachment: " + str(att[key])
							body = body % att.get(key, {})

					if message.has_key("fwd_messages"):
						body += _("\nForward messages")
						fwd_messages = sorted(message["fwd_messages"], lambda a, b: a["date"] - b["date"])
						for fwd in fwd_messages:
							idFrom = fwd["uid"]
							date = fwd["date"]
							fwdBody = uHTML(fwd["body"])
							date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
							if idFrom not in self.friends:
								name = self.vk.method("users.get", {"fields": "screen_name", "user_ids": idFrom})
								if name:
									name = name.pop()
									name = u"%s %s" % (name["first_name"], name["last_name"])
							else:
								name =  self.friends[idFrom]
							body += "\n[%s] <%s> %s" % (date, name, fwdBody)
					msgSend(self.cl, self.jUser, body, fromjid, message["date"])
				self.vk.msgMarkAsRead(read)
				if UseLastMessageID:
					with Database(DatabaseFile, Semaphore) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.jUser))

	def rosterSubscribe(self, dist = {}):
		Presence = xmpp.Presence(self.jUser, "subscribe")
		Presence.setTag("nick", namespace = xmpp.NS_NICK)
		for id in dist.keys():
			nickName = self.friends[id]["name"]
			Presence.setTagData("nick", nickName)
			Presence.setFrom(vk2xmpp(id))
			Sender(self.cl, Presence)
			time.sleep(0.2)
		Presence.setFrom(TransportID)
		Presence.setTagData("nick", IDentifier["name"])
		Sender(self.cl, Presence)
		if dist:
			self.rosterSet = True
			with Database(DatabaseFile, Semaphore) as db:
				db("update users set rosterSet=? where jid=?", (self.rosterSet, self.jUser))

	def tryAgain(self):
		logger.debug("calling reauth for user %s" % self.jUser)
		try:
			if not self.vk.Online:
				self.connect()
			self.init(True)
		except:
			crashLog("tryAgain")

def Sender(cl, stanza):
	try:
		cl.send(stanza)
		gc.collect() 		## maybe it's wrong place, because collect() takes many cpu time, but when we have many users we'll collect more
		time.sleep(0.001)
	except IOError:
		logger.error("Panic: Couldn't send stanza: %s" % str(stanza))
	except:
		crashLog("Sender")


def msgSend(cl, jidTo, body, jidFrom, timestamp = 0):
	msg = xmpp.Message(jidTo, body, "chat", frm = jidFrom)
	msg.setTimestamp(timestamp)
	Sender(cl, msg)

def msgRecieved(msg, jidFrom, jidTo):
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom)
		tag = answer.setTag("received", namespace = "urn:xmpp:receipts")
		tag.setAttr("id", msg.getID())
		answer.setFrom(jidTo)
		answer.setID(msg.getID())
		return answer

def msgHandler(cl, msg):
	mType = msg.getType()
	jidFrom = msg.getFrom()
	jidFromStr = jidFrom.getStripped()
	if jidFromStr in Transport and mType == "chat":
		Class = Transport[jidFromStr]
		jidTo = msg.getTo()
		body = msg.getBody()
		if body:
			answer = None
			if jidTo == TransportID:
				raw = body.split(None, 1)
				if len(raw) > 1:
					text, args = raw
					args = args.strip()
					if text == "!captcha" and args:
						captchaAccept(cl, args, jidTo, jidFromStr)
						answer = msgRecieved(msg, jidFrom, jidTo)
			else:
				uID = jidTo.getNode()
				vkMessage = Class.msg(body, uID)
				if vkMessage:
					answer = msgRecieved(msg, jidFrom, jidTo)
			if answer:
				Sender(cl, answer)
		else:
			raise xmpp.NodeProcessed()


def apply(instance, args = ()):
	try:
		code = instance(*args)
	except:
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

def prsHandler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	jidTo = prs.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	if jidFromStr in Transport:
		Class = Transport[jidFromStr]
		if pType in ("available", "probe", None):
			if not Class.vk.Online and Class.lastStatus != pType:
				logger.debug("%s from user %s, will send sendInitPresence" % (pType, jidFromStr))
				Class.vk.Online = True
				Class.vk.onlineMe()
				Class.sendInitPresence()
			else:
				raise xmpp.NodeProcessed()

		elif pType == "unavailable" and Class.lastStatus != pType:
			Sender(cl, xmpp.Presence(jidFromStr, "unavailable", frm = TransportID))
			Class.vk.disconnect()

		elif pType == "subscribe":
			if jidToStr == TransportID:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = TransportID))
				Sender(cl, xmpp.Presence(jidFrom, frm = TransportID))
			else:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = jidTo))
				if Class.friends:
					id = vk2xmpp(jidToStr)
					if id in Class.friends:
						if Class.friends[id]["online"]:
							Sender(cl, xmpp.Presence(jidFrom, frm = jidTo))
		Class.lastStatus = pType

def iqBuildError(stanza, error = None, text = None):
	if not error:
		error = xmpp.ERR_FEATURE_NOT_IMPLEMENTED
	error = xmpp.Error(stanza, error, True)
	if text:
		eTag = error.getTag("error")
		eTag.setTagData("text", text)
	return error

def captchaAccept(cl, args, jidTo, jidFromStr):
	if args:
		answer = None
		Class = Transport[jidFromStr]
		if Class.vk.engine.captcha:
			logger.debug("user %s called captcha challenge" % jidFromStr)
			Class.vk.engine.captcha["key"] = args
			retry = False
			try:
				logger.debug("retrying for user %s" % jidFromStr)
				retry = Class.vk.engine.retry()
			except api.captchaNeeded:
				logger.error("retry for user %s failed!" % jidFromStr)
				Class.vk.captchaChallenge()
			if retry:
				logger.debug("retry for user %s OK" % jidFromStr)
				answer = _("Captcha valid.")
				Class.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, jidFromStr, answer, jidTo)
		

def iqHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidFromStr = jidFrom.getStripped()
	if WhiteList:
		if jidFrom and jidFrom.getDomain() not in WhiteList:
			Sender(cl, iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "You're not in the white-list"))
			raise xmpp.NodeProcessed()

	if iq.getType == "set" and iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		if jidFromStr in Transport:
			jidTo = iq.getTo()
			if jidTo == TransportID:
				cTag = iq.getTag("captcha")
				cxTag = cTag.getTag("x", {}, xmpp.NS_DATA)
				fcxTag = cxTag.getTag("field", {"var": "ocr"})
				cValue = fcxTag.getTagData('value')
				captchaAccept(cl, cValue, jidTo, jidFromStr)

	ns = iq.getQueryNS()
	if ns == xmpp.NS_REGISTER:
		iqRegisterHandler(cl, iq)
	elif ns == xmpp.NS_GATEWAY:
		iqGatewayHandler(cl, iq)
	elif ns == xmpp.NS_STATS:
		iqStatsHandler(cl, iq)
	elif ns == xmpp.NS_VERSION:
		iqVersionHandler(cl, iq)
	elif ns == xmpp.NS_LAST:
		iqUptimeHandler(cl, iq)
	elif ns in (xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS):
		iqDiscoHandler(cl, iq)
	else:
		Tag = iq.getTag("vCard") or iq.getTag("ping")
		if Tag and Tag.getNamespace() == xmpp.NS_VCARD:
			iqVcardHandler(cl, iq)
		elif Tag and Tag.getNamespace == xmpp.NS_PING:
			Sender(cl, iq.buildReply("result"))

	raise xmpp.NodeProcessed()

URL_ACCEPT_APP = "http://simpleapps.ru/vk4xmpp.html"

def iqRegisterHandler(cl, iq):
	jidTo = iq.getTo()
	jidFrom = iq.getFrom()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")

	if iType == "get" and jidToStr == TransportID and not IQChildren:
		data = xmpp.Node("x")
		logger.debug("Sending register form to %s" % jidFromStr)
		data.setNamespace(xmpp.NS_DATA)
		instr= data.addChild(node=xmpp.Node("instructions"))
		instr.setData(_("Enter phone number (like +71234567890) and password (or access-token)"\
			"\nIf your need automatic authorization, mark checkbox and enter password of your VK account."))
		link = data.addChild(node=xmpp.DataField("link"))
		link.setLabel(_("If you won't get access-token automatically, please, follow authorization link below and authorize app,\n"\
					  "and then paste url to password field. Autorization page"))
		link.setType("text-single")
		link.setValue(URL_ACCEPT_APP)
		phone = data.addChild(node=xmpp.DataField("phone"))
		phone.setLabel(_("Type phone"))
		phone.setType("text-single")
		phone.setValue("+")
		use_password = data.addChild(node=xmpp.DataField("use_password"))
		use_password.setLabel(_("Try to get access-token automatically? (NOT recommented, password required)"))
		use_password.setType("boolean")
		use_password.setValue("0")
		password = data.addChild(node=xmpp.DataField("password"))
		password.setLabel(_("Type password or url (recommented) or access-token"))
		password.setType("text-private")
		result.setQueryPayload((data,))

	elif iType == "set" and jidToStr == TransportID and IQChildren:
		phone, password, usePassword, token = False, False, False, False
		Query = iq.getTag("query")
		if Query.getTag("x"):
			for node in iq.getTags("query", namespace = xmpp.NS_REGISTER):
				for node in node.getTags("x", namespace = xmpp.NS_DATA):
					phone = node.getTag("field", {"var": "phone"})
					phone = phone and phone.getTagData("value")
					password = node.getTag("field", {"var": "password"})
					password = password and password.getTagData("value")
					usePassword = node.getTag("field", {"var": "use_password"})
					usePassword = usePassword and usePassword.getTagData("value")

			if not phone:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Phone incorrect."))
			if not password:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Null password"))
			if not isNumber(usePassword):
				if usePassword.lower() == "true":
					usePassword = 1
				else:
					usePassword = 0
			usePassword = int(usePassword)
			if not usePassword:
				logger.debug("user %s won't to use password" % jidFromStr)
				token = password
				password = None
			else:
				logger.debug("user %s want to use password" % jidFromStr)
			user = tUser(cl, (phone, password), (jidFrom, jidFromStr))
			if not usePassword:
				try:
					token = token.split("#access_token=")[1].split("&")[0].strip()
				except (IndexError, AttributeError):
					pass
				user.token = token
			if not user.connect():
				logger.error("user %s connection failed (from iq)" % jidFromStr)
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
			else:
				try: 
					user.init()
				except api.captchaNeeded:
					user.vk.captchaChallenge()
				except:
					crashLog("iq.user.init")
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
				else:
					Transport[jidFromStr] = user
					updateTransportsList(Transport[jidFromStr]) #$
					WatcherMsg(_("New user registered: %s") % jidFromStr)

		elif Query.getTag("remove"): # Maybe exits a better way for it
			logger.debug("user %s want to remove me :(" % jidFromStr)
			if jidFromStr in Transport:
				Class = Transport[jidFromStr]
				Class.fullJID = jidFrom
				Class.deleteUser(True)
				result.setPayload([], add = 0)
				WatcherMsg(_("User remove registration: %s") % jidFromStr)
		else:
			result = iqBuildError(iq, 0, _("Feature not implemented."))
	Sender(cl, result)

def calcStats():
	countTotal = 0
	countOnline = 0
	with Database(DatabaseFile, Semaphore) as db:
		db("select count(*) from users")
		countTotal = db.fetchone()[0]
	for key in TransportsList:
		if hasattr(key, "vk") and key.vk.Online:
			countOnline += 1
	return [countOnline, countTotal]

def iqUptimeHandler(cl, iq):
	jidFrom = iq.getFrom()
	iType = iq.getType()
	if iType == "get":
		uptime = int(time.time() - startTime)
		result = xmpp.Iq("result", to = jidFrom)
		result.setID(iq.getID())
		result.setTag("query", {"seconds": str(uptime)}, xmpp.NS_LAST)
		result.setTagData("query", IDentifier["name"])
		Sender(cl, result)
	raise xmpp.NodeProcessed()

def iqVersionHandler(cl, iq):
	iType = iq.getType()
	result = iq.buildReply("result")
	if iType == "get":
		Query = result.getTag("query")
		Query.setTagData("name", IDentifier["name"])
		Query.setTagData("version", Revision)
		Query.setTagData("os", "%s / %s" % (OS, Python))
		Sender(cl, result)
	raise xmpp.NodeProcessed()

sDict = {
		  "users/total": "users",
		  "users/online": "users",
		  "memory/virtual": "bytes",
		  "memory/real": "bytes",
		  "cpu/percent": "percent",
		  "cpu/time": "seconds"
		  }

def iqStatsHandler(cl, iq):
	jidToStr = iq.getTo()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if iType == "get" and jidToStr == TransportID:
		QueryPayload = list()
		if not IQChildren:
			for key in sDict.keys():
				Node = xmpp.Node("stat", {"name": key})
				QueryPayload.append(Node)
		else:
			users = calcStats()
			shell = os.popen("ps -o vsz,rss,%%cpu,time -p %s" % os.getpid()).readlines()
			memVirt, memReal, cpuPercent, cpuTime = shell[1].split()
			stats = {"users": users, "bytes": [memVirt, memReal], 
					 "percent": [cpuPercent], "seconds": [cpuTime]}
			for Child in IQChildren:
				if Child.getName() != "stat":
					continue
				name = Child.getAttr("name")
				if name in sDict:
					attr = sDict[name]
					value = stats[attr].pop(0)
					Node = xmpp.Node("stat", {"units": attr})
					Node.setAttr("name", name)
					Node.setAttr("value", value)
					QueryPayload.append(Node)
		if QueryPayload:
			result.setQueryPayload(QueryPayload)
			Sender(cl, result)

def iqDiscoHandler(cl, iq):
	jidFromStr = iq.getFrom().getStripped()
	jidToStr = iq.getTo().getStripped()
	iType = iq.getType()
	ns = iq.getQueryNS()
	Node = iq.getTagAttr("query", "node")
	if iType == "get":
		if not Node and jidToStr == TransportID:
			QueryPayload = []
			result = iq.buildReply("result")
			QueryPayload.append(xmpp.Node("identity", IDentifier))
			if ns == xmpp.NS_DISCO_INFO:
				for key in TransportFeatures:
					xNode = xmpp.Node("feature", {"var": key})
					QueryPayload.append(xNode)
				result.setQueryPayload(QueryPayload)
			elif ns == xmpp.NS_DISCO_ITEMS:
				QueryPayload.append(xmpp.Node("identity", IDentifier))
				result.setQueryPayload(QueryPayload)
			Sender(cl, result)
	raise xmpp.NodeProcessed()

def iqGatewayHandler(cl, iq):
	jidTo = iq.getTo()
	iType = iq.getType()
	jidToStr = jidTo.getStripped()
	IQChildren = iq.getQueryChildren()
	if jidToStr == TransportID:
		result = iq.buildReply("result")
		if iType == "get" and not IQChildren:
			query = xmpp.Node("query", {"xmlns": xmpp.NS_GATEWAY})
			query.setTagData("desc", "Enter phone number")
			query.setTag("prompt")
			result.setPayload([query])

		elif IQChildren and iType == "set":
			phone = ""
			for node in IQChildren:
				if node.getName() == "prompt":
					phone = node.getData()
					break
			if phone:
				xNode = xmpp.simplexml.Node("prompt")
				xNode.setData(phone[0])
				result.setQueryPayload([xNode])
		else:
			raise xmpp.NodeProcessed()
		Sender(cl, result)

def vCardGetPhoto(url, encode = True):
	try:
		opener = urllib.urlopen(url)
		data = opener.read()
		if data and encode:
			data = data.encode("base64")
		return data
	except IOError:
		pass
	except:
		crashLog("vcard.getPhoto")

def iqVcardBuild(tags):
	vCard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			binVal = vCard.setTag("PHOTO")
			binVal.setTagData("BINVAL", vCardGetPhoto(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard


DESC = _("© simpleApps, 2013."\
	   "\nYou can support developing of any project"\
	   " via donation by WebMoney:"\
	   "\nZ405564701378 | R330257574689.")
ProblemReport = _("If you found any problems, please contact us:\n"\
				"http://github.com/mrDoctorWho/vk4xmpp • xmpp:simpleapps@conference.jabber.ru")

def iqVcardHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	iType = iq.getType()
	result = iq.buildReply("result")
	if iType == "get":
		if jidToStr == TransportID:
			vcard = iqVcardBuild({"NICKNAME": "VK4XMPP Transport",
								  "DESC": DESC,
								  "PHOTO": "http://simpleApps.ru/vk4xmpp.png",
								  "URL": "http://simpleapps.ru"})
			result.setPayload([vcard])

		elif jidFromStr in Transport:
			Class = Transport[jidFromStr]
			Friends = Class.vk.getFriends("screen_name,photo_200_orig")
			if Friends:
				id = vk2xmpp(jidToStr)
				if id in Friends.keys():
					name = Friends[id]["name"]
					photo = Friends[id]["photo"]
					vCard = iqVcardBuild({"NICKNAME": name, "PHOTO": photo, "URL": "http://vk.com/id%s" % id,
										  "DESC": _("Contact uses VK4XMPP Transport\n%s") % DESC})
					result.setPayload([vCard])
				else:
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("User is not your friend."))
			else:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is null."))
		else:
			result = iqBuildError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
	else:
		raise xmpp.NodeProcessed()
	Sender(cl, result)


def updateTransportsList(user, add=True): #$
	global lengthOfTransportsList
	if add and user not in TransportsList:
		TransportsList.append(user)
	elif user in TransportsList:
		TransportsList.remove(user)
	length = len(TransportsList)
	if length > lengthOfTransportsList:
		start = lengthOfTransportsList
		lengthOfTransportsList += SLICE_STEP
		end = lengthOfTransportsList
		threadRun(hyperThread, (start, end), "updateTransportsList")
	elif length <= lengthOfTransportsList - SLICE_STEP:
		lengthOfTransportsList -= SLICE_STEP

def wFile(filename, data):
	with open(filename, "w") as file:
		file.write(data)

def rFile(filename):
	with open(filename, "r") as file:
		return file.read()

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
					time.sleep(2)
					os.kill(oldPid, 9)
				except OSError:
					pass
				Print("%d killed.\n" % oldPid, False)
	wFile(pidFile, str(nowPid))
	return True

def hyperThread(start, end):
	while True:
		slice = TransportsList[start:end]
		if not slice:
			break
		cTime = time.time()
		for user in slice:
			if cTime - user.last_activity < USER_CONSIDERED_ACTIVE_IF_LAST_ACTIVITY_LESS_THAN \
			or cTime - user.last_udate > MAX_ROSTER_UPDATE_TIMEOUT:
				user.last_udate = time.time() # cTime
				friends = user.vk.getFriends()
				if friends != user.friends:
					for uid in friends:
						if uid in user.friends:
							if user.friends[uid]["online"] != friends[uid]["online"]:
								jid = vk2xmpp(uid)
								pType = "unavailable" if not friends[uid]["online"] else None
								Sender(user.cl, xmpp.protocol.Presence(user.jUser, pType, frm=jid))
					user.friends = friends
				user.sendMessages()
				#?
		time.sleep(ROSTER_UPDATE_TIMEOUT)

def WatcherMsg(text):
	for watch_jid in WatcherList:
		msgSend(Component, watch_jid, text, TransportID)

def main():
	Counter = [0, 0]
	getPid() and initDatabase(DatabaseFile)
	globals()["Component"] = xmpp.Component(Host, debug = DEBUG_XMPPPY)
	Print("\n#-# Connecting: ", False)
	if not Component.connect((Server, Port)):
		Print("fail.\n", False)
		crashLog("main.connect")
	else:
		Print("ok.\n", False)
		Print("#-# Auth: ", False)
		if not Component.auth(TransportID, Password):
			Print("fail.\n", False)
		else:
			Print("ok.\n", False)
			Print("#-# Initializing users", False)
			with Database(DatabaseFile) as db:
				users = db("select * from users").fetchall()
				for user in users:
					jid, phone = user[:2]
					Transport[jid] = tUser(Component, (phone, None), jid)
					try:
						if Transport[jid].connect():
							TransportsList.append(Transport[jid])
							if DefaultStatus == 1: # 1 — online, 0 — offline
								Transport[jid].init()
							Print(".", False)
							Counter[0] += 1
						else:
							Print("!", False)
							Counter[1] += 1
							crashLog("main.connect", 0, False)
							msgSend(Component, jid, _("Auth failed! Please register again. This incident will be reported."), TransportID)
					except KeyboardInterrupt:
						exit()
					except:
						crashLog("main.init")
						continue
			Print("\n#-# Connected %s/%s users." % (str(Counter[0]), len(TransportsList)))
			if Counter[1]:
				Print("#-# Failed to connect %s users." % str(Counter[1]))

			globals()["lengthOfTransportsList"] = int(ceil(float(len(TransportsList)) / SLICE_STEP) * SLICE_STEP)

			Component.RegisterHandler("iq", iqHandler)
			Component.RegisterHandler("presence", prsHandler)
			Component.RegisterHandler("message", msgHandler)
			Component.RegisterDisconnectHandler(lambda: crashLog("main.Disconnect"))
			Component.RegisterDefaultHandler(lambda x, y: None)

			for start in xrange(0, lengthOfTransportsList, SLICE_STEP):
				end = start + SLICE_STEP
				threadRun(hyperThread, (start, end), "main.init-%d" % start)

			Print("\n#-# Finished.")

def exit(signal = None, frame = None): 	# LETS BURN CPU AT LAST TIME!
	status = "Shutting down by %s" % ("SIGTERM" if signal else "KeyboardInterrupt")
	Print("#! %s" % status, False)
	Presence = xmpp.protocol.Presence(None, "unavailable", frm = TransportID)
	Presence.setStatus(status)
	for Class in TransportsList:
		Presence.setTo(Class.jUser)
		Sender(Component, Presence)
		friends = Class.friends
		if friends:
			for id in friends:
				jid = vk2xmpp(id)
				Presence.setFrom(jid)
				Sender(Component, Presence)
				Print(".", False)
	Print("\n")
	try:
		os.remove(pidFile)
	except:
		pass
	os._exit(1)

if __name__ == "__main__":
	signal.signal(signal.SIGTERM, exit)
	main()
	Errors = 0

	while True:
		try:
			Component.iter(6)
		except KeyboardInterrupt:
			exit()
		except IOError:
			os.execl(sys.execute)
		except:
			if Errors > 10:
				exit()
			Errors += 1
			crashLog("Component.Process")
			continue
