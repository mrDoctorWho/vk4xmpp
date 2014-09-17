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

def sendIQ(chat, attr, data, afrls, role, jidFrom):
	stanza = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = xmpp.Node("query", {"xmlns": xmpp.NS_MUC_ADMIN})
	arole = query.addChild("item", {attr: data, afrls: role})
	stanza.addChild(node = query)
	sender(Component, stanza)

def makeMember(chat, jid, jidFrom):
	sendIQ(chat, "jid", jid, "affiliation", "member", jidFrom)

def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to=chat, frm=jidFrom)
	x = xmpp.Node("x", {"xmlns": xmpp.NS_MUC_USER})
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node=x)
	sender(Component, invite)


def setChatConfig(chat, jidFrom, exterminate=False):
	iq = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
	if exterminate:
		query.addChild("destroy")
	else:
		form = utils.buildDataForm(fields = [{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
										 {"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
										 {"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "0"},
										 {"var": "muc#roomconfig_whois", "value": "anyone"}])
		query.addChild(node=form)
	sender(Component, iq)

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

def outgoungChatMessageHandler(self, msg):
	if not self.settings.groupchats:
		return None
	if msg.has_key("chat_id"):
		fromID = msg["uid"]
		owner = msg["admin_id"]
		chatID = "%s_chat#%s" % (self.vk.userID, msg["chat_id"])
		chat = "%s@%s" % (chatID, ConferenceServer)
		users = msg["chat_active"].split(",")
		if not self.vk.userID:
			self.vk.getUserID()

		if chat not in self.chatUsers:
			logger.debug("groupchats: creating %s. Users: %s; owner: %s (jid: %s)" % (chat, msg["chat_active"], owner, self.source))
			self.chatUsers[chat] = []
			joinChat(chat, self.vk.getUserData(owner)["name"], TransportID)
			setChatConfig(chat, TransportID)
			makeMember(chat, self.source, TransportID)
			inviteUser(chat, self.source, TransportID, self.vk.getUserData(owner)["name"])
			logger.debug("groupchats: user has been invited to chat %s (jid: %s)" % (chat, self.source))
			chatMessage(chat, msg["title"], TransportID, True, msg["date"])
			joinChat(chat, IDENTIFIER["name"], TransportID)
	
		for user in users:
			if not user in self.chatUsers[chat]:
				logger.debug("groupchats: user %s has joined the chat %s (jid: %s)" % (user, chat, self.source))
				self.chatUsers[chat].append(user)
				uName = self.vk.getUserData(user)["name"]
				user = vk2xmpp(user)
				makeMember(chat, user, TransportID)
				joinChat(chat, uName, user)
		
		for user in self.chatUsers[chat]:
			if not user in users:
				logger.debug("groupchats: user %s has left the chat %s (jid: %s)" % (user, chat, self.source))
				self.chatUsers[chat].remove(user)
				uName = self.vk.getUserData(user)["name"]
				leaveChat(chat, vk2xmpp(user))
				if user == self.vk.userID:
					setChatConfig(chat, TransportID, exterminate=True)

		body = escape("", uHTML(msg["body"]))
		body += parseAttachments(self, msg)
		body += parseForwardedMessages(self, msg)
		if body:
			chatMessage(chat, body, vk2xmpp(fromID), None, msg["date"])
		return None
	return ""

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

		if not msg.getTimestamp() and body:
			Node, Domain = source.split("@")
			if Domain == ConferenceServer:
				id = int(Node.split("_")[0])
				if destination == TransportID and id:
					jid = jidToID[id]
					if jid in Transport:
						user = Transport[jid]
						if html and html.getTag("body"): ## XHTML-IM!
							logger.debug("groupchats: fetched xhtml image (jid: %s)" % source)
							try:
								xhtml = mod_xhtml.parseXHTML(user, html, source, source, "chat_id")
							except Exception:
								xhtml = False
							if xhtml:
								raise xmpp.NodeProcessed()
						user.vk.sendMessage(body, Node.split("#")[1], "chat_id")


def exterminateChat(user):
	chats = user.vk.method("execute.getChats")
	for chat in chats:
		setChatConfig("%s_chat#%s@%s" % (user.vk.userID, chat["chat_id"], ConferenceServer), TransportID, True)

if ConferenceServer:
	logger.debug("extension groupchats is loaded")
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	registerHandler("msg01", outgoungChatMessageHandler)
	registerHandler("msg02", incomingChatMessageHandler)
	registerHandler("evt03", exterminateChat)

else:
	del incomingChatMessageHandler, outgoungChatMessageHandler, inviteUser, joinChat, chatMessage
