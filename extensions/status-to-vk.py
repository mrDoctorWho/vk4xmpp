# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 08:08AM GMT)

VK_ACCESS += 1024

GLOBAL_USER_SETTINGS["status_to_vk"] = {"label": "Publish my status in VK", "value": 0}

def statustovk_prs01(source, prs):
	if source in Transport and prs.getType() in ("available", None):
		user = Transport[source]
		if user.settings.status_to_vk:
			mask = user.vk.method("account.getAppPermissions") or 0
			status = prs.getStatus()
			if not getattr(user, "last_status", None) or user.last_status != status:
				if mask & 1024 == 1024:
					if not status:
						user.vk.method("status.set", {"text": ""})
					else:
						user.vk.method("status.set", {"text": status})
				else:
					sendMessage(Component, source, TransportID, _("Not enough permissions to publish your status on the site. Please, register again."))
					logger.error("not changing user's status on the site 'cause we do not have enough permissions (jid: %s)" % source)
			user.last_status = status

registerHandler("prs01", statustovk_prs01)