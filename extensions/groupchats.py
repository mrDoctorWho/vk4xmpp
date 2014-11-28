# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.
# File contains parts of code from 
# BlackSmith mark.1 XMPP Bot, © simpleApps 2011 — 2014.

if not require("attachments") or not require("forwarded_messages"):
	raise AssertionError("'groupchats' requires 'forwarded_messages'")

try:
	import mod_xhtml
except ImportError:
	mod_xhtml = None

def sendIQ(chat, attr, data, afrls, role, jidFrom, cb=None, args={}):
	stanza = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = xmpp.Node("query", {"xmlns": xmpp.NS_MUC_ADMIN})
	arole = query.addChild("item", {attr: data, afrls: role})
	stanza.addChild(node = query)
	sender(Component, stanza, cb, args)


def makeMember(chat, jid, jidFrom, cb=None, args={}):
	sendIQ(chat, "jid", jid, "affiliation", "member", jidFrom, cb, args)


def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to=chat, frm=jidFrom)
	x = xmpp.Node("x", {"xmlns": xmpp.NS_MUC_USER})
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node=x)
	sender(Component, invite)


def joinChat(chat, name, jidFrom):
	prs = xmpp.Presence("%s/%s" % (chat, name), frm=jidFrom)
	prs.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": Revision}, xmpp.NS_CAPS)
	sender(Component, prs)


def leaveChat(chat, jidFrom):
	prs = xmpp.Presence(chat, "unavailable", frm=jidFrom)
	sender(Component, prs)


def chatMessage(chat, text, jidFrom, subj=None, timestamp=0):
	message = xmpp.Message(chat, typ="groupchat")
	if timestamp:
		timestamp = time.gmtime(timestamp)
		message.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	if not subj:
		message.setBody(text)
	else:
		message.setSubject(text)
	message.setFrom(jidFrom)
	sender(Component, message)


def outgoingChatMessageHandler(self, vkChat):
	if not self.settings.groupchats:
		return None
	if vkChat.has_key("chat_id"):
		owner = vkChat.get("admin_id", "1")
		fromID = vkChat["uid"]
		chatID = vkChat["chat_id"]
		chatJID = "%s_chat#%s@%s" % (self.vk.userID, chatID, ConferenceServer)

		if not hasattr(self, "chats"):
			self.chats = {}

		if not self.vk.userID:
			logger.warning("groupchats: we didn't receive user id, trying again after 10 seconds (jid: %s)" % self.source)
			self.vk.getUserID()
			runThread(outgoingChatMessageHandler, (self, vkChat), delay=10)
			return None

		if chatJID not in self.chats:
			chat = self.chats[chatJID] = Chat(owner, chatID, chatJID, vkChat["title"], vkChat["date"], vkChat["chat_active"].split(","))
			chat.create(self)
		else:
			chat = self.chats[chatJID]

		## joining new people and make the old ones leave
		chat.update(self, vkChat)

		body = escape("", uHTML(vkChat["body"]))
		body += parseAttachments(self, vkChat)
		body += parseForwardedMessages(self, vkChat)
		if body:
			chatMessage(chatJID, body, vk2xmpp(fromID), None, vkChat["date"])
		return None
	return ""


