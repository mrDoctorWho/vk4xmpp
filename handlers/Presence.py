# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

def prsHandler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	jidTo = prs.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	resource = jidFrom.getResource()
	if jidFromStr in Transport:
		user = Transport[jidFromStr]
		if pType in ("available", "probe", None):
			if jidTo == TransportID and resource not in user.resources:
				logger.debug("%s from user %s, will send sendInitPresence" % (pType, jidFromStr))
				user.resources.append(resource)
				user.sendInitPresence()

		elif pType == "unavailable":
			if jidTo == TransportID and resource in user.resources:
				user.resources.remove(resource)
				if user.resources:
					user.sendOutPresence(jidFrom)
			if not user.resources:
				Sender(cl, xmpp.Presence(jidFrom, "unavailable", frm = TransportID))
				user.vk.disconnect()
				Poll.remove(user)
				try:
					del Transport[jidFromStr]
				except KeyError:
					pass
	
		elif pType == "error":
			eCode = prs.getErrorCode()
			if eCode == "404":
				user.vk.disconnect()

		elif pType == "subscribe":
			if jidToStr == TransportID:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = TransportID))
				Sender(cl, xmpp.Presence(jidFrom, frm = TransportID))
			else:
				Sender(cl, xmpp.Presence(jidFromStr, "subscribed", frm = jidTo))
				if user.friends:
					id = vk2xmpp(jidToStr)
					if id in user.friends:
						if user.friends[id]["online"]:
							Sender(cl, xmpp.Presence(jidFrom, frm = jidTo))
	
		elif pType == "unsubscribe":
			if jidFromStr in Transport and jidToStr == TransportID:
				user.deleteUser(True)
				watcherMsg(_("User removed registration: %s") % jidFromStr)


	elif pType in ("available", None):
		logger.debug("User %s not in transport but want to be in" % jidFromStr)
		with Database(DatabaseFile) as db:
			db("select jid,username from users where jid=?", (jidFromStr,))
			data = db.fetchone()
			if data:
				logger.debug("User %s found in db" % jidFromStr)
				jid, phone = data
				Transport[jid] = user = tUser((phone, None), jid)
				try:
					if user.connect():
						user.init(None, True)
						user.resources.append(resource)
						Poll.add(user)
					else:
						crashLog("prs.connect", 0, False)
						msgSend(Component, jid, _("Auth failed! If this error repeated, please register again. This incident will be reported."), TransportID)
				except Exception:
					crashLog("prs.init")
