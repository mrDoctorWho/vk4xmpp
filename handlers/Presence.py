# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

def prsHandler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	jidTo = prs.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	if jidFromStr in Transport:
		Class = Transport[jidFromStr]
		Resource = jidFrom.getResource()
		if pType in ("available", "probe", None):
			if jidTo == TransportID and Resource not in Class.resources:
				logger.debug("%s from user %s, will send sendInitPresence" % (pType, jidFromStr))
				Class.resources.append(Resource)
				if Class.lastStatus == "unavailable" and len(Class.resources) == 1:
					if not Class.vk.Online:
						Class.vk.Online = True
						Class.vk.onlineMe()
				Class.sendInitPresence()

		elif pType == "unavailable":
			if jidTo == TransportID and Resource in Class.resources:
				Class.resources.remove(Resource)
				if not Class.resources:
					Sender(cl, xmpp.Presence(jidFrom, "unavailable", frm = TransportID))
					Class.vk.disconnect()
				else:
					Class.sendOutPresence(jidFrom)
	
		elif pType == "error":
			eCode = prs.getErrorCode()
			if eCode == "404":
				Class.vk.disconnect()

		elif pType == "subscribe":
			if jidToStr == TransportID:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = TransportID))
				Sender(cl, xmpp.Presence(jidFrom, frm = TransportID))
			else:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = jidTo))
				if Class.friends:
					id = vk2xmpp(jidToStr)
					if id in Class.friends:
						if Class.friends[id]["online"]:
							Sender(cl, xmpp.Presence(jidFrom, frm = jidTo))
		if jidToStr == TransportID:
			Class.lastStatus = pType

