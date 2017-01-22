# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 08:08AM GMT) — 2015.

"""
This plugin allows users to publish their status in VK
"""

VK_ACCESS += 1024

GLOBAL_USER_SETTINGS["status_to_vk"] = {"label": "Publish my status in VK", "value": 0}
GLOBAL_USER_SETTINGS["status_from_vk"] = {"label": "Show my friends status messages", "value": 0}


def statustovk_prs01(source, prs, retry=3):
	if source in Users and prs.getType() in ("available", None):
		if prs.getTo() == TransportID:
			user = Users[source]
			if user.settings.status_to_vk:
				mask = user.vk.method("account.getAppPermissions") or 0
				if mask:
					status = prs.getStatus()
					if not getattr(user, "last_status", None) or user.last_status != status:
						if mask & 1024 == 1024:
							if not status:
								user.vk.method("status.set", {"text": ""})
							else:
								user.vk.method("status.set", {"text": status})
						else:
							sendMessage(source, TransportID, _("Not enough permissions to publish your status on the site. Please, register again."))
							logger.error("not changing user's status on the site 'cause we do not have enough permissions (jid: %s)" % source)
					user.last_status = status
				else:
					logger.debug("we didn't receive application permissions, so starting a timer (jid: %s)" % source)
					if retry:
						utils.runThread(statustovk_prs01, (source, prs, (retry -1)), delay=10)


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


registerHandler("prs01", statustovk_prs01)
registerHandler("evt07", statusfromvk_evt07)
registerHandler("prs02", statusfromvk_prs02)