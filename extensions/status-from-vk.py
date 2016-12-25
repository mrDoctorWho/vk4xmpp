# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

"""
This plugin allows user to see his friends status messages
"""

GLOBAL_USER_SETTINGS["status_from_vk"] = {"label": "Show my friends status messages", "value": 0}


def statusfromvk_evt07(user):
	if user and user.settings.status_from_vk:
		user.vk.friends_fields.add("status")


def statusfromvk_prs02(prs, destination, source):
	if source != TransportID and destination in Users:
		user = Users[destination]
		if user.settings.status_from_vk and not prs.getType():
			id = vk2xmpp(source)
			if id in user.friends and user.friends[id].get("status"):
				prs.setStatus(user.friends[id]["status"])


registerHandler("evt07", statusfromvk_evt07)
registerHandler("prs02", statusfromvk_prs02)
