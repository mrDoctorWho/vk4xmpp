# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

"""
Module purpose is to receive and handle presences
"""

from __main__ import *
from __main__ import _
from utils import *

# keeps the user's roster
USERS_ON_INIT = {}
EXPIRING_OBJECT_LIFETIME = 600
UPDATE_FRIENDS_DELAY = 60


def updateFriends(user, local):
	"""
	Compares the local (xmpp) and remote (vk) list of friends
	"""
	if TransportID in local:
		local.remove(TransportID)
	if not user.vk.online:
		return None

	friends = user.friends or user.vk.getFriends()
	if not friends or not local:
		logger.error("updateFriends: no friends received (local: %s, remote: %s) (jid: %s).",
			str(local), str(friends), user.source)
		return None

	for uid in friends:
		if uid not in local:
			user.sendSubPresence({uid: friends[uid]})
	# TODO
	# for uid in self.friends:
	# 	if uid not in friends:
	# 		sendPresence(self.source, vk2xmpp(uid), "unsubscribe")


def initializeUser(source, resource, prs):
	"""
	Initializes user for the first time after they connected
	"""
	logger.debug("Got a presence. Searching jid in the database. (jid: %s)", source)
	user = User(source)
	try:
		user.connect()
	except RuntimeError:
		pass
	except Exception:
		sendMessage(source, TransportID,
			_("Auth failed! If this error repeated, "
				"please register again."
				" This incident will be reported.\nCause: %s") % returnExc())
		report(crashLog("user.connect"))
	else:
		user.initialize(send=True, resource=resource)  # probably we need to know resource a bit earlier than this time
		utils.runThread(updateFriends, (user, list(USERS_ON_INIT[source])),  # making a copy so we can remote it safely
			delay=UPDATE_FRIENDS_DELAY)
		utils.runThread(executeHandlers, ("prs01", (source, prs)))

	if source in USERS_ON_INIT:
		del USERS_ON_INIT[source]


def presence_handler(cl, prs):
	pType = prs.getType()
	jidFrom = prs.getFrom()
	source = jidFrom.getStripped()
	resource = jidFrom.getResource()
	destination = prs.getTo().getStripped()
	if source in Users:
		user = Users[source]
		if pType in ("available", "probe", None):
			if destination == TransportID:
				if resource not in user.resources and user not in USERS_ON_INIT:
					logger.debug("Received presence %s from user. Calling sendInitPresence() (jid: %s)" % (pType, source))
					user.resources.add(resource)
					utils.runThread(user.sendInitPresence)
			elif source in USERS_ON_INIT:
				USERS_ON_INIT[source].add(vk2xmpp(destination))

		elif pType == "unavailable":
			if destination == TransportID and resource in user.resources:
				user.resources.remove(resource)
				if user.resources:
					user.sendOutPresence(jidFrom)
			if not user.resources:
				sendPresence(source, TransportID, "unavailable")
				if Transport.settings.send_unavailable:
					user.sendOutPresence(source)
				try:
					user.vk.disconnect()
					del Users[source]
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
						sendPresence(source, destination, hash=USER_CAPS_HASH)
			if destination == TransportID:
				sendPresence(source, destination, hash=TRANSPORT_CAPS_HASH)

		elif pType == "unsubscribe":
			if destination == TransportID:
				removeUser(user, True, False)
				executeHandlers("evt09", (source,))

	# when user becomes online, we get subscribe as we don't have both subscription
	elif pType not in ("error", "unavailable"):
		# It's possible to receive more than one presence from @gmail.com
		if source in USERS_ON_INIT:
			roster = USERS_ON_INIT[source]
			if destination == TransportID and TransportID not in roster and pType in ("available", "probe", None):
				utils.runThread(initializeUser, args=(source, resource, prs))
		else:
			__set = set([])
			USERS_ON_INIT[source] = ExpiringObject(__set, EXPIRING_OBJECT_LIFETIME)
			if destination == TransportID:
				utils.runThread(initializeUser, args=(source, resource, prs))
		USERS_ON_INIT[source].add(vk2xmpp(destination))
	utils.runThread(executeHandlers, ("prs01", (source, prs)))


MOD_TYPE = "presence"
MOD_HANDLERS = ((presence_handler, "", "", False),)
MOD_FEATURES = []
