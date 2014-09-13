# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 08:08AM GMT)

VK_ACCESS += 1024

GLOBAL_USER_SETTINGS["status_to_vk"] = {"label": "Publish my status in VK", "value": 0}

def statusChange(source, prs):
	if source in Transport and prs.getType() in ("available", None): ## do we need to check prs type?
		user = Transport[source]
		if user.settings.status_to_vk:
			mask = user.vk.method("account.getAppPermissions") or 0
			status = prs.getStatus()
			if not getattr(user, "last_status", None) or user.last_status != status:
				if mask & 1024 == 1024:
					user.vk.method("status.set", {"text": status})
				else:
					logger.debug("not changing user's status in the VK 'cause we do not have enough permissions (jid: %s)" % source)
			user.last_status = status

registerHandler("prs01", statusChange)