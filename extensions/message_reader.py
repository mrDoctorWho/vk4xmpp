# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (16.12.14 14:54PM GMT) — 2015.

GLOBAL_USER_SETTINGS["typingreader"] = {"label": "Mark my messages as read when I compose message", "value": 0}
GLOBAL_USER_SETTINGS["read_on_displayed"] = {"label": "Mark my messages as read when I read them", "value": 0}

def typingreader_watch(msg):
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	destination = msg.getTo().getStripped()
	if msg.getType() == "chat" and source in Users:
		user = Users[source]
		uid = vk2xmpp(destination)
		if uid in user.lastMsgByUser:
			lastMsgID = user.lastMsgByUser[uid]
			if lastMsgID > user.lastMarkedMessage:
				if user.settings.typingreader and msg.getTag("composing", namespace=xmpp.NS_CHATSTATES):
					typingreader_markasread(user, lastMsgID)
				if user.settings.read_on_displayed and (msg.getTag("displayed", namespace=xmpp.NS_CHAT_MARKERS)
					or msg.getTag("active", xmpp.NS_CHATSTATES)):
					typingreader_markasread(user, lastMsgID)


def typingreader_markasread(user, mid):
	user.vk.method("messages.markAsRead", {"message_ids": mid})
	# try to ensure that we don't skip further messages unmarked (doesn't work properly though)
	if user.lastMarkedMessage < mid:
		user.lastMarkedMessage = user.lastMsgID


def typingreader_add(msg, destination, source):
	if destination in Users:
		user = Users[destination]
		if user.settings.read_on_displayed:
			msg.setTag("markable", namespace=xmpp.NS_CHAT_MARKERS)


def typingreader_init(user):
	user.lastMarkedMessage = 0


registerHandler("msg02", typingreader_watch)
registerHandler("evt07", typingreader_init)
