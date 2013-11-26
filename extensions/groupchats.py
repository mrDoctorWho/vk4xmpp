# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.
# File contains parts of code from 
# BlackSmith mark.1 XMPP Bot, © simpleApps 2011 — 2013.

if not require("attachments") or not require("forwardMessages"):
	raise

def IQSender(chat, attr, data, afrls, role, jidFrom):
	stanza = xmpp.Iq("set", to = chat, frm = jidFrom)
	query = xmpp.Node("query")
	query.setNamespace(xmpp.NS_MUC_ADMIN)
	arole = query.addChild("item", {attr: data, afrls: role})
	stanza.addChild(node = query)
	Sender(Component, stanza)

def member(chat, jid, jidFrom):
	IQSender(chat, "jid", jid, "affiliation", "member", jidFrom)

def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to = chat, frm = jidFrom)
	x = xmpp.Node("x")
	x.setNamespace(xmpp.NS_MUC_USER)
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node = x)
	Sender(Component, invite)

def groupchatSetConfig(chat, jidFrom, exterminate = False):
	iq = xmpp.Iq("set", to = chat, frm = jidFrom, xmlns = "jabber:component:accept")
	query = iq.addChild("query", namespace = xmpp.NS_MUC_OWNER)
	if exterminate:
		query.addChild("destroy")
	else:
		form = xmpp.DataForm("submit")
		field = form.setField("FORM_TYPE")
		field.setType("hidden")
		field.setValue(xmpp.NS_MUC_ROOMCONFIG)
		membersonly = form.setField("muc#roomconfig_membersonly")
		membersonly.setType("boolean")
		membersonly.setValue("1")
		whois = form.setField("muc#roomconfig_whois")
		whois.setValue("anyone")
		query.addChild(node = form)
	Sender(Component, iq)

def groupchatPresence(chat, name, jidFrom, type = None):
	prs = xmpp.Presence("%s/%s" % (chat, name), type, frm = jidFrom)
	Sender(Component, prs)

def groupchatMessage(chat, text, jidFrom, subj = None, timestamp = 0):
	message = xmpp.Message(chat)
	message.setType("groupchat")
	if timestamp:
		timestamp = time.gmtime(timestamp)
		message.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp), xmpp.NS_DELAY)
	if not subj:
		message.setBody(text)
	else:
		message.setSubject(text)
	message.setFrom(jidFrom)
	Sender(Component, message)

def handleChatMessages(self, msg):
	if msg.has_key("chat_id"):
		idFrom = msg["uid"]
		owner = msg["admin_id"]
		_owner = vk2xmpp(owner)
		chatID = "%s_chat#%s" % (self.UserID, msg["chat_id"]) ## Maybe better to use owner id for chat
		chat = "%s@%s" % (chatID, ConferenceServer)
		users = msg["chat_active"].split(",") ## Why chat owner isn't in a chat? It may cause problems. Or not?
		users.append(self.UserID)
		if not users: ## is it possible?
			if chat in self.chatUsers:
				groupchatPresence(chat, self.getUserData(owner)["name"], vk2xmpp(self.UserID), "unavailable")
				del self.chatUsers[chat]
			return None # Maybe true?

		if not chat in self.chatUsers:
			self.chatUsers[chat] = []
			for usr in (owner, self.UserID):
				groupchatPresence(chat, self.getUserData(usr)["name"], vk2xmpp(usr))
			groupchatSetConfig(chat, _owner)
			member(chat, self.jidFrom, _owner)
			inviteUser(chat, self.jidFrom, _owner, self.getUserData(owner)["name"]) ## TODO: Handle WHO invited me. Yes, i know that it'll be never happen. But maybe someone another do it for himself? You're welcome!
			groupchatMessage(chat, msg["title"], _owner, True, msg["date"])
	
		for user in users: ## BURN IT!
			if not user in self.chatUsers[chat]:
				self.chatUsers[chat].append(user)
				uName = self.getUserData(user)["name"]
				user = vk2xmpp(user)
				member(chat, user, _owner)
				groupchatPresence(chat, uName, user)
		
		for user in self.chatUsers[chat]: ## BURN IT MORE!
			if not user in users:
				self.chatUsers[chat].remove(user)
				uName = self.getUserData(user)["name"]
				groupchatPresence(chat, uName, vk2xmpp(user), "unavailable")

		# This code will not work because function can be called only at message in chat
		if not self.chatUsers[chat]:
			groupchatSetConfig(chat, _owner, exterminate = True) # EXTERMINATE!!!

		body = escapeMsg(uHTML(msg["body"]))
		body += parseAttachments(self, msg)
		body += parseForwardMessages(self, msg)
		if body:
			groupchatMessage(chat, body, vk2xmpp(idFrom), None, msg["date"])
		return None
	return ""

def incomingGroupchatMessageHandler(msg):
	if msg.getType() == "groupchat":
		body = msg.getBody()
		jidToStr = msg.getTo().getStripped()
		jidFromStr = msg.getFrom().getStripped()
		if not msg.getTimestamp() and body:
			Node, Domain = jidFromStr.split("@")
			if Domain == ConferenceServer:
				jidToStr = vk2xmpp(jidToStr)
				if jidToStr in jidToID:
					jid = jidToID[jidToStr]
					Class = Transport[jid]
					Class.msg(body, Node.split("#")[1], "chat_id")


## TODO:
##def onShutdown():
##	for user in TransportList:
##		if Transport[user].chatUsers
##

if ConferenceServer:
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	Handlers["msg01"].append(handleChatMessages)
	Handlers["msg02"].append(incomingGroupchatMessageHandler)
##	Handlers["shutdown"] TODO
else:
	del incomingGroupchatMessageHandler, handleChatMessages, inviteUser, groupchatPresence, groupchatMessage