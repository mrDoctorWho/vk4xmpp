# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.
# File contains parts of code from
# BlackSmith mark.1 XMPP Bot, © simpleApps 2011 — 2014.

# Installation:
# The extension requires up to 2 fields in the main config:
# 1. ConferenceServer - the address of your (or not yours?) conference server
# Bear in mind that there can be limits on the jabber server for conference per jid. Read the wiki for more details.
# 2. CHAT_LIFETIME_LIMIT - the limit of the time after that user considered inactive and will be removed. 
# Time must be formatted as text and contain the time variable measurement.
# For example: CHAT_LIFETIME_LIMIT = "28y09M21d" means chat will be removed after 28 years 9 Months 21 days from now
# You can wheter ignore or use any of these chars: smdMy.
# Used chars: s for seconds, m for minutes, d for days, M for months, y for years. The number MUST contain 2 digits as well.
# Note: if you won't set the field, plugin won't remove any chat, but still will be gathering statistics.


"""
Handles VK Multi-Dialogs
Implements XEP-0045: Multi-User Chat (over an exsisting chat)
Note: This file contains only outgoing-specific stuff (vk->xmpp)
along with the Chat class and other useful functions
The code which handles incoming stuff (xmpp->vk) is placed in the following modules:
mod_groupchat_prs for presence handling
mod_groupchat_msg for message handling
"""

MAX_UPDATE_DELAY = 3600  # 1 hour
CHAT_CLEANUP_DELAY = 86400  # 24 hours

if not require("attachments") or not require("forwarded_messages"):
	raise AssertionError("extension 'groupchats' requires 'forwarded_messages' and 'attachments'")


def setAffiliation(chat, afl, jid, jidFrom=TransportID, reason=None):
	"""
	Set user affiliation in a chat.
	Parameters:
		* chat - the chat to set affiliation in
		* afl - the affiliation to set to
		* jid - the user's jid whose affiliation needs to be changed
		* jidFrom - the chat's owner jid (or anyone who can set users roles)
		* reason - special reason
	"""
	stanza = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = xmpp.Node("query", {"xmlns": xmpp.NS_MUC_ADMIN})
	arole = query.addChild("item", {"jid": jid, "affiliation": afl})
	if reason:
		arole.setTagData("reason", reason)
	stanza.addChild(node=query)
	sender(Component, stanza)


def inviteUser(chat, jidTo, jidFrom, name):
	"""
	Invite user to a chat.
	Parameters:
		* chat - the chat to invite to
		* jidTo - the user's jid who needs to be invited
		* jidFrom - the inviter's jid
		* name - the inviter's name
	"""
	invite = xmpp.Message(to=chat, frm=jidFrom)
	x = xmpp.Node("x", {"xmlns": xmpp.NS_MUC_USER})
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node=x)
	sender(Component, invite)


def joinChat(chat, name, jidFrom, status=None):
	"""
	Join a chat.
	Parameters:
		* chat - the chat to join in
		* name - nickname
		* jidFrom - jid which will be displayed when joined
		* status - special status
	"""
	prs = xmpp.Presence("%s/%s" % (chat, name), frm=jidFrom, status=status)
	prs.setTag("c", {"node": TRANSPORT_CAPS_HASH, "ver": hash, "hash": "sha-1"},
		xmpp.NS_CAPS)
	sender(Component, prs)


def leaveChat(chat, jidFrom, reason=None):
	"""
	Leave chat.
	Parameters:
		* chat - chat to leave from
		* jidFrom - jid to leave with
		* reason - special reason
	"""
	prs = xmpp.Presence(chat, "unavailable", frm=jidFrom, status=reason)
	sender(Component, prs)


def chatMessage(chat, text, jidFrom, subj=None, timestamp=0):
	"""
	Sends a message to the chat
	"""
	message = xmpp.Message(chat, typ="groupchat")
	if timestamp:
		timestamp = time.gmtime(timestamp)
		message.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	if not subj:
		message.setBody(text)
	else:
		message.setSubject(text)
	message.setFrom(jidFrom)
	executeHandlers("msg03g", (message, chat, jidFrom))
	sender(Component, message)


