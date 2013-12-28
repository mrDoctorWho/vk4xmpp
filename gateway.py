#!/usr/bin/env python2
# coding: utf-8

# vk4xmpp gateway, v1.9
# © simpleApps, 01.08.2013
# Program published under MIT license.

import re, os, sys, time, signal, socket, logging, threading
from hashlib import sha1
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

## xmpppy.
import xmpp

## other.
from itypes import Database
from webtools import *
from writer import *
from stext import *
from stext import _

import vkApi as api

Transport = {}
TransportsList = []
WatcherList = []
WhiteList = []
jidToID = {}
unAllowedChars = [unichr(x) for x in xrange(32) if x not in (9, 10, 13)] + [unichr(57003)]

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
except:
	Print("#! Error while loading config file:")
	wException()
	exit()

setVars(DefLang, __file__)


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
	revNumber, rev = 131, 0
	shell = os.popen("git describe --always && git log --pretty=format:''").readlines()
	if shell:
		revNumber, rev = len(shell), shell[0]
	return "#%s-%s" % (revNumber, rev)

OS = "{0} {2:.16} [{4}]".format(*os.uname())
Python = "{0} {1}.{2}.{3}".format(sys.subversion[0], *sys.version_info)
Revision = gatewayRev()

Handlers = {"msg01": [], "msg02": []}

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


escapeName = re.compile(u"[^-0-9a-zа-яёë\._\'\ ]", re.IGNORECASE | re.UNICODE | re.DOTALL).sub
escapeMsg = re.compile("|".join(unAllowedChars)).sub
require = lambda name: os.path.exists("extensions/%s.py" % name)

