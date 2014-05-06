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

def buildConfigForm(form=None, type="sumbit", fields=[]):
	form = form or xmpp.DataForm(type)
	for key in fields:
		field = form.setField(key["var"], key.get("value"), key.get("type"))
	return form

## TODO: Set chatroom's name
def groupchatSetConfig(chat, jidFrom, exterminate=False):
	iq = xmpp.Iq("set", to=chat, frm=jidFrom, xmlns="jabber:component:accept")
	query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
	if exterminate:
		query.addChild("destroy")
	else:
		form = buildConfigForm(fields = [{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
										 {"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
										 {"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "1"},
										 {"var": "muc#roomconfig_whois", "value": "anyone"}])
		query.addChild(node=form)
	Sender(Component, iq)

def groupchatPresence(chat, name, jidFrom, type=None):
	prs = xmpp.Presence("%s/%s" % (chat, name), type, frm=jidFrom)
	Sender(Component, prs)

def groupchatMessage(chat, text, jidFrom, subj=None, timestamp=0):
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
			logger.debug("groupchats: all users exterminated in chat: %s" % chat)
			if chat in self.chatUsers:
				groupchatPresence(chat, self.getUserData(owner)["name"], vk2xmpp(self.UserID), "unavailable")
				del self.chatUsers[chat]
			return None # Maybe true?

		if chat not in self.chatUsers:
			logger.debug("groupchats: creating %s. Users: %s; owner: %s" % (chat, msg["chat_active"], owner))
			self.chatUsers[chat] = []
			for usr in (owner, self.UserID):
				groupchatPresence(chat, self.getUserData(usr)["name"], vk2xmpp(usr))
			groupchatSetConfig(chat, _owner)
			member(chat, self.source, _owner)
			inviteUser(chat, self.source, _owner, self.getUserData(owner)["name"]) ## TODO: Handle WHO invited me. Yes, i know that it'll be never happen. But maybe someone another do it for himself? You're welcome!
			groupchatMessage(chat, msg["title"], _owner, True, msg["date"])
	
		for user in users: ## BURN IT!
			if not user in self.chatUsers[chat]:
				logger.debug("groupchats: user %s has joined the chat %s" % (user, chat))
				self.chatUsers[chat].append(user)
				uName = self.getUserData(user)["name"]
				user = vk2xmpp(user)
				member(chat, user, _owner)
				groupchatPresence(chat, uName, user)
		
		for user in self.chatUsers[chat]: ## BURN IT MORE!
			if not user in users:
				logger.debug("groupchats: user %s has left the chat %s" % (user, chat))
				self.chatUsers[chat].remove(user)
				uName = self.getUserData(user)["name"]
				groupchatPresence(chat, uName, vk2xmpp(user), "unavailable")

		# This code will not work because function can be called only at message in chat
		if not self.chatUsers[chat]: # Impossible
			logger.debug("groupchats: %s would be exterminated right now!" % chat)
			groupchatSetConfig(chat, _owner, exterminate=True) # EXTERMINATE!!!

		body = escape("", uHTML(msg["body"]))
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
		xTag = msg.getTag("x", {"xmlns": "http://jabber.org/protocol/muc#user"})
		if xTag and xTag.getTagAttr("status", "code") == "100":
			raise xmpp.NodeProcessed()

		if not msg.getTimestamp() and body:
			Node, Domain = jidFromStr.split("@")
			if Domain == ConferenceServer:
				jidToStr = vk2xmpp(jidToStr)
				if jidToStr in jidToID:
					jid = jidToID[jidToStr]
					user = Transport[jid]
					user.msg(body, Node.split("#")[1], "chat_id")


## TODO:
##def onShutdown():
##	for user in Transport.values():
##		if user.chatUsers
##

if ConferenceServer:
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	Handlers["msg01"].append(handleChatMessages)
	Handlers["msg02"].append(incomingGroupchatMessageHandler)
##	Handlers["shutdown"] TODO
else:
	del incomingGroupchatMessageHandler, handleChatMessages, inviteUser, groupchatPresence, groupchatMessage
