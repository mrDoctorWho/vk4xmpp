#!/usr/bin/python
# coding:utf-8

# vk4xmpp gateway, v1.3
# © simpleApps, 01.08.2013
# Program published under MIT license.

import os, sys, time, signal, urllib, socket, traceback, threading
from math import ceil
if not hasattr(sys, "argv") or not sys.argv[0]:
	sys.argv = ["."]

try:
	__file__ = os.path.abspath(sys.argv[0])
	os.chdir(os.path.dirname(__file__))
except OSError:
	print "#! Incorrect launch!"
	time.sleep(6)

sys.path.insert(0, "library.zip")
reload(sys).setdefaultencoding("utf-8")
socket.setdefaulttimeout(10)

import gc
gc.enable()

## xmpppy.
import xmpp

## other.
from itypes import Database, Number
from writer import *
import vk_api as api

Transport = {}
TransportsList = []
TransportFeatures = [ xmpp.NS_DISCO_INFO,
					  xmpp.NS_DISCO_ITEMS,
		#			  xmpp.NS_STATS, # later
					  xmpp.NS_VCARD, 
					  xmpp.NS_REGISTER,
					  xmpp.NS_GATEWAY ]

IDentifier = {"type": "vk",
			  "category": "gateway",
			  "name": "VK4XMPP Transport"}

Semaphore = threading.Semaphore()

SLICE_STEP = 8
pidFile = "pidFile.txt"
Config = "Config.txt"
if os.path.exists(Config):
	try:
		execfile(Config)
		Print("#-# Config loaded successfully.")
	except:
		crashLog("config.load")
else:
	Print("#-# Config file doesn't exists.")

def initDatabase(filename):
	if not os.path.exists(filename):
		with Database(filename) as db:
			db("create table users (jid text, username text, token text, lastMsgID integer, rosterSet bool)")
			db.commit()
	return True

def crashLog(name, text = 0, fixMe = True):
	if fixMe:
		fixme(name)
	try:
		File = "crash/%s.txt" % name
		if not os.path.exists("crash"): 
			os.makedirs("crash")
		with open(File, "a", 0) as file:
			file.write(time.strftime("| %d.%m.%Y (%H:%M:%S) |\n"))
			wException(None, file)
			if text:
				file.write(text)
	except:
		fixme("crashlog")
		wException(None, sys.stdout)

class CaptchaNeeded(Exception):
	pass

