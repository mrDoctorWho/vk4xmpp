# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015 (27.08.15 09:31AM GMT)

"""
Implements XEP-0172: User Nickname (case 4.2)
"""

GLOBAL_USER_SETTINGS["add_nicknames"] = {"value": 0, "label": "Add nickname to messages from strangers"}


def add_nickname(msg, destination, source):
	if destination in Transport and source != TransportID:  # That would be strange if user wasn't in Transport
		user = Transport[destination]
		if user.settings.add_nicknames:
			uid = vk2xmpp(source)
			strangers = getattr(user, "strangers", set([]))
			if uid not in strangers and uid not in user.friends:
				key = "name"
				if user.settings.use_nicknames:
					key = "screen_name"
				name = user.vk.getUserData(uid)[key]
				msg.setTag("nick", namespace=xmpp.NS_NICK)
				msg.setTagData("nick", name)
				strangers.add(uid)
			user.strangers = strangers


registerHandler("msg03", add_nickname)