class VKLogin(object):

	def __init__(self, number, password = None, jidFrom = None):
		self.number = number
		self.password = password
		self.Online = False
		self.jidFrom = jidFrom
		logger.debug("VKLogin.__init__ with number:%s from jid:%s" % (number, jidFrom))

	def auth(self, token = None):
		logger.debug("VKLogin.auth %s token" % ("with" if token else "without"))
		try:
			self.engine = api.APIBinding(self.number, self.password, token = token)
			self.checkData()
		except api.AuthError as e:
			logger.error("VKLogin.auth failed with error %s" % e.message)
			return False
		except:
			crashLog("VKLogin.auth")
		logger.debug("VKLogin.auth completed")
		self.Online = True
		return self.Online

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
				raise api.tokenError("Token for user %s invalid: " % (self.jidFrom, self.engine.token))
		else:
			logger.error("VKLogin.checkData: no token and password for jid:%s" % self.jidFrom)
			raise api.TokenError("%s, Where are your token?" % self.jidFrom)

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
				logger.error("VKLogin: running captcha challenge for %s" % self.jidFrom)
				self.captchaChallenge()
			except api.NotAllowed:
				if self.engine.lastMethod[0] == "messages.send":
					msgSend(Component, self.jidFrom, _("You're not allowed to perform this action."), vk2xmpp(args.get("user_id", TransportID)))
			except api.VkApiError as e:
				if e.message == "User authorization failed: user revoke access for this token.":
					try:
						Transport[self.jidFrom].deleteUser()
					except KeyError:
						pass
				elif e.message == "User authorization failed: invalid access_token.":
					msgSend(Component, self.jidFrom, _(e.message + " Please, register again"), TransportID)
				self.Online = False
				logger.error("VKLogin: apiError %s for user %s" % (e.message, self.jidFrom))
		return result

	def captchaChallenge(self):
		if self.engine.captcha:
			logger.debug("VKLogin: sending message with captcha to %s" % self.jidFrom)
			body = _("WARNING: VK sent captcha to you."
					 " Please, go to %s and enter text from image to chat."
					 " Example: !captcha my_captcha_key. Tnx") % self.engine.captcha["img"]
			msg = xmpp.Message(self.jidFrom, body, "chat", frm = TransportID)
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
			Presence = xmpp.protocol.Presence(self.jidFrom, frm = TransportID)
			Presence.setStatus(body)
			Presence.setShow("xa")
			Sender(Component, Presence)
		else:
			logger.error("VKLogin: captchaChallenge called without captcha for user %s" % self.jidFrom)

	def disconnect(self):
		logger.debug("VKLogin: user %s has left" % self.jidFrom)
		self.method("account.setOffline")
		self.Online = False

	def getToken(self):
		return self.engine.token

	def getFriends(self, fields = None):
		fields = fields or ["screen_name"]
		friendsRaw = self.method("friends.get", {"fields": ",".join(fields)}) or {} # friends.getOnline
		friendsDict = {}
		for friend in friendsRaw:
			uid = friend["uid"]
			name = escapeName("", u"%s %s" % (friend["first_name"], friend["last_name"]))
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
		self.rosterSet = None
		self.existsInDB = None
		self.lastStatus = None
		self.last_activity = time.time()
		self.last_udate = time.time()
		self.jidFrom = source
		self.resources = []
		self.chatUsers = {}
		self.vk = VKLogin(self.username, self.password, self.jidFrom)
		logger.debug("initializing tUser for %s" % self.jidFrom)
		with Database(DatabaseFile, Semaphore) as db:
			db("select * from users where jid=?", (self.jidFrom,))
			desc = db.fetchone()
			if desc:
				if not self.token or not self.password:
					logger.debug("tUser: %s exists in db. Using it." % self.jidFrom)
					self.existsInDB = True
					self.jidFrom, self.username, self.token, self.lastMsgID, self.rosterSet = desc
				elif self.password or self.token:
					logger.debug("tUser: %s exists in db. Will be deleted." % self.jidFrom)
					threadRun(self.deleteUser)

	def deleteUser(self, roster = False):
		logger.debug("tUser: deleting user %s from db." % self.jidFrom)
		with Database(DatabaseFile) as db:
			db("delete from users where jid=?", (self.jidFrom,))
			db.commit()
		self.existsInDB = False
		if roster and self.friends:
			logger.debug("tUser: deleting me from %s roster" % self.jidFrom)
			for id in self.friends.keys():
				jid = vk2xmpp(id)
				self.sendPresence(self.jidFrom, jid, "unsubscribe")
				self.sendPresence(self.jidFrom, jid, "unsubscribed")
			self.vk.Online = False
		if self.jidFrom in Transport:
			del Transport[self.jidFrom]
			try:
				updateTransportsList(self, False)
			except NameError:
				pass

	def msg(self, body, uID, mType = "user_id"):
		try:
			self.last_activity = time.time()
			Message = self.vk.method("messages.send", {mType: uID, "message": body, "type": 0})
		except:
			crashLog("messages.send")
			Message = False
		return Message

	def connect(self):
		logger.debug("tUser: connecting %s" % self.jidFrom)
		self.auth = False
		try:
			self.auth = self.vk.auth(self.token)
			logger.debug("tUser: auth=%s for %s" % (self.auth, self.jidFrom))
		except api.CaptchaNeeded:
			self.rosterSubscribe()
			self.vk.captchaChallenge()
			return True
		except api.TokenError as e:
			if e.message == "User authorization failed: user revoke access for this token.":
				self.deleteUser()
			elif e.message == "User authorization failed: invalid access_token.":
				msgSend(Component, self.jidFrom, _(e.message + " Please, register again"), TransportID)
			self.vk.Online = False
		except:
			crashLog("tUser.Connect")
			return False

		if self.auth and self.vk.getToken():
			logger.debug("tUser: updating db for %s because auth done " % self.jidFrom)
			if not self.existsInDB:
				with Database(DatabaseFile, Semaphore) as db:
					db("insert into users values (?,?,?,?,?)", (self.jidFrom, self.username,
						self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Database(DatabaseFile, Semaphore) as db:
					db("update users set token=? where jid=?", (self.vk.getToken(), self.jidFrom))
			try:
				self.UserID = self.vk.method("users.get")[0]["uid"]
			except (KeyError, TypeError):
				self.UserID = 0

			jidToID[self.UserID] = self.jidFrom
			self.friends = self.vk.getFriends()
			self.vk.Online = True
		if not UseLastMessageID:
			self.lastMsgID = 0
		return self.vk.Online

	def init(self, force = False, send = True):
		logger.debug("tUser: called init for user %s" % self.jidFrom)
		self.friends = self.vk.getFriends()
		if self.friends and not self.rosterSet or force:
			logger.debug("tUser: calling subscribe with force:%s for %s" % (force, self.jidFrom))
			self.rosterSubscribe(self.friends)
		if send: self.sendInitPresence()

	def sendPresence(self, target, jidFrom, pType = None, nick = None, reason = None):
		Presence = xmpp.Presence(target, pType, frm = jidFrom, status = reason)
		if nick:
			Presence.setTag("nick", namespace = xmpp.NS_NICK)
			Presence.setTagData("nick", nick)
		time.sleep(0.001)
		Sender(Component, Presence)

	def sendInitPresence(self):
		self.friends = self.vk.getFriends() ## too too bad way to do it again. But it's a guarantee of the availability of friends.
		logger.debug("tUser: sending init presence to %s (friends %s)" %\
					(self.jidFrom, "exists" if self.friends else "empty"))
		for uid, value in self.friends.iteritems():
			if value["online"]:
				self.sendPresence(self.jidFrom, vk2xmpp(uid), None, value["name"])
		self.sendPresence(self.jidFrom, TransportID, None, IDentifier["name"])

	def sendOutPresence(self, target, reason = None):
		pType = "unavailable"
		logger.debug("tUser: sending out presence to %s" % self.jidFrom)
		for uid in self.friends.keys() + [TransportID]:
			self.sendPresence(target, vk2xmpp(uid), "unavailable", reason = reason)

	def rosterSubscribe(self, dist = None):
		dist = dist or {}
		for uid, value in dist.iteritems():
			self.sendPresence(self.jidFrom, vk2xmpp(uid), "subscribe", value["name"])
			time.sleep(0.2)
		self.sendPresence(self.jidFrom, TransportID, "subscribe", IDentifier["name"])
		if dist:
			self.rosterSet = True
			with Database(DatabaseFile, Semaphore) as db:
				db("update users set rosterSet=? where jid=?",
					(self.rosterSet, self.jidFrom))

	def getUserData(self, uid, fields = None):
		fields = fields or ["screen_name"]
		data = self.vk.method("users.get", {"fields": ",".join(fields), "user_ids": uid})
		if data:
			data = data.pop()
			data["name"] = escapeName("", u"%s %s" % (data["first_name"], data["last_name"]))
			del data["first_name"], data["last_name"]
		else:
			data = {}
			for key in fields:
				data[key] = "Unknown error when trying to get user data. We're so sorry."
		return data

	def sendMessages(self):
		messages = self.vk.getMessages(200, self.lastMsgID if UseLastMessageID else 0)
		if messages:
			messages = messages[1:]
			messages = sorted(messages, msgSort)
			if messages:
				read = list()
				self.lastMsgID = messages[-1]["mid"]
				for message in messages:
					read.append(str(message["mid"]))
					fromjid = vk2xmpp(message["uid"])
					body = uHTML(message["body"])
					iter = Handlers["msg01"].__iter__()
					for func in iter:
						try:
							result = func(self, message)
						except:
							result = None
							crashLog("handle.%s" % func.func_name)
						if result is None:
							for func in iter:
								apply(func, (self, message))
							break
						else:
							body += result
					else:
						msgSend(Component, self.jidFrom, escapeMsg("", body), fromjid, message["date"])
				self.vk.msgMarkAsRead(read)
				if UseLastMessageID:
					with Database(DatabaseFile, Semaphore) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.jidFrom))

	def tryAgain(self):
		logger.debug("calling reauth for user %s" % self.jidFrom)
		try:
			if not self.vk.Online:
				self.connect()
			self.init(True)
		except:
			crashLog("tryAgain")