class VKLogin(object):

	def __init__(self, number, password = None):
		self.number = number
		self.password = password
		self.Online = False
		self.captcha = {}
		self.lastMethod = None

	def auth(self, token = None):
		try:
			self.engine = api.VkApi(self.number, self.password, token = token)
		except (ValueError, api.authError):
			return False
		self.Online = True
		self.onlineMe(900)
		return self.Online

	def method(self, method, values = {}):
		if self.Online:
			try:
				if "key" in self.captcha:
					values["captcha_key"] = self.captcha["key"]
					values["captcha_sid"] = self.captcha["sid"]
					self.captcha = {}
				self.lastMethod = (method, values)
				return self.engine.method(method, values)
			except api.apiError as json:
				json = json.message
				if "captcha_sid" in json:
					self.captcha = {"sid": json["captcha_sid"], "img": json["captcha_img"]}
					raise CaptchaNeeded("Enter it. Tnx.")

	def retry(self): # it will be useful in some methods f.e. markAsRead, messages.send
		try: 
			if self.lastMethod: 
				return self.method(*self.lastMethod)
		except:
			pass # WARN

	def disconnect(self):
		if self.Online:
			self.method("account.setOffline")
			self.Online = False

	def getToken(self):
		if not self.Online:
			token = "nil_token"
		return self.engine.token

	def getFriends(self, fields = "screen_name"):
		friendsRaw = self.method("friends.get", {"fields": fields}) # friends.getOnline
		friendsDict = {}
		if friendsRaw:
			for friend in friendsRaw:
				id = friend["uid"]
				name = " ".join([friend["first_name"], friend["last_name"]])
				try:
					friendsDict[id] = {"name": name, "online": friend["online"]}
					friendsDict[id]["photo"] = friend.get("photo_200_orig", URL_VCARD_NO_IMAGE)
				except KeyError:
					continue
					crashLog("vk.getFriend")
		else:
			crashLog("vk.getFriendsRaw")
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
		if data:
			self.username, self.password = data
		self.cl = cl
		self.token = None
		self.friends = None
		self.lastMsgID = None
		self.rosterSet = None
		self.existsInDB = None
		self.last_activity = time.time()
		self.vk = VKLogin(self.username, self.password)
		if len(source) == 2:							# Is it 
			self.fullJID, self.jUser = source			# really
		else:
			self.jUser = source							# needed?
	
		with Semaphore:
			with Database(DatabaseFile) as db:
				base = db("select * from users where jid=?", (self.jUser,))
				desc = db.fetchone()
				if desc and not self.password:
					self.existsInDB = True
					self.jUser, self.username, self.token, \
						self.lastMsgID, self.rosterSet = desc
				elif desc and data:
					self.deleteUser()

	def deleteUser(self, roster = False):
		with Database(DatabaseFile) as db:
			db("delete from users where jid=?", (self.jUser,))
			db.commit()
		if roster and self.friends:
			for id in self.friends.keys():
				jid = vk2xmpp(id)
				unSub = xmpp.Presence(self.fullJID, "unsubscribe", frm = jid)
				self.cl.send(unSub)
				unSubed = xmpp.Presence(self.fullJID, "unsubscribed", frm = jid)
				self.cl.send(unSubed)
			self.vk.Online = False
		updateTransportsList(self, False) #$
		try: 
			del Transport[self.jUser] #?
		except KeyError:
			pass

	def method(self, method, values = {}): 													# yep, i know that it func exists in self.vk, but
		try:
			return self.vk.method(method, values) 											# and i know that it makes transport some slower
		except CaptchaNeeded:																# but i should handle this exception!
			if self.vk.captcha:
				msgSend(self.cl, self.jUser, "WARNING: VK sent captcha to you. "\
					"Please, go to %s and then enter code from image here. "\
					"Example: !captcha megakey. Tnx." % self.vk.captcha["img"], TransportID) # And i hope you will understand it.

	def msg(self, body, uID):
		try:
			self.last_activity = time.time()
			self.method("account.setOnline")
			Message = self.method("messages.send", {"user_id": uID, "message": body, "type": 0})
		except:
			Message = False
		return Message

	def connect(self):
		auth = False
		try:
			auth = self.vk.auth(self.token)
		except api.tokenError:
			self.deleteUser()
		if auth:
			if not self.existsInDB:
				with Semaphore:
					with Database(DatabaseFile) as db:
						db("insert into users values (?,?,?,?,?)", (self.jUser, self.username, 
							self.vk.getToken(), self.lastMsgID, self.rosterSet))
			elif self.password:
				with Semaphore:
					with Database(DatabaseFile) as db:
						db("update users set token=? where jid=?", (self.vk.getToken(), self.jUser))
			self.friends = self.vk.getFriends()
			self.vk.Online = True
		return self.vk.Online

	def init(self):
		if not self.rosterSet and self.friends:
			self.roster(self.friends)
			self.rosterSet = True
			with Semaphore:
				with Database(DatabaseFile) as db:
					db("update users set rosterSet=? where jid=?", (self.rosterSet, self.jUser))
		self.sendInitPresence()
		self.sendMessages()

	def sendInitPresence(self):
		self.cl.send(xmpp.protocol.Presence(self.jUser, frm = TransportID))
		if self.friends:
			for uid in self.friends:
				jid = "%s@%s" % (uid, TransportID)
				pType = "unavailable" if not self.friends[uid]["online"] else None
				self.cl.send(xmpp.protocol.Presence(self.jUser, pType, frm = jid))

	def sendMessages(self):
		messages = self.vk.getMessages(None, 200, lastMsgID = self.lastMsgID) # messages.getLastActivity
		messages = messages[1:]
		messages = sorted(messages, lambda a, b: a["date"] - b["date"])
		if messages:
			self.lastMsgID = messages[-1]["mid"]
			read = list()
			for message in messages:
				read.append(str(message.get("mid", 0)))
				fromjid = "%s@%s" % (message["uid"], TransportID)
				body = message["body"].replace("<br>", "\n")
				msgSend(self.cl, self.jUser, body, fromjid, message["date"])
			self.vk.msgMarkAsRead(read)
			if UseLastMessageID:
				with Semaphore:
					with Database(DatabaseFile) as db:
						db("update users set lastMsgID=? where jid=?", (self.lastMsgID, self.jUser))

	def roster(self, dist):
		IQ = xmpp.Iq("set", to = self.fullJID, frm = TransportID) # jUser?
		Node = xmpp.Node("x", {"xmlns": xmpp.NS_ROSTERX})
		items = list()
		for id in dist.keys():
			jid = "%s@%s" % (id, TransportID)
			item = xmpp.Node("item", {"action": "add", "jid": jid, "name": dist[id]["name"]})
			items.append(item)
		items.append(xmpp.Node("item", {"action": "add", "jid": TransportID}))
		Node.setPayload(items)
		IQ.addChild(node = Node)
		self.cl.send(IQ)
	

def msgSend(cl, jidTo, body, jidFrom, timestamp = 0):
	msg = xmpp.Message(jidTo, body, "chat", frm = jidFrom)
	if timestamp:
		msg.setTimestamp(timestamp)
	cl.send(msg)

