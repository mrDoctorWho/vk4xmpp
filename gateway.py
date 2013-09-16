#!/usr/bin/python
# coding:utf-8

# vk4xmpp gateway, v1.7
# © simpleApps, 01.08.2013
# Program published under MIT license.

import os, sys, time, signal, urllib, socket, traceback, threading
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
					  xmpp.NS_RECEIPTS,
					  xmpp.NS_REGISTER,
					  xmpp.NS_GATEWAY,
					  xmpp.NS_VERSION,
					  xmpp.NS_CAPTCHA,
					  xmpp.NS_STATS,
					  xmpp.NS_VCARD,
					  xmpp.NS_DELAY,
					  xmpp.NS_PING,
					  xmpp.NS_LAST ]

IDentifier = { "type": "vk",
			   "category": "gateway",
			   "name": "VK4XMPP Transport" }

Semaphore = threading.Semaphore()

SLICE_STEP = 8
pidFile = "pidFile.txt"
Config = "Config.txt"
DefLang = "ru"
evalJID = ""

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

	def getFriends(self, fields = ["screen_name"]):
		friendsRaw = self.method("friends.get", {"fields": ",".join(fields)}) # friends.getOnline
		friendsDict = {}
		if friendsRaw:
			for friend in friendsRaw:
				uid = friend["uid"]
				name = u"%s %s" % (friend["first_name"], friend["last_name"])
				try:
					friendsDict[uid] = {"name": name, "online": friend["online"]}
					for key in fields:
						if key != "screen_name":
							friendsDict[uid][key] = friend.get(key)
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
		gc.collect()					# only this line is needed part of all transport code. ITS A MAGIC DUDE!
		if self.Online:					# config
			self.method("account.setOnline")
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
		self.lastStatus = False
		self.lastMsgID = False
		self.rosterSet = False
		self.existsInDB = False
		self.last_activity = time.time()
		self.jUser = source
		self.resources = []
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
				unSub = xmpp.Presence(self.jUser, "unsubscribe", frm = jid) 
				Sender(self.cl, unSub)
				unSubed = xmpp.Presence(self.jUser, "unsubscribed", frm = jid)
				Sender(self.cl, unSubed)
			self.vk.Online = False
		if self.jUser in Transport:
			del Transport[self.jUser]
			updateTransportsList(self, False)

	def msg(self, body, uID):
		try:
			self.last_activity = time.time()
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
			crashLog("tUser.Connect")
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
		self.friends = self.vk.getFriends()
		logger.debug("tUser: sending init presence to %s (friends %s)" % (self.jUser, "exists" if self.friends else "empty"))
		for uid in self.friends.keys():
			pType = None if self.friends[uid]["online"] else "unavailable"
			Presence = xmpp.protocol.Presence(self.jUser, pType, frm = vk2xmpp(uid))
			if not pType:
				Presence.setTag("nick", namespace = xmpp.NS_NICK)
				Presence.setTagData("nick", self.friends[uid]["name"])
			Sender(self.cl, Presence)
		Presence = xmpp.protocol.Presence(self.jUser, frm = TransportID)
		Sender(self.cl, Presence)

	def sendOutPresence(self, target):
		pType = "unavailable"
		logger.debug("tUser: sending out presence to %s" % self.jUser)
		Presence = xmpp.protocol.Presence(target, pType, frm = TransportID)
		Sender(self.cl, Presence)
		for uid in self.friends.keys():
			Presence.setFrom(vk2xmpp(uid))
			Sender(self.cl, Presence)

	def parseAttachments(self, msg):
		body = str()
		if msg.has_key("attachments"):
			if msg["body"]:
				body += _("\nAttachments:")
			attachments = msg["attachments"]
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
		return body

	def sendMessages(self):
		messages = self.vk.getMessages(None, 200, lastMsgID = self.lastMsgID) # messages.getLastActivity
		if messages:
			messages = messages[1:]
			messages = sorted(messages, lambda a, b: a["date"] - b["date"])
			if messages:
				self.lastMsgID = messages[-1]["mid"]
				read = list()
				for message in messages:
					read.append(str(message.get("mid", 0)))
					fromjid = vk2xmpp(message["uid"])
					body = uHTML(message["body"])
					body += self.parseAttachments(message)
					if message.has_key("fwd_messages"):
						body += _("\nForward messages:")
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
								name = self.friends[idFrom]["name"]
							body += "\n[%s] <%s> %s" % (date, name, fwdBody)
							body += self.parseAttachments(fwd)
					msgSend(self.cl, self.jUser, body, fromjid, message["date"])
				self.vk.msgMarkAsRead(read)
				if UseLastMessageID:
					with Database(DatabaseFile, Semaphore) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.jUser))

	def rosterSubscribe(self, dist = {}):
		Presence = xmpp.Presence(self.jUser, "subscribe")
		Presence.setTag("nick", namespace = xmpp.NS_NICK)
		for id in dist.keys():
			nickName = dist[id]["name"]
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
		time.sleep(0.0001)
	except IOError:
		logger.error("Panic: Couldn't send stanza: %s" % str(stanza))
	except:
		crashLog("Sender")

