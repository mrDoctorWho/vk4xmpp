# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.
# File contains parts of code from 
# BlackSmith mark.1 XMPP Bot, © simpleApps 2011 — 2014.

if not require("attachments") or not require("forwardMessages"):
	raise

def IQSender(chat, attr, data, afrls, role, jidFrom):
	stanza = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = xmpp.Node("query", {"xmlns": xmpp.NS_MUC_ADMIN})
	arole = query.addChild("item", {attr: data, afrls: role})
	stanza.addChild(node = query)
	Sender(Component, stanza)

def member(chat, jid, jidFrom):
	IQSender(chat, "jid", jid, "affiliation", "member", jidFrom)

def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to=chat, frm=jidFrom)
	x = xmpp.Node("x", {"xmlns": xmpp.NS_MUC_USER})
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node=x)
	Sender(Component, invite)


## TODO: Set chatroom's name
def chatSetConfig(chat, jidFrom, exterminate=False):
	iq = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
	if exterminate:
		query.addChild("destroy")
	else:
		form = utils.buildDataForm(fields = [{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
										 {"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
										 {"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "1"},
										 {"var": "muc#roomconfig_whois", "value": "anyone"}])
		query.addChild(node=form)
	Sender(Component, iq)

def chatPresence(chat, name, jidFrom, type=None):
	prs = xmpp.Presence("%s/%s" % (chat, name), type, frm=jidFrom)
	prs.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": Revision}, xmpp.NS_CAPS)
	Sender(Component, prs)

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
	Sender(Component, message)

def outgoungChatMessageHandler(self, msg):
	if msg.has_key("chat_id"):
		idFrom = msg["uid"]
		owner = msg["admin_id"]
		_owner = vk2xmpp(owner)
		chatID = "%s_chat#%s" % (self.UserID, msg["chat_id"])
		chat = "%s@%s" % (chatID, ConferenceServer)
		users = msg["chat_active"].split(",")
		users.append(self.UserID)
		if not users: ## is it possible?
			logger.debug("groupchats: all users exterminated in chat: %s" % chat)
			if chat in self.chatUsers:
				chatPresence(chat, self.getUserData(owner)["name"], vk2xmpp(self.UserID), "unavailable")
				del self.chatUsers[chat]
			return None

		if chat not in self.chatUsers:
			logger.debug("groupchats: creating %s. Users: %s; owner: %s" % (chat, msg["chat_active"], owner))
			self.chatUsers[chat] = []
			for usr in (owner, self.UserID):
				chatPresence(chat, self.getUserData(usr)["name"], vk2xmpp(usr))
			chatSetConfig(chat, _owner)
			member(chat, self.source, _owner)
			inviteUser(chat, self.source, _owner, self.getUserData(owner)["name"])
			chatMessage(chat, msg["title"], _owner, True, msg["date"])
	
		for user in users:
			if not user in self.chatUsers[chat]:
				logger.debug("groupchats: user %s has joined the chat %s" % (user, chat))
				self.chatUsers[chat].append(user)
				uName = self.getUserData(user)["name"]
				user = vk2xmpp(user)
				member(chat, user, _owner)
				chatPresence(chat, uName, user)
		
		for user in self.chatUsers[chat]:
			if not user in users:
				logger.debug("groupchats: user %s has left the chat %s" % (user, chat))
				self.chatUsers[chat].remove(user)
				uName = self.getUserData(user)["name"]
				chatPresence(chat, uName, vk2xmpp(user), "unavailable")

		body = escape("", uHTML(msg["body"]))
		body += parseAttachments(self, msg)
		body += parseForwardMessages(self, msg)
		if body:
			chatMessage(chat, body, vk2xmpp(idFrom), None, msg["date"])
		return None
	return ""

def incomingChatMessageHandler(msg):
	if msg.getType() == "groupchat":
		body = msg.getBody()
		destination = msg.getTo().getStripped()
		source = msg.getFrom().getStripped()
		html = msg.getTag("html")
		x = msg.getTag("x", {"xmlns": "http://jabber.org/protocol/muc#user"})

		if x and x.getTagAttr("status", "code") == "100":
			raise xmpp.NodeProcessed()

		if not msg.getTimestamp() and body:
			Node, Domain = source.split("@")
			if Domain == ConferenceServer:
				destination = vk2xmpp(destination)
				if destination in jidToID:
					jid = jidToID[destination]
					if jid in Transport:
						user = Transport[jid]
						if html and html.getTag("body"): ## XHTML-IM!
							logger.debug("groupchats: fetched xhtml image from %s" % source)
							try:
								xhtml = xhtmlParse(user, html, source, source, "chat_id")
							except Exception:
								xhtml = False
							if xhtml:
								raise xmpp.NodeProcessed()
						user.msg(body, Node.split("#")[1], "chat_id")


def chatDestroy(user):
	chats = user.vk.method("execute.getChats")
	for chat in chats:
		chatSetConfig("%s_chat#%s@%s" % (user.UserID, chat["chat_id"], ConferenceServer), vk2xmpp(chat["admin_id"]), True)

if ConferenceServer:
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	Handlers["msg01"].append(outgoungChatMessageHandler)
	Handlers["msg02"].append(incomingChatMessageHandler)
	Handlers["evt03"].append(chatDestroy)

else:
	del incomingChatMessageHandler, outgoungChatMessageHandler, inviteUser, chatPresence, chatMessage