def msgRecieved(msg, jidFrom, jidTo):
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom)
		tag = answer.setTag("received", namespace = "urn:xmpp:receipts")
		tag.setAttr("id", msg.getID())
		answer.setFrom(jidTo)
		answer.setID(msg.getID())
		return answer

def msgHandler(cl, msg):
	pType = msg.getType()
	jidFrom = msg.getFrom()
	jidFromStr = jidFrom.getStripped()
	if jidFromStr in Transport:
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
						if Class.vk.captcha:
							Class.vk.captcha["key"] = args
							if Class.vk.retry():
								body = "Captcha valid."
								Class.vk.captcha = {}
							else:
								body = "Captcha invalid."
						else:
							body = "Not now. Ok?"
					else:
						body = "Incorrect command or args."
					answer = msgRecieved(msg, jidFrom, jidTo)
					msgSend(cl, jidFromStr, body, jidTo)
			else:
				uID = jidTo.getNode()
				vkMessage = Class.msg(body, uID)
				if vkMessage:
					answer = msgRecieved(msg, jidFrom, jidTo)
			if answer:
				cl.send(answer)
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
			if not Class.vk.Online:
				Class.vk.Online = True
				Class.vk.onlineMe()
			Class.sendInitPresence()

		elif pType == "unavailable":
			Class.vk.disconnect()

		elif pType == "subscribe":
			if jidToStr == TransportID:
				cl.send(xmpp.Presence(jidFromStr, "subscribed", frm = TransportID))
				cl.send(xmpp.Presence(jidFrom, frm = TransportID))
			else:
				cl.send(xmpp.Presence(jidFromStr, "subscribed", frm = jidTo))
				if Class.friends:
					id = vk2xmpp(jidToStr)
					if id in Class.friends:
						if Class.friends[id]["online"]:
							cl.send(xmpp.Presence(jidFrom, frm = jidTo))

def iqBuildError(stanza, error = None, text = None):
	if not error:
		error = xmpp.ERR_FEATURE_NOT_IMPLEMENTED
	error = xmpp.Error(stanza, error, True)
	if text:
		error.setTagData("error", text)
		errTag = error.getTag("error")
		errTag.setTagData("text", text)
	return error

def iqHandler(cl, iq):
	ns = iq.getQueryNS()
	if ns == xmpp.NS_REGISTER:
		iqRegisterHandler(cl, iq)
	elif ns == xmpp.NS_GATEWAY:
		iqGatewayHandler(cl, iq)
	elif ns in (xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS):
		iqDiscoHandler(cl, iq)
	else:
		Tag = iq.getTag("vCard")
		if Tag and Tag.getNamespace() == xmpp.NS_VCARD:
			iqVcardHandler(cl, iq)
		else:
			raise xmpp.NodeProcessed()

def iqRegisterHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	iType = iq.getType()
	fullJID = str(jidFrom)
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")

	if iType == "get" and jidToStr == TransportID and not IQChildren:
		instr = xmpp.Node("instructions")
		instr.setData("Enter phone number (like +71234567890) and password."\
			"\nNOTE: Your password will be NOT saved. \nTransport saves only API key.")
		phone = xmpp.Node("phone")
		password = xmpp.Node("password")
		result.setQueryPayload((instr, phone, password))

	elif iType == "set" and jidToStr == TransportID and IQChildren:
		Query = iq.getTag("query")
		if Query.getTag("phone") and Query.getTag("password"):
			phone = Query.getTagData("phone")
			password = Query.getTagData("password")
			if not phone:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "Phone incorrect.")
			if not password:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "Null password")
			else:
				user = tUser(cl, (phone, password), (fullJID, jidFromStr)) 
				if not user.connect(): 
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "Incorrect password!!!")
				else:
					try: 
						user.init()
					except:
						result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "Initialization failed")
					else:
						Transport[jidFromStr] = user
						updateTransportsList(Transport[jidFromStr]) #$
					
		elif Query.getTag("remove"): # Maybe exits a better way for it
			if jidFromStr in Transport:
				Class = Transport[jidFromStr]
				Class.fullJID = fullJID
				Class.deleteUser(True)
				result.setPayload([], add = 0)
		else:
			result = iqBuildError(iq, 0, "Feature not implemented.")
	cl.send(result)

def iqDiscoHandler(cl, iq):
	jidFromStr = iq.getFrom().getStripped()
	jidToStr = iq.getTo().getStripped()
	iType = iq.getType()
	ns = iq.getQueryNS()
	Node = iq.getTagAttr("query", "node")
	result = iq.buildReply("result")
	if iType == "get":
		if ns == xmpp.NS_DISCO_INFO:
			if not Node and jidToStr == TransportID:
				QueryPayload = []
				QueryPayload.append(xmpp.Node("identity", attrs = IDentifier))
				for key in TransportFeatures:
					xNode = xmpp.Node("feature", attrs = {"var": key})
					QueryPayload.append(xNode)	
				result.setQueryPayload(QueryPayload)
			cl.send(result)