msgSort = lambda Br, Ba: Br["date"] - Ba["date"]

def Sender(cl, stanza):
	try:
		cl.send(stanza)
		time.sleep(0.007)
	except KeyboardInterrupt:
		pass
	except IOError:
		logger.error("Panic: Couldn't send stanza: %s" % str(stanza))
	except:
		crashLog("Sender")

def msgSend(cl, jidTo, body, jidFrom, timestamp = 0):
	msg = xmpp.Message(jidTo, body, "chat", frm = jidFrom)
	if timestamp:
		timestamp = time.gmtime(timestamp)
		msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
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

DESC = _("© simpleApps, 2013."
	"\nYou can support developing of any project"
	" via donation by WebMoney:"
	"\nZ405564701378 | R330257574689.")

def updateTransportsList(user, add=True):
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

def hyperThread(start, end):
	while True:
		SliceOfLife = TransportsList[start:end]
		if not SliceOfLife:
			break
		cTime = time.time()
		for user in SliceOfLife:
			if user.vk.Online:
				if cTime - user.last_activity < USER_CONSIDERED_ACTIVE_IF_LAST_ACTIVITY_LESS_THAN \
				or cTime - user.last_udate > MAX_ROSTER_UPDATE_TIMEOUT:
					user.last_udate = time.time()
					friends = user.vk.getFriends() ## TODO: Maybe update only statuses? Again friends.getOnline...
					user.vk.method("account.setOnline")
					if friends != user.friends:
						for uid, value in friends.iteritems():
							if uid in user.friends:
								if user.friends[uid]["online"] != value["online"]:
									user.sendPresence(user.jidFrom, vk2xmpp(uid),
										None if value["online"] else "unavailable")
							else:
								user.rosterSubscribe({uid: friends[uid]})
						user.friends = friends
					user.sendMessages()
					del friends
		del SliceOfLife, cTime
		time.sleep(ROSTER_UPDATE_TIMEOUT)

