# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from __main__ import *
from __main__ import _


def initializeUser(source, resource, prs):
	logger.debug("User not in the transport, but presence received. Searching in database (jid: %s)" % source)
	with Database(DatabaseFile, Semaphore) as db:
		db("select jid,username from users where jid=?", (source,))
		data = db.fetchone()
	if data:
		logger.debug("User has been found in database (jid: %s)" % source)
		jid, phone = data
		Transport[jid] = user = User((phone, None), jid)
		try:
			if user.connect():
				user.initialize(False, True, resource)
				runThread(executeHandlers, ("prs01", (source, prs)))
			else:
				crashLog("user.connect", False)
				sendMessage(Component, jid, TransportID, _("Auth failed! If this error repeated, please register again. This incident will be reported."))
		except Exception:
			crashLog("prs.init")


def presence_handler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	jidTo = prs.getTo()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	resource = jidFrom.getResource()
	if source in Transport:
		user = Transport[source]
		if pType in ("available", "probe", None):
			if jidTo == TransportID:
				if resource not in user.resources:
					logger.debug("Received presence %s from user. Will send sendInitPresence (jid: %s)" % (pType, source))
					user.resources.add(resource)
					runThread(user.sendInitPresence, ())
				runThread(executeHandlers, ("prs01", (source, prs)))

		elif pType == "unavailable":
			if jidTo == TransportID and resource in user.resources:
				user.resources.remove(resource)
				if user.resources:
					user.sendOutPresence(jidFrom)
			if not user.resources:
				sender(cl, xmpp.Presence(jidFrom, "unavailable", frm = TransportID))
				user.vk.disconnect()
				try:
					del Transport[source]
				except KeyError:
					pass
	
		elif pType == "error":
			eCode = prs.getErrorCode()
			if eCode == "404":
				user.vk.disconnect()

		elif pType == "subscribe":
			if destination == TransportID:
				sender(cl, xmpp.Presence(source, "subscribed", frm = TransportID))
				sender(cl, xmpp.Presence(jidFrom, frm = TransportID))
			else:
				sender(cl, xmpp.Presence(source, "subscribed", frm = jidTo))
				if user.friends:
					id = vk2xmpp(destination)
					if id in user.friends:
						if user.friends[id]["online"]:
							sender(cl, xmpp.Presence(jidFrom, frm = jidTo))
	
		elif pType == "unsubscribe":
			if source in Transport and destination == TransportID:
				removeUser(user, True, False)
				watcherMsg(_("User removed his registration: %s") % source)


	elif pType in ("available", None) and destination == TransportID:
		runThread(initializeUser, args=(source, resource, prs))
		


def load():
	Component.RegisterHandler("presence", presence_handler)