def iqGatewayHandler(cl, iq):
	jidTo = iq.getTo()
	iType = iq.getType()
	jidToStr = jidTo.getStripped()
	IQChildren = iq.getQueryChildren()
	if jidToStr == TransportID:
		result = iq.buildReply("result")
		if iType == "get" and not IQChildren:
			query = xmpp.Node('query', attrs={'xmlns':xmpp.NS_GATEWAY})
			query.setTagData('desc', "Enter phone number")
			query.setTag('prompt')
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
		cl.send(result)

def vCardGetPhoto(url):
	try:
		opener = urllib.urlopen(url)
		data = opener.read()
		if data:
			data = data.encode("base64")
			return data
	except:
		crashLog("vcard.getPhoto")
		return ""

def iqVcardBuild(tags):
	vCard = xmpp.Node("vCard", attrs = {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			binVal = vCard.setTag("PHOTO")
			binVal.setTagData("BINVAL", vCardGetPhoto(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard


DESC = "© simpleApps, 2013."\
	   "\nYou can support developing of any project"\
	   " via donation by WebMoney:"\
	   "\nZ405564701378 | R330257574689."
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
								  "PHOTO": "http://simpleapps.ru/sa_logo2.png",
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
					vCard = iqVcardBuild({"NICKNAME": name, "PHOTO": photo,
										  "DESC": "Contact uses VK4XMPP Transport\n%s" % DESC})
					result.setPayload([vCard])
				else:
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "User is not your friend.")
			else:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "Your friend-list is null.")
		else:
			result = iqBuildError(iq, xmpp.ERR_REGISTRATION_REQUIRED, "You're not registered for this action.")
	else:
		raise xmpp.NodeProcessed()
	cl.send(result)


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
		threading.Thread(target = hyperThread, args = (start, end)).start()
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
					Print("%d killed.\n" % oldPid, False)
				except OSError:
					pass
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
								jid = "%s@%s" % (uid, TransportID)
								pType = "unavailable" if not friends[uid]["online"] else None
								user.cl.send(xmpp.protocol.Presence(user.jUser, pType, frm=jid))
					user.friends = friends			
				user.sendMessages()
				#?
		time.sleep(ROSTER_UPDATE_TIMEOUT)


def main():
	Counter = [Number(), Number()]
	getPid() and initDatabase(DatabaseFile)
	globals()["Component"] = xmpp.Component(Host, debug = True)
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
							Counter[0].plus()
						else:
							Print(jid)
							Print("!", False)
							Counter[1].plus()
							crashlog("main.connect", 0, False)
							msgSend(Component, jid, "Auth failed! Please register again. This incident will be reported.", TransportID)
					except:
						crashLog("main.init")
						continue
			Print("\n#-# Connected %s/%s users." % (str(Counter[0]), len(TransportsList)))
			if str(Counter[1]) != "0":
				Print("#-# Failed to connect %s users." % str(Counter[1]))

			globals()["lengthOfTransportsList"] = int(ceil(float(len(TransportsList)) / SLICE_STEP) * SLICE_STEP)

			for start in xrange(0, lengthOfTransportsList, SLICE_STEP):
				end = start + SLICE_STEP
				threading.Thread(target = hyperThread, args = (start, end)).start()

			Component.RegisterHandler("iq", iqHandler)
			Component.RegisterHandler("presence", prsHandler)
			Component.RegisterHandler("message", msgHandler)
			Component.RegisterDefaultHandler(lambda x, y: None)
			signal.signal(signal.SIGTERM, exit)
			Print("\n#-# Finished.")

def exit(signal = None, frame = None): 	# LETS BURN CPU AT LAST TIME!
	status = "Shutting down by %s" % ("SIGTERM" if signal else "KeyboardInterrupt")
	Print("#! %s" % status, False)
	Presence = xmpp.protocol.Presence(None, "unavailable", frm = TransportID)
	Presence.setStatus(status)
	for Class in TransportsList:
		Presence.setTo(Class.jUser)
		Component.send(Presence)
		friends = Class.friends
		if friends:
			for id in friends:
				jid = vk2xmpp(id)
				Presence.setFrom(jid)
				Component.send(Presence)
				Print(".", False)
	Print("\n")
	os._exit(1)

main()

Errors = 0
while True:
	try:
		Component.Process(1)
	except KeyboardInterrupt:
		exit()
	except:
		if Errors > 10:
			exit()
		Errors += 1
		crashLog("Component.Process")
		continue