def msgSend(cl, jidTo, body, jidFrom, timestamp = 0):
	msg = xmpp.Message(jidTo, body, "chat", frm = jidFrom)
	if timestamp:
		gmTime = time.gmtime(timestamp)
		strTime = time.strftime("%Y-%m-%dT%H:%M:%SZ", gmTime)
		msg.setTimestamp(strTime)
	Sender(cl, msg)

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

DESC = _("© simpleApps, 2013."\
	   "\nYou can support developing of any project"\
	   " via donation by WebMoney:"\
	   "\nZ405564701378 | R330257574689.")
ProblemReport = _("If you found any problems, please contact us:\n"\
				"http://github.com/mrDoctorWho/vk4xmpp • xmpp:simpleapps@conference.jabber.ru")

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
	return True

def hyperThread(start, end):
	while True:
		slice = TransportsList[start:end]
		if not slice:
			break
		cTime = time.time()
		for user in slice:
			if user.vk.Online: 			# TODO: delete user from memory when he offline
				if cTime - user.last_activity < USER_CONSIDERED_ACTIVE_IF_LAST_ACTIVITY_LESS_THAN \
				or cTime - user.last_udate > MAX_ROSTER_UPDATE_TIMEOUT:
					user.last_udate = time.time() # cTime
					friends = user.vk.getFriends()
					if friends != user.friends:
						for uid in friends:
							if uid in user.friends:
								if user.friends[uid]["online"] != friends[uid]["online"]:
									jid = vk2xmpp(uid)
									pType = None if friends[uid]["online"] else "unavailable"
									Sender(user.cl, xmpp.protocol.Presence(user.jUser, pType, frm=jid))
							else:
								user.rosterSubscribe({uid: friends[uid]})
						user.friends = friends
					user.sendMessages()
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
							msgSend(Component, jid, _("Auth failed! If this error repeated, please register again. This incident will be reported."), TransportID)
					except KeyboardInterrupt:
						exit()
					except:
						crashLog("main.init")
						continue
			Print("\n#-# Connected %d/%d users." % (Counter[0], len(TransportsList)))
			if Counter[1]:
				Print("#-# Failed to connect %d users." % Counter[1])

			globals()["lengthOfTransportsList"] = int(ceil(float(len(TransportsList)) / SLICE_STEP) * SLICE_STEP)

			Component.RegisterHandler("iq", iqHandler)
			Component.RegisterHandler("presence", prsHandler)
			Component.RegisterHandler("message", msgHandler)
			Component.RegisterDisconnectHandler(lambda: crashLog("main.Disconnect"))

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
	except OSError:
		pass
	os._exit(1)

def garbageCollector():
	while True:
		gc.collect()
		time.sleep(10)

def loadHandlers():
	for handler in os.listdir("handlers"):
		execfile("handlers/%s" % handler, globals())

if __name__ == "__main__":
	threadRun(garbageCollector, (), "gc")
	signal.signal(signal.SIGTERM, exit)
	loadHandlers()
	main()
	Errors = 0

	while True:
		try:
			Component.iter(4)
		except KeyboardInterrupt:
			exit()
		except xmpp.StreamError:
			crashLog("Component.iter")
			pass
		except IOError:
			os.execl(sys.executable, sys.executable, sys.argv[0])
		except:
			if Errors > 10:
				exit()
			Errors += 1
			crashLog("Component.iter")
			continue
