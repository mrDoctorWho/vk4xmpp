# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

"""
Module purpose is to receive and handle presences
"""

from __main__ import *
from __main__ import _

USERS_ON_INIT = set([])

def initializeUser(source, resource, prs):
	"""
	Initializes user for a first time after he have registered
	"""
	logger.debug("User not in the transport, but presence received. Searching in database (jid: %s)" % source)
	with Database(DatabaseFile, Semaphore) as db:
		db("select jid,username from users where jid=?", (source,))
		data = db.fetchone()
	if data:
		sendPresence(source, TransportID, None, IDENTIFIER["name"], caps=True, reason=_("You are being initialized, please wait..."), show="xa")
		logger.debug("User has been found in database (jid: %s)" % source)
		jid, phone = data
		Transport[jid] = user = User(jid)
		try:
			if user.connect():
				user.initialize(False, True, resource) ## probably we need to know resource a bit earlier than this time
				runThread(executeHandlers, ("prs01", (source, prs)))
			else:
				crashLog("user.connect", False)
				sendMessage(Component, jid, TransportID, _("Auth failed! If this error repeated, please register again. This incident will be reported."))
		except Exception:
			crashLog("prs.init")
	if source in USERS_ON_INIT:
		USERS_ON_INIT.remove(source)


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
				if resource not in user.resources and user not in USERS_ON_INIT:
					logger.debug("Received presence %s from user. Calling sendInitPresence() (jid: %s)" % (pType, source))
					user.resources.add(resource)
					runThread(user.sendInitPresence, ())

		elif pType == "unavailable":
			if jidTo == TransportID and resource in user.resources:
				user.resources.remove(resource)
				if user.resources:
					user.sendOutPresence(jidFrom)
			if not user.resources:
				sender(cl, xmpp.Presence(jidFrom, "unavailable", frm = TransportID))
				if transportSettings.send_unavailable:
					user.sendOutPresence(jidFrom)
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
				sender(cl, xmpp.Presence(source, "subscribed", frm=TransportID))
				sender(cl, xmpp.Presence(jidFrom, frm=TransportID))
			else:
				sender(cl, xmpp.Presence(source, "subscribed", frm=jidTo))
				if user.friends:
					id = vk2xmpp(destination)
					if id in user.friends:
						if user.friends[id]["online"]:
							sender(cl, xmpp.Presence(jidFrom, frm=jidTo))
	
		elif pType == "unsubscribe":
			if source in Transport and destination == TransportID:
				removeUser(user, True, False)
				watcherMsg(_("User removed his registration: %s") % source)


	elif pType in ("available", None) and destination == TransportID:
		# It's possible to receive more than one presence from @gmail.com
		if source not in USERS_ON_INIT:
			runThread(initializeUser, args=(source, resource, prs))
			USERS_ON_INIT.add(source)
	runThread(executeHandlers, ("prs01", (source, prs)))


def load():
	Component.RegisterHandler("presence", presence_handler)


def unload():
	Component.UnregisterHandler("presence", presence_handler)