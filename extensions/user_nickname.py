# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015 (27.08.15 09:31AM GMT)

"""
Implements XEP-0172: User Nickname (apparently, case 4.2)
"""

GLOBAL_USER_SETTINGS["add_nicknames_msg"] = {"value": 0, "label": "Add nickname to message stanzas from strangers"}
GLOBAL_USER_SETTINGS["add_nicknames_prs"] = {"value": 0, "label": "Add nickname to presence stanzas"}


def add_username(stanza, user, uid):
	if uid != TransportID:
		key = "name"
		if user.settings.use_nicknames:
			key = "screen_name"
		name = user.vk.getUserData(uid)[key]
	else:
		name = IDENTIFIER["name"]
	stanza.setTag("nick", namespace=xmpp.NS_NICK)
	stanza.setTagData("nick", name)


def add_nickname_msg03(msg, destination, source):
	if destination in Transport and source != TransportID:  # That would be strange if user wasn't in Transport
		user = Transport[destination]
		if user.settings.add_nicknames_msg:
			uid = vk2xmpp(source)
			strangers = getattr(user, "strangers", set([]))
			if uid not in strangers and uid not in user.friends:
				add_username(msg, user, uid)
				strangers.add(uid)
			user.strangers = strangers


def add_nickname_prs02(prs, destination, source):
	if destination in Transport and not prs.getType():
		user = Transport[destination]
		uid = vk2xmpp(source)
		if uid in user.friends and user.settings.add_nicknames_prs:
			add_username(prs, user, uid)


registerHandler("msg03", add_nickname_msg03)
registerHandler("prs02", add_nickname_prs02)