class Chat(object):
	def __init__(self, owner, id, jid, topic, date, users=[]):
		self.id = id
		self.jid = jid
		self.owner = owner
		self.users = {}
		self.raw_users = users
		self.created = False
		self.invited = False
		self.topic = topic
		self.creation_date = date

	def create(self, user):	
		logger.debug("groupchats: creating %s. Users: %s; owner: %s (jid: %s)" % (self.jid, self.raw_users, self.owner, user.source))
		name = user.vk.getUserData(self.owner)["name"]
		self.users[TransportID] = {"name": name, "jid": TransportID}
		joinChat(self.jid, name, TransportID) ## we're joining to chat with the room owner's name to set the topic. That's why we have so many lines of code right here
		self.setConfig(self.jid, TransportID, False, self.onConfigSet, {"user": user}) ## executehandler?

	## TODO: Return chat object from the message
	def initialize(self, user, chat):
		if not self.users:
			vkChat = self.getVKChat(user, self.id)
			if vkChat:
				vkChat = vkChat[0]
			elif not self.invited:
				logger.error("groupchats: damn vk didn't answer to chat list request, starting timer to try again (jid: %s)" % user.source)
				runThread(self.initialize, (user, chat), delay=10)
				return False
			self.raw_users = vkChat.get("users")

		name = "@%s" % TransportID
		makeMember(chat, user.source, TransportID)
		if not self.invited:
			inviteUser(chat, user.source, TransportID, user.vk.getUserData(self.owner)["name"])
			self.invited = True
		logger.debug("groupchats: user has been invited to chat %s (jid: %s)" % (chat, user.source))
		chatMessage(chat, self.topic, TransportID, True, self.creation_date)
		joinChat(chat, name, TransportID) ## let's rename ourself
		self.users[TransportID] = {"name": name, "jid": TransportID}

	def update(self, userObject, vkChat):
		users = vkChat["chat_active"].split(",")
		for user in users:
			if not user in self.users:
				logger.debug("groupchats: user %s has joined the chat %s (jid: %s)" % (user, self.jid, userObject.source))
				jid = vk2xmpp(user)
				name = userObject.vk.getUserData(user)["name"]
				self.users[user] = {"name": name, "jid": jid}
				makeMember(self.jid, jid, TransportID)
				joinChat(self.jid, name, jid) 

		for user in self.users.keys():
			if not user in users and user != TransportID:
				logger.debug("groupchats: user %s has left the chat %s (jid: %s)" % (user, self.jid, userObject.source))
				del self.users[user]
				leaveChat(self.jid, vk2xmpp(user))
				if user == userObject.vk.userID:
					self.setConfig(self.jid, TransportID, exterminate=True) ## exterminate the chats when user leave conference or just go offline?

		topic = vkChat["title"]
		if topic != self.topic:
			chatMessage(self.jid, topic, TransportID, True)
			self.topic = topic
		self.raw_users = users

	def getVKChat(self, user, id):
		chats = user.vk.method("execute.getChats")
		return filter(lambda dict: dict.get("chat_id") == id, chats)

	@classmethod
	def setConfig(cls, chat, jidFrom, exterminate=False, cb=None, args={}):
		iq = xmpp.Iq("set", to=chat, frm=jidFrom)
		query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
		if exterminate:
			query.addChild("destroy")
		else:
			form = utils.buildDataForm(fields = [{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
											 {"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
											 {"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "0"},
											 {"var": "muc#roomconfig_whois", "value": "anyone"}], type="submit")
			query.addChild(node=form)
		sender(Component, iq, cb, args)

	def onConfigSet(self, cl, stanza, user):
		chat = stanza.getFrom().getStripped()
		if xmpp.isResultNode(stanza):
			logger.debug("groupchats: stanza \"result\" received from %s, continuing initialization (jid: %s)" % (chat, user.source))
			execute(self.initialize, (user, chat)) ## i don't trust VK so it's better to execute it
			self.created = True
		else:
			logger.error("groupchats: couldn't set room %s config (jid: %s)" % (chat, user.source))

	@classmethod
	def getParts(cls, source):
		node, domain = source.split("@")
		creator, id = node.split("_chat#")
		return (int(creator), int(id), domain)

	@classmethod
	def getUserObject(cls, source):
		user = None
		creator, id, domain = cls.getParts(source)
		if domain == ConferenceServer and creator: ## we will ignore zero-id
			jid = jidToID[creator]
			if jid in Transport:
				user = Transport[jid]
		return user


def incomingChatMessageHandler(msg):
	if msg.getType() == "groupchat":
		body = msg.getBody()
		destination = msg.getTo().getStripped()
		source = msg.getFrom().getStripped()
		if mod_xhtml:
			html = msg.getTag("html")
		else:
			html = None

		x = msg.getTag("x", {"xmlns": "http://jabber.org/protocol/muc#user"})
		if x and x.getTagAttr("status", "code") == "100":
			raise xmpp.NodeProcessed()

		if not msg.getTimestamp() and body and destination == TransportID:
			user = Chat.getUserObject(source)
			creator, id, domain = Chat.getParts(source)
			if user:
				if html and html.getTag("body"): ## XHTML-IM!
					logger.debug("groupchats: fetched xhtml image (jid: %s)" % source)
					try:
						xhtml = mod_xhtml.parseXHTML(user, html, source, source, "chat_id")
					except Exception:
						xhtml = False
					if xhtml:
						raise xmpp.NodeProcessed()
				user.vk.sendMessage(body, id, "chat_id")


def handleChatErrors(source, prs):
	## todo: leave on 401, 403, 405
	## and rejoin timer on 404, 503
	## is it safe by the way?
	destination = prs.getTo().getStripped()
	if prs.getType() == "error":
		code = prs.getErrorCode()
		nick = prs.getFrom().getResource()
		if source.split("@")[1] == ConferenceServer:
			user = Chat.getUserObject(source)
			if user and source in getattr(user, "chats", {}):
				chat = user.chats[source]
				if code == "409":
					id = vk2xmpp(destination)
					if id in chat.users:
						nick += "."
						if not chat.created and id == TransportID:
							chat.users[id]["name"] = nick
							chat.create(user)
						else:
							joinChat(source, nick, destination)
	# TODO:
	## Make user leave if he left when transport's user wasn't online
	## This could be done using jids or/and nicks lists. Completely unreliably as well as the groupchats realization itself
#	if prs.getStatusCode() == "110":
#		print prs.getJid()
#		print prs.getType()


def exterminateChat(user):
	chats = user.vk.method("execute.getChats")
	for chat in chats:
		Chat.setConfig("%s_chat#%s@%s" % (user.vk.userID, chat["chat_id"], ConferenceServer), TransportID, True)


if ConferenceServer:
	logger.info("extension groupchats is loaded")
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	registerHandler("msg01", outgoingChatMessageHandler)
	registerHandler("msg02", incomingChatMessageHandler)
	registerHandler("prs01", handleChatErrors)
	registerHandler("evt03", exterminateChat)

else:
	del incomingChatMessageHandler, outgoingChatMessageHandler, inviteUser, joinChat, chatMessage
