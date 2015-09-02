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
	Initializes user for the first time after they connected
	"""
	logger.debug("Got a presence. Searching jid in the database. (jid: %s)", source)
	user = User(source)
	try:
		connect = user.connect()
	except RuntimeError:
		pass
	except Exception:
		sendMessage(source, TransportID, 
			_("Auth failed! If this error repeated, "
				"please register again. This incident will be reported."))
		crashLog("user.connect")
	else:
		user.initialize(send=True, resource=resource)  # probably we need to know resource a bit earlier than this time
		utils.runThread(executeHandlers, ("prs01", (source, prs)))

	if source in USERS_ON_INIT:
		USERS_ON_INIT.remove(source)


def presence_handler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	source = jidFrom.getStripped()
	resource = jidFrom.getResource()
	destination = prs.getTo().getStripped()
	if source in Transport:
		user = Transport[source]
		if pType in ("available", "probe", None):
			if destination == TransportID:
				if resource not in user.resources and user not in USERS_ON_INIT:
					logger.debug("Received presence %s from user. Calling sendInitPresence() (jid: %s)" % (pType, source))
					user.resources.add(resource)
					utils.runThread(user.sendInitPresence)

		elif pType == "unavailable":
			if destination == TransportID and resource in user.resources:
				user.resources.remove(resource)
				if user.resources:
					user.sendOutPresence(jidFrom)
			if not user.resources:
				sendPresence(source, TransportID, "unavailable")
				if transportSettings.send_unavailable:
					user.sendOutPresence(source)
				try:
					user.vk.disconnect()
					del Transport[source]
				except (AttributeError, KeyError):
					pass
	
		elif pType == "error":
			if prs.getErrorCode() == "404":
				user.vk.disconnect()

		elif pType == "subscribe":
			sendPresence(source, destination, "subscribed")
			if user.friends:
				id = vk2xmpp(destination)
				if id in user.friends:
					if user.friends[id]["online"]:
						sendPresence(source, destination)
			if destination == TransportID:
				sendPresence(source, destination)
	
		elif pType == "unsubscribe":
			if destination == TransportID:
				removeUser(user, True, False)
				executeHandlers("evt09", (source,))


	elif pType in ("available", None) and destination == TransportID:
		# It's possible to receive more than one presence from @gmail.com
		if source not in USERS_ON_INIT:
			utils.runThread(initializeUser, args=(source, resource, prs))
			USERS_ON_INIT.add(source)
	utils.runThread(executeHandlers, ("prs01", (source, prs)))


MOD_TYPE = "presence"
MOD_HANDLERS = ((presence_handler, "", "", False),)
MOD_FEATURES = []