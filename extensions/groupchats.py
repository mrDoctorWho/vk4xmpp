# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

if not require("attachments") or not require("forwardMessages"):
	raise

def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to = chat, frm = jidFrom)
	x = xmpp.Node("x")
	x.setNamespace(xmpp.NS_MUC_USER)
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node = x)
	Sender(Component, invite)

def roomPresence(chat, name, jidFrom, type = None):
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
		chatID = "%s_chat#%s" % (self.UserID, msg["chat_id"]) ## Maybe better to use owner id for chat
		chat = "%s@%s" % (chatID, ConferenceServer)
		users = msg["chat_active"].split(",") ## Why chat owner isn't in a chat? It may cause problems. Or not?
		
		if not users:
			if chat in self.chatUsers:
				roomPresence(chat, self.getUserName(owner), vk2xmpp(self.UserID), "unavailable")
				del self.chatUsers[chat]
			return None # Maybe true?

		if not chat in self.chatUsers:
			self.chatUsers[chat] = []
			inviteUser(chat, self.jidFrom, vk2xmpp(owner), self.getUserName(owner)) ## TODO: Handle WHO invited me. Yes, i know that it'll be never happen. But maybe someone another do it for himself? You're welcome!
			for usr in (owner, self.UserID):
				roomPresence(chat, self.getUserName(usr), vk2xmpp(usr))
			groupchatMessage(chat, msg["title"], vk2xmpp(owner), True, msg["date"])
	
		for user in users: ## BURN IT!
			if not user in self.chatUsers[chat]:
				self.chatUsers[chat].append(user)
				uName = self.getUserName(user)
				roomPresence(chat, uName, vk2xmpp(user))
		
		for user in self.chatUsers[chat]: ## BURN IT MORE!
			if not user in users:
				self.chatUsers[chat].remove(user)
				uName = self.getUserName(user)
				roomPresence(chat, uName, vk2xmpp(user), "unavailable")

		body = escapeMsg(msg["body"])
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

if ConferenceServer:
	TransportFeatures.append(xmpp.NS_GROUPCHAT)
	Handlers["msg01"].append(handleChatMessages)
	Handlers["msg02"].append(incomingGroupchatMessageHandler)
else:
	del incomingGroupchatMessageHandler, handleChatMessages, inviteUser, roomPresence, groupchatMessage