def WatcherMsg(text):
	for jid in WatcherList:
		msgSend(Component, jid, text, TransportID)

def disconnectHandler(crash = True):
	if crash:
		crashLog("main.disconnect")
	try:
		Component.disconnect()
	except (NameError, AttributeError):
		pass
	Print("Reconnecting..."); time.sleep(5)
	os.execl(sys.executable, sys.executable, *sys.argv)

## Public transport's list: http://anakee.ru/vkxmpp
def makeMeKnown():
	if WhiteList:
		WhiteList.append("anon.anakee.ru")
	if TransportID.split(".")[1] != "localhost":
		RIP = api.RequestProcessor()
		RIP.post("http://anakee.ru/vkxmpp/hosts.php", {"add": TransportID})
		Print("#! Information about myself successfully published.")

def main():
	Counter = [0, 0]
	getPid()
	initDatabase(DatabaseFile)
	globals()["Component"] = xmpp.Component(Host, debug = DEBUG_XMPPPY)
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
			Print("#-# Initializing users", False)
			with Database(DatabaseFile) as db:
				users = db("select * from users").fetchall()
				for user in users:
					Sender(Component, xmpp.Presence(user[0], "probe", frm = TransportID))
			Print("\n#-# Finished.")
			if allowBePublic:
				makeMeKnown()

def exit(signal = None, frame = None):
	status = "Shutting down by %s" % ("SIGTERM" if signal == 15 else "SIGINT")
	Print("#! %s" % status, False)
	for Class in TransportsList:
		Class.sendPresence(Class.jidFrom, TransportID, "unavailable", reason = status)
		Print("." * len(Class.friends))
	Print("\n")
	try:
		os.remove(pidFile)
	except OSError:
		pass
	os._exit(1)

def garbageCollector():
	while True:
		gc.collect()
		time.sleep(60)

def loadSomethingMore(dir):
	for something in os.listdir(dir):
		execfile("%s/%s" % (dir, something), globals())

lengthOfTransportsList = 0
if __name__ == "__main__":
	threadRun(garbageCollector, (), "gc")
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