def setChatConfig(chat, jidFrom, exterminate=False, cb=None, args={}):
	"""
	Sets the chat config
	"""
	iq = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
	if exterminate:
		query.addChild("destroy")
	else:
		form = utils.buildDataForm(fields=[
			{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
			{"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
			{"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "0"},
			{"var": "muc#roomconfig_persistentroom", "type": "boolean", "value": "1"},
			{"var": "muc#roomconfig_whois", "value": "anyone"}],
			type="submit")
		query.addChild(node=form)
	sender(Component, iq, cb, args)


def handleOutgoingChatMessage(user, vkChat):
	"""
	Handles outging VK messages and sends them to XMPP
	"""
	if "chat_id" in vkChat:
		# check if the groupchats support enabled in user's settings
		if not user.settings.groupchats:
			return None

		if not hasattr(user, "chats"):
			user.chats = {}

		# TODO: make this happen in the kernel, so we don't need to check it here
		if not user.vk.userID:
			logger.warning("groupchats: we didn't receive user id, trying again after 10 seconds (jid: %s)", user.source)
			user.vk.getUserID()
			utils.runThread(handleOutgoingChatMessage, (user, vkChat), delay=10)
			return None

		owner = vkChat.get("admin_id", "1")
		chatID = vkChat["chat_id"]
		chatJID = "%s_chat#%s@%s" % (user.vk.userID, chatID, ConferenceServer)
		chat = createChat(user, chatJID)
		if not chat.initialized:
			chat.init(owner, chatID, chatJID, vkChat["title"], vkChat["date"], vkChat["chat_active"].split(","))
		if not chat.created:
			if chat.creation_failed:
				return None
			# we can add user, vkChat to the create() method to prevent losing or messing up the messages
			chat.create(user)
		# read the comments above the handleMessage function
		if not chat.created:
			time.sleep(1.5)
		chat.handleMessage(user, vkChat)
		return None
	return ""


def createChat(user, source):
	"""
	Creates a chat
	Args:
		user: the User object
		source: the chat's jid
	"""
	if not hasattr(user, "chats"):
		user.chats = {}
	if source in user.chats:
		chat = user.chats[source]
	else:
		user.chats[source] = chat = Chat()
	return chat


class Chat(object):
	"""
	Class used to handle multi-user dialogs
	"""
	def __init__(self):
		self.created = False
		self.invited = False
		self.initialized = False
		self.exists = False
		self.creation_failed = False
		self.owner_nickname = None
		self.source = None
		self.jid = None
		self.owner = None
		self.subject = None
		self.creation_date = None
		self.id = 0
		self.last_update = 0
		self.raw_users = {}
		self.users = {}

	def init(self, owner, id, jid, subject, date, users=[]):
		"""
		Assigns an id and other needed attributes to the class object
		Args:
			owner: owner's id (str)
			id: chat's id (int)
			jid: chat's jid (str)
			subject: chat's subject
			date: the chat creation date
			users: dictionary of ids, id: {"name": nickname, "jid": jid}
		"""
		self.id = id
		self.jid = jid
		self.owner = owner
		self.raw_users = users
		self.subject = subject
		self.creation_date = date
		self.initialized = True

	def create(self, user):
		"""
		Creates a chat, joins it and sets the config
		"""
		logger.debug("groupchats: creating %s. Users: %s; owner: %s (jid: %s)",
			self.jid, self.raw_users, self.owner, user.source)
		exists = runDatabaseQuery("select user from groupchats where jid=?", (self.jid,), many=True)
		if exists:
			self.exists = True
			logger.debug("groupchats: groupchat %s exists in the database (jid: %s)",
				self.jid, user.source)
		else:
			logger.debug("groupchats: groupchat %s will be added to the database (jid: %s)",
				self.jid, user.source)
			runDatabaseQuery("insert into groupchats (jid, owner, user, last_used) values (?,?,?,?)",
				(self.jid, TransportID, user.source, time.time()), True)

		name = user.vk.getUserData(self.owner)["name"]
		self.users[TransportID] = {"name": name, "jid": TransportID}
		# We join to the chat with the room owner's name to set the room subject from their name.
		joinChat(self.jid, name, TransportID, "Lost in time.")
		setChatConfig(self.jid, TransportID, False, self.onConfigSet, {"user": user})

	def initialize(self, user, chat):
		"""
		Initializes chat object: 
			1) requests users list if required
			2) makes them members
			3) invites the user 
			4) sets the chat subject
		Parameters:
			chat: chat's jid
		"""
		if not self.raw_users:
			vkChat = self.getVKChat(user, self.id)  # getting the chat users
			if not vkChat and not self.invited:
				logger.error("groupchats: damn vk didn't answer to the chat list "
							"request, starting timer to try again (jid: %s)", user.source)
				utils.runThread(self.initialize, (user, chat), delay=10)
				return False
			self.raw_users = vkChat.get("users")

		name = "@%s" % TransportID
		setAffiliation(chat, "member", user.source)
		if not self.invited:
			inviteUser(chat, user.source, TransportID, user.vk.getUserData(self.owner)["name"])
			logger.debug("groupchats: user has been invited to chat %s (jid: %s)", chat, user.source)
			self.invited = True
		self.setSubject(self.subject, self.creation_date)
		joinChat(chat, name, TransportID, "Lost in time.")  # let's rename ourselves
		self.users[TransportID] = {"name": name, "jid": TransportID}

	def update(self, userObject, vkChat):
		"""
		Updates chat users and sends messages
		Uses two user lists to prevent losing of any of them
		"""
		all_users = vkChat["chat_active"].split(",")
		all_users = [int(user) for user in all_users if user]
		if userObject.settings.show_all_chat_users:
			users = self.getVKChat(userObject, self.id)
			if users:
				all_users = users.get("users", [])
		old_users = self.users.keys()
		buddies = all_users + old_users
		if TransportID in buddies:
			buddies.remove(TransportID)
		if userObject.vk.getUserID() in buddies:
			buddies.remove(userObject.vk.getUserID())

		for user in buddies:
			jid = vk2xmpp(user)
			if user not in old_users:
				logger.debug("groupchats: user %s has joined the chat %s (jid: %s)",
					user, self.jid, userObject.source)
				name = userObject.vk.getUserData(user)["name"]
				self.users[int(user)] = {"name": name, "jid": jid}
				setAffiliation(self.jid, "member", jid)
				joinChat(self.jid, name, jid)

			elif user not in all_users:
				logger.debug("groupchats: user %s has left the chat %s (jid: %s)",
					user, self.jid, userObject.source)
				leaveChat(self.jid, jid)
				del self.users[user]

		subject = vkChat["title"]
		if subject and subject != self.subject:
			self.setSubject(subject)
		self.raw_users = all_users


	def setSubject(self, subject, date=None):
		"""
		Changes the chat subject
		"""
		chatMessage(self.jid, subject, TransportID, True, date)
		self.subject = subject

	def onConfigSet(self, cl, stanza, user):
		"""
		A callback which called after attempt to create the chat
		"""
		chat = stanza.getFrom().getStripped()
		if xmpp.isResultNode(stanza):
			self.created = True
			logger.debug("groupchats: stanza \"result\" received from %s, "
			 	 "continuing initialization (jid: %s)", chat, user.source)
			utils.execute(self.initialize, (user, chat))
		else:
			logger.error("groupchats: couldn't set room %s config, the answer is: %s (jid: %s)",
				chat, str(stanza), user.source)
			self.creation_failed = True

	# there's a possibility to mess up here if many messages were sent before we created the chat 
	# we have to send the messages immendiately as soon as possible, so delay can mess the messages up
	def handleMessage(self, user, vkChat, retry=True):
		"""
		Handle incoming (VK -> XMPP) messages
		"""
		if self.created:
			self.update(user, vkChat)
			body = escape("", uhtml(vkChat["body"]))
			body += parseAttachments(user, vkChat)
			body += parseForwardedMessages(user, vkChat)
			if body:
				date = 0
				if user.settings.force_vk_date_group:
					date = vkChat["date"]
				chatMessage(self.jid, body, vk2xmpp(vkChat["uid"]), None, date)
		else:
			source = "unknown"
			userObject = self.getUserObject(self.jid)
			if userObject:
				source = userObject.source
			# todo: FULL leave on error and try to create the chat again
			logger.warning("groupchats: chat %s wasn't created well, so trying to create it again (jid: %s)", self.jid, source)
			logger.warning("groupchats: is there any groupchat limit on the server?")
			if retry:
				# TODO: We repeat it twice on each message. We shouldn't.
				self.handleMessage(user, vkChat, False)

	def isUpdateRequired(self):
		"""
		Tells whether it's required to update the chat's last_used time
		Returns:
			True if required
		"""
		if not self.source:
			return False
		if not self.last_update:
			return True
		if (time.time() - self.last_update) > MAX_UPDATE_DELAY:
			return True
		return False

	@api.attemptTo(3, dict, RuntimeError)
	def getVKChat(cls, user, id):
		"""
		Get vk chat by id
		"""
		chat = user.vk.method("messages.getChat", {"chat_id": id})
		if not chat:
			raise RuntimeError("Unable to get a chat!")
		return chat

	@classmethod
	def getParts(cls, source):
		"""
		Split the source and return required parts
		"""
		node, domain = source.split("@")
		if "_chat#" in node:
			creator, id = node.split("_chat#")
		else:
			return (None, None, None)
		return (int(creator), int(id), domain)

	@classmethod
	def getUserObject(cls, source):
		"""
		Gets user object by chat jid
		"""
		user = None
		jid = None
		creator, id, domain = cls.getParts(source)
		if domain == ConferenceServer and creator:
			jid = cls.getJIDByID(id)
		if not jid:
			jid = runDatabaseQuery("select user from groupchats where jid=?", (source,), many=False)
			if jid:
				jid = jid[0]
		if jid and jid in Transport:
			user = Transport[jid]
		return user

	@staticmethod
	def getJIDByID(id):
		for key, value in Transport.iteritems():
			if key == id:
				return value
		return None


def updateLastUsed(chat):
	"""
	Updates the last_used field in the database
	Args:
		chat: the Chat object
	"""
	runDatabaseQuery("update groupchats set last_used=? where jid=?", (time.time(), chat.source), set=True)


def exterminateChats(user=None, chats=[]):
	"""
	Calls a Dalek for exterminate the chat
	The chats argument must be a list of tuples
	"""
	def exterminated(cl, stanza, jid):
		"""
		The callback that's being called when the stanza we sent's got an answer
		Args:
			cl: the xmpp.Client object
			stanza: the result stanza
			jid: the jid stanza's sent from (?)
		"""
		chat = stanza.getFrom().getStripped()
		if xmpp.isResultNode(stanza):
			logger.debug("groupchats: target exterminated! Yay! target:%s (jid: %s)", chat, jid)
		else:
			logger.debug("groupchats: explain! Explain! "
				"The chat wasn't exterminated! Target: %s (jid: %s)", chat, jid)
			logger.error("groupchats: got stanza: %s (jid: %s)", str(stanza), jid)

	if user and not chats:
		chats = runDatabaseQuery("select jid, owner, user from groupchats where user=?", (user.source,))

	# current chats
	userChats = getattr(user, "chats", [])
	for (jid, owner, source) in chats:
		server = owner
		if "@" in owner:
			server = owner.split("@")[1]
		if server == TransportID:
			joinChat(jid, "Dalek", owner, "Exterminate!")
			logger.debug("groupchats: going to exterminate %s, owner:%s (jid: %s)", jid, owner, source)
			setChatConfig(jid, owner, True, exterminated, {"jid": jid})
			# remove the chat from current
			if jid in userChats:
				del userChats[jid]
		else:
			# if we try to send from another jid with prosody, we'll be killed
			logger.warning("Warning: Was the transport moved from other domain? Groupchat %s deletion skipped.", jid)
		runDatabaseQuery("delete from groupchats where jid=?", (jid,), set=True)


def initChatsTable():
	"""
	Initializes database if it doesn't exist
	"""
	def checkColumns():
		"""
		Checks and adds additional column(s) into the groupchats table
		"""
		info = runDatabaseQuery("pragma table_info(groupchats)")
		names = [col[1] for col in info]
		if "nick" not in names:
			logger.warning("groupchats: adding \"nick\" column to groupchats table")
			runDatabaseQuery("alter table groupchats add column nick text", set=True)

	runDatabaseQuery("create table if not exists groupchats "
		"(jid text, owner text,"
		"user text, last_used integer, nick text)", set=True)
	checkColumns()
	return True


def cleanTheChatsUp():
	"""
	Calls Dalek(s) to exterminate inactive users or their chats, whatever they catch
	"""
	chats = runDatabaseQuery("select jid, owner, last_used, user from groupchats")
	result = []
	for (jid, owner, last_used, user) in chats:
		if (time.time() - last_used) >= utils.TimeMachine(CHAT_LIFETIME_LIMIT):
			result.append((jid, owner, user))
			logger.debug("groupchats: time for %s expired (jid: %s)", jid, user)
	if result:
		exterminateChats(chats=result)
	utils.runThread(cleanTheChatsUp, delay=CHAT_CLEANUP_DELAY)


def initChatExtension():
	"""
	Initializes the extension"
	"""
	global mod_xhtml
	try:
		import mod_xhtml
	except ImportError:
		mod_xhtml = None
	if initChatsTable():
		if isdef("CHAT_LIFETIME_LIMIT"):
			cleanTheChatsUp()
		else:
			logger.warning("not starting chats cleaner because CHAT_LIFETIME_LIMIT is not set")


if isdef("ConferenceServer") and ConferenceServer:
	# G is for Groupchats. That's it.
	Handlers["msg03g"] = []

	GLOBAL_USER_SETTINGS["groupchats"] = {"label": "Handle groupchats",
		"desc": "If set, transport would create xmpp-chatrooms for VK Multi-Dialogs", "value": 1}

	GLOBAL_USER_SETTINGS["show_all_chat_users"] = {"label": "Show all chat users",
		"desc": "If set, transport will show ALL users in a conference", "value": 0}

	GLOBAL_USER_SETTINGS["tie_chat_to_nickname"] = {"label": "Tie chat to my nickname (tip: enable timestamp for groupchats)",
		"desc": "If set, your messages will be sent only from your nickname\n"\
		"(there is no way to determine whether message was sent\nfrom you or from the transport, so this setting might help,\nbut"\
		" there's one problem comes up: you wouldn't be able to send messages until the chat is initialized). "
		"\nChat initializes when first message received after transport's boot", "value": 1}

	GLOBAL_USER_SETTINGS["force_vk_date_group"] = {"label": "Force VK timestamp for groupchat messages", "value": 1}

	TRANSPORT_SETTINGS["destroy_on_leave"] = {"label": "Destroy groupchat if user leaves it", "value": 0}

	TransportFeatures.add(xmpp.NS_GROUPCHAT)
	registerHandler("msg01", handleOutgoingChatMessage)
	registerHandler("evt01", initChatExtension)
	registerHandler("evt03", exterminateChats)
	logger.info("extension groupchats is loaded")

else:
	del setAffiliation, inviteUser, joinChat, leaveChat, \
		handleOutgoingChatMessage, chatMessage, Chat, \
		exterminateChats, cleanTheChatsUp, initChatExtension
