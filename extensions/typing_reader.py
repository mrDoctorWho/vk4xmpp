# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (16.12.14 14:54PM GMT) — 2015.

GLOBAL_USER_SETTINGS["typingreader"] = {"label": "Mark my messages as read when I compose message", "value": 0}

def typingreader_watch(msg):
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	if msg.getType() == "chat" and source in Transport:
		user = Transport[source]
		if user.settings.typingreader:
			if (user.lastMsgID > user.lastMarkedMessage) and msg.getTag("composing"):
				user.vk.method("messages.markAsRead", {"message_ids": str(user.lastMsgID)})
				user.lastMarkedMessage = user.lastMsgID


def typingreader_init(user):
	user.lastMarkedMessage = 0


registerHandler("msg02", typingreader_watch)
registerHandler("evt07", typingreader_init)
 
