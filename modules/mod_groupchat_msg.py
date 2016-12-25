# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

"""
Module purpose is to handle messages from groupchats
"""

from __main__ import *


def incoming_message_handler(cl, msg):
	"""
	Handles incoming (xmpp) messages and sends them to VK
	"""
	if msg.getType() == "groupchat":
		body = msg.getBody()
		destination = msg.getTo().getStripped()
		nick = msg.getFrom().getResource()
		source = msg.getFrom().getStripped()
		if mod_xhtml:
			html = msg.getTag("html")
		else:
			html = None

		x = msg.getTag("x", {"xmlns": xmpp.NS_MUC_USER})
		if x and x.getTagAttr("status", "code") == "100":
			raise xmpp.NodeProcessed()

		if not msg.getTimestamp() and body and destination == TransportID:
			user = Chat.getUserObject(source)
			creator, id, domain = Chat.getParts(source)
			owner_nickname = None
			if user:
				if source in getattr(user, "chats", {}):
					owner_nickname = user.chats[source].owner_nickname
				if not owner_nickname:
					owner_nickname = runDatabaseQuery("select nick from groupchats where jid=?",
						(source,), many=False)[0]
				# None of “normal” clients will send messages with timestamp
				# If we do (as we set in force_vk_date_group), then the message received from a user
				# If we don't and nick (as in settings) is tied to the chat, then we can determine who sent the message
				send = (nick == owner_nickname and user.settings.tie_chat_to_nickname)
				chat = createChat(user, source)
				chat.invited = True  # the user has joined themselves, so we don't need to invite them
				if html and html.getTag("body"):
					logger.debug("groupchats: fetched xhtml image (jid: %s)" % source)
					try:
						mod_xhtml.parseXHTML(user, html, source, source, "chat_id")
					except Exception:
						pass
					else:
						# Don't send a message if there's an image
						raise xmpp.NodeProcessed()
				if send:
					with user.sync:
						user.vk.sendMessage(body, id, "chat_id")
					if chat.isUpdateRequired():
						updateLastUsed(chat)
					raise xmpp.NodeProcessed()


MOD_TYPE = "message"
MOD_HANDLERS = ((incoming_message_handler, "", "", False),)
MOD_FEATURES = []
