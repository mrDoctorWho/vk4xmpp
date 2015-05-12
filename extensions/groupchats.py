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
"""

if not require("attachments") or not require("forwarded_messages"):
	raise AssertionError("extension 'groupchats' requires 'forwarded_messages' and 'attachments'")

try:
	import mod_xhtml
except ImportError:
	mod_xhtml = None


def setAffiliation(chat, role, jid, jidFrom=TransportID, reason=None):
	stanza = xmpp.Iq("set", to=chat, frm=jidFrom)
	query = xmpp.Node("query", {"xmlns": xmpp.NS_MUC_ADMIN})
	arole = query.addChild("item", {"jid": jid, "affiliation": role})
	if reason:
		arole.setTagData("reason", reason)
	stanza.addChild(node=query)
	sender(Component, stanza)


def inviteUser(chat, jidTo, jidFrom, name):
	invite = xmpp.Message(to=chat, frm=jidFrom)
	x = xmpp.Node("x", {"xmlns": xmpp.NS_MUC_USER})
	inv = x.addChild("invite", {"to": jidTo})
	inv.setTagData("reason", _("You're invited by user «%s»") % name)
	invite.addChild(node=x)
	sender(Component, invite)


def joinChat(chat, name, jidFrom, status=None):
	prs = xmpp.Presence("%s/%s" % (chat, name), frm=jidFrom, status=status)
	prs.setTag("c", {"node": "http://simpleapps.ru/caps/vk4xmpp", "ver": REVISION}, xmpp.NS_CAPS)
	sender(Component, prs)


def leaveChat(chat, jidFrom, reason=None):
	prs = xmpp.Presence(chat, "unavailable", frm=jidFrom, status=reason)
	sender(Component, prs)


def chatMessage(chat, text, jidFrom, subj=None, timestamp=0):
	message = xmpp.Message(chat, typ="groupchat")
	if timestamp:
		timestamp = time.gmtime(timestamp)
		message.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	if not subj:
		message.setBody(text)
	else:
		message.setSubject(text)
	message.setFrom(jidFrom)
	sender(Component, message)


def outgoingChatMessageHandler(self, vkChat):
	"""
	Handles outging messages (VK) and sends them to XMPP
	"""

	if vkChat.has_key("chat_id"):
		if not self.settings.groupchats:
			return None
		owner = vkChat.get("admin_id", "1")
		fromID = vkChat["uid"]
		chatID = vkChat["chat_id"]
		chatJID = "%s_chat#%s@%s" % (self.vk.userID, chatID, ConferenceServer)

		if not hasattr(self, "chats"):
			self.chats = {}

		if not self.vk.userID:
			logger.warning("groupchats: we didn't receive user id, trying again after 10 seconds (jid: %s)" % self.source)
			self.vk.getUserID()
			utils.runThread(outgoingChatMessageHandler, (self, vkChat), delay=10)
			return None

		if chatJID not in self.chats:
			chat = self.chats[chatJID] = Chat(owner, chatID, chatJID, vkChat["title"], vkChat["date"], vkChat["chat_active"].split(","))
			chat.create(self) ## we can add self, vkChat to the create() function to prevent losing or messing up the messages
		else:
			chat = self.chats[chatJID]
		## read the comments above the handleMessage function
		if not chat.created:
			time.sleep(1.5)
		chat.handleMessage(self, vkChat)
		return None
	return ""


class Chat(object):
	"""
	Class used for Chat handling
	"""
	def __init__(self, owner, id, jid, topic, date, users=[]):
		"""
		Initializes Chat class.
		Not obvious attributes:
			id: chat's id (int)
			jid: chat's jid (str)
			owner: owner's id (str)
			users: dictionary of ids, id: {"name": nickname, "jid": jid}
			raw_users: vk id's (list of str or int, hell knows)
			created: flag if the chat was created successfully
			invited: flag if the user was invited
			topic: chat's topic
			errors: list of chat's errors (not needed at this moment)
			creation_date: hell knows
		"""
		self.id = id
		self.jid = jid
		self.owner = owner
		self.users = {}
		self.raw_users = users
		self.created = False
		self.invited = False
		self.exists = False
		self.owner_nickname = None
		self.topic = topic
		self.errors = []
		self.creation_date = date

	def create(self, user):	
		"""
		Creates a chat, joins it and sets the config
		"""
		logger.debug("groupchats: creating %s. Users: %s; owner: %s (jid: %s)" %\
			 		(self.jid, self.raw_users, self.owner, user.source))
		
		exists = runDatabaseQuery("select user from groupchats where jid=?", (self.jid,), many=True)
		if exists:
			self.exists = True
			logger.debug("groupchats: groupchat %s exists in the database (jid: %s)" %\
						(self.jid, user.source))

		else:
			logger.debug("groupchats: groupchat %s will be added to the database (jid: %s)" %\
			 			(self.jid, user.source))
			runDatabaseQuery("insert into groupchats (jid, owner, user, last_used) values (?,?,?,?)", 
							(self.jid, TransportID, user.source, time.time()), True)

		name = user.vk.getUserData(self.owner)["name"]
		self.users[TransportID] = {"name": name, "jid": TransportID}
		## We join to the chat with the room owner's name to set the room topic from their name.
		joinChat(self.jid, name, TransportID, "Lost in time.")
		self.setConfig(self.jid, TransportID, False, self.onConfigSet, {"user": user})

	def initialize(self, user, chat):
		"""
		Initializes chat object: 
			1) requests users list if required
			2) makes them members
			3) invites the user 
			4) sets the chat topic
		Parameters:
			chat: chat's jid
		"""
		if not self.raw_users:
			vkChat = self.getVKChat(user, self.id)
			if not vkChat and not self.invited:
				logger.error("groupchats: damn vk didn't answer to chat list"\
							"request, starting timer to try again (jid: %s)" % user.source)
				utils.runThread(self.initialize, (user, chat), delay=10)
				return False
			self.raw_users = vkChat.get("users")

		name = "@%s" % TransportID
		setAffiliation(chat, "member", user.source)
		if not self.invited:
			inviteUser(chat, user.source, TransportID, user.vk.getUserData(self.owner)["name"])
			self.invited = True
		logger.debug("groupchats: user has been invited to chat %s (jid: %s)" % (chat, user.source))
		chatMessage(chat, self.topic, TransportID, True, self.creation_date)
		joinChat(chat, name, TransportID, "Lost in time.") ## let's rename ourselves
		self.users[TransportID] = {"name": name, "jid": TransportID}

	def update(self, userObject, vkChat):
		"""
		Updates chat users and sends messages
		Uses two users list to prevent losing anyone
		"""
		all_users = vkChat["chat_active"].split(",") or []
		all_users = [int(user) for user in all_users if user]
		if userObject.settings.show_all_chat_users:
			users = self.getVKChat(userObject, self.id)
			if users:
				all_users = users.get("users", [])

		old_users = self.users.keys()
		buddies = all_users + old_users
		if TransportID in buddies:
			buddies.remove(TransportID)

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

		topic = vkChat["title"]
		if topic != self.topic:
			chatMessage(self.jid, topic, TransportID, True)
			self.topic = topic
		self.raw_users = all_users

	@classmethod
	def setConfig(cls, chat, jidFrom, exterminate=False, cb=None, args={}):
		"""
		Sets the chat config
		"""
		iq = xmpp.Iq("set", to=chat, frm=jidFrom)
		query = iq.addChild("query", namespace=xmpp.NS_MUC_OWNER)
		if exterminate:
			query.addChild("destroy")
		else:
			form = utils.buildDataForm(fields=[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_MUC_ROOMCONFIG},
				{"var": "muc#roomconfig_membersonly", "type": "boolean", "value": "1"},
				{"var": "muc#roomconfig_publicroom", "type": "boolean", "value": "0"},
				{"var": "muc#roomconfig_persistent", "type": "boolean", "value": "1"},
				{"var": "muc#roomconfig_whois", "value": "anyone"}], 
				type="submit")
			query.addChild(node=form)
		sender(Component, iq, cb, args)

	def onConfigSet(self, cl, stanza, user):
		"""
		Called when the chat config has been set
		"""
		chat = stanza.getFrom().getStripped()
		if xmpp.isResultNode(stanza):
			self.created = True
			logger.debug("groupchats: stanza \"result\" received from %s,"\
			 			 "continuing initialization (jid: %s)", chat, user.source)
			utils.execute(self.initialize, (user, chat))
		else:
			logger.error("groupchats: couldn't set room %s config, the answer is: %s (jid: %s)",
				chat, str(stanza), user.source)

	# here is a possibility to get messed up if many messages were sent before we created the chat 
	# we have to send the messages immendiately as soon as possible, so delay can mess the messages up
	def handleMessage(self, user, vkChat, retry=10):
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
			logger.debug("groupchats: chat %s wasn't created well, so trying to create it again (jid: %s)" % (self.jid, source))
			logger.warning("groupchats: is there any groupchat limit on the server?")
			if retry:
				utils.runThread(self.handleMessage, (user, vkChat, (retry - 1)), delay=(10 - retry))

	@api.attemptTo(3, dict, RuntimeError)
	def getVKChat(cls, user, id):
		"""
		Get vk chat by id
		"""
		chat = user.vk.method("messages.getChat", {"chat_id": id})
		if not chat:
			raise RuntimeError("Well, this is embarrassing.")
		return chat

	@classmethod
	def getParts(cls, source):
		"""
		Split the source and returns required parts
		"""
		node, domain = source.split("@")
		if "_chat#" in node:  # Custom chat name?
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
			jid = runDatabaseQuery("select user from groupchats where jid=?", (source,), many=False, semph=None)
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


def incomingChatMessageHandler(msg):
	"""
	Handles incoming (xmpp) messages and sends them to VK
	"""
	if msg.getType() == "groupchat":
		body = msg.getBody()
		destination = msg.getTo().getStripped()
		nick = msg.getFrom().getResource()
		source = msg.getFrom().getStripped()
		if mod_xhtml:
			html = msg.getTag("html")
		else:
			html = None

		x = msg.getTag("x", {"xmlns": xmpp.NS_MUC_USER})
		if x and x.getTagAttr("status", "code") == "100":
			raise xmpp.NodeProcessed()

		if not msg.getTimestamp() and body and destination == TransportID:
			user = Chat.getUserObject(source)
			creator, id, domain = Chat.getParts(source)
			send = False
			owner_nickname = None
			if user: 
				if source in getattr(user, "chats", {}):
					owner_nickname = user.chats[source].owner_nickname
				if not owner_nickname:
					owner_nickname = runDatabaseQuery("select nick from groupchats where jid=?",
						(source,), many=False)[0]
				# None of “normal” clients will send messages with timestamp
				# If we do (as we set in force_vk_date_group), then the message received from a user
				# If we don't and nick (as in settings) is tied to the chat, then we can determine who sent the message
				send = ((nick == owner_nickname and user.settings.tie_chat_to_nickname)
					or user.settings.force_vk_date_group)

				if html and html.getTag("body"): ## XHTML-IM!
					logger.debug("groupchats: fetched xhtml image (jid: %s)" % source)
					try:
						mod_xhtml.parseXHTML(user, html, source, source, "chat_id")
					except Exception:
						pass
					else:
						# Don't send a message if there's an image
						raise xmpp.NodeProcessed()
				if send:
					with user.sync:
						user.vk.sendMessage(body, id, "chat_id")
					runDatabaseQuery("update groupchats set last_used=? where jid=?", (time.time(), source), set=True)
					raise xmpp.NodeProcessed()


def handleChatErrors(source, prs):
	"""
	Handles error presences from groupchats
	"""
	## todo: leave on 401, 403, 405
	## and rejoin timer on 404, 503
	destination = prs.getTo().getStripped()
	error = prs.getErrorCode()
	status = prs.getStatusCode()
	nick = prs.getFrom().getResource()
	jid = prs.getJid()
	user = None
	if status or prs.getType() == "error":
		user = Chat.getUserObject(source)
		if user and source in getattr(user, "chats", {}):
			chat = user.chats[source]
			if error == "409":
				id = vk2xmpp(destination)
				if id in chat.users:
					nick += "."
					if not chat.created and id == TransportID:
						chat.users[id]["name"] = nick
						chat.create(user)
					else:
						joinChat(source, nick, destination)

			if status == "303":
				if jid == user.source:
					chat.owner_nickname = prs.getNick()
					runDatabaseQuery("update groupchats where jid=? set nick=?",
									(source, chat.owner_nickname), set=True, semph=None)

		logger.debug("groupchats: presence error (error #%s, status #%s)" \
			"from source %s (jid: %s)" % (error, status, source, user.source if user else "unknown"))


def handleChatPresences(source, prs):
	"""
	Makes old users leave
	Parameters:
		* source: stanza source
		* prs: xmpp.Presence object
	"""
	jid = prs.getJid()
	if jid and "@" in jid:
		user = Chat.getUserObject(source)
		if user and source in getattr(user, "chats", {}):
			chat = user.chats[source]
			if jid.split("@")[1] == TransportID and chat.created:
				id = vk2xmpp(jid)
				if id != TransportID and id not in chat.users.keys():
					if (time.gmtime().tm_mon, time.gmtime().tm_mday) == (4, 1):
						setAffiliation(source, "outcast", jid, reason=_("Get the hell outta here!"))
					else:
						leaveChat(source, jid, _("I am not welcomed here"))

				if (prs.getRole(), prs.getAffiliation()) == ("moderator", "owner"):
					if jid != TransportID:
						runDatabaseQuery("update groupchats set owner=? where jid=?", (source, jid), set=True, semph=None)

			if jid.split("/")[0] == user.source:
				chat.owner_nickname = prs.getFrom().getResource()
				runDatabaseQuery("update groupchats set nick=? where jid=? ", (chat.owner_nickname, source), set=True, semph=None)

			if prs.getType() == "unavailable" and jid == user.source:
				if transportSettings.destroy_on_leave:
					exterminateChats(chats=[source])


def exterminateChats(user=None, chats=[]):
	"""
	Calls a Dalek for exterminate the chat
	The chats argument must be a list of tuples
	"""
	def exterminated(cl, stanza, jid):
		"""
		Our Dalek is happy now!
		"""
		chat = stanza.getFrom().getStripped()
		if xmpp.isResultNode(stanza):
			logger.debug("groupchats: target exterminated! Yay! target:%s (jid: %s)" % (chat, jid))
			runDatabaseQuery("delete from groupchats where jid=?", (chat,), set=True, semph=None)
		else:
			logger.debug("groupchats: explain! Explain! " \
				"The chat wasn't exterminated well! target:%s (jid: %s)" % (chat, jid))
			logger.error("groupchats: got stanza: %s (jid: %s)" % (str(stanza), jid))

	if user:
		chats = runDatabaseQuery("select jid, owner, user from groupchats where user=?", (user.source,), semph=None)
		source = user.source
		userChats = getattr(user, "chats", {})
	else:
		userChats = []

	for (jid, owner, source) in chats:
		joinChat(jid, "Dalek", owner)
		logger.debug("groupchats: going to exterminate %s, owner:%s (jid: %s)" % (jid, owner, source))
		Chat.setConfig(jid, owner, True, exterminated, {"jid": jid})
		if jid in userChats:
			del userChats[jid]


def initChatsTable():
	"""
	Initializes database if it doesn't exist
	"""
	def checkColumns():
		info = runDatabaseQuery("pragma table_info(groupchats)", semph=Semaphore)
		names = [col[1] for col in info]
		if not "nick" in names:
			logger.warning("groupchats: adding \"nick\" column to groupchats table")
			runDatabaseQuery("alter table groupchats add column nick text", set=True, semph=Semaphore)

	runDatabaseQuery("create table if not exists groupchats " \
		"(jid text, owner text," \
		"user text, last_used integer, nick text)", set=True, semph=Semaphore)
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
			logger.debug("groupchats: time for %s expired (jid: %s)" % (jid, user))
	if result:
		exterminateChats(chats=result)
	utils.runThread(cleanTheChatsUp, delay=(60*60*24))


def initChatExtension():
	if initChatsTable():
		if isdef("CHAT_LIFETIME_LIMIT"):
			cleanTheChatsUp()
		else:
			logger.warning("not starting chats cleaner because CHAT_LIFETIME_LIMIT is not set")


if isdef("ConferenceServer") and ConferenceServer:
	GLOBAL_USER_SETTINGS["groupchats"] = {"label": "Handle groupchats", 
		"desc": "If set, transport would create xmpp-chatrooms for VK Multi-Dialogs", "value": 1}

	GLOBAL_USER_SETTINGS["show_all_chat_users"] = {"label": "Show all chat users", 
		"desc": "If set, transport will show ALL users in a conference, even you", "value": 0}

	GLOBAL_USER_SETTINGS["tie_chat_to_nickname"] = {"label": "Tie chat to my nickname (tip: enable timestamp for groupchats)",
		"desc": "If set, your messages will be sent only from your nickname\n"\
		"(there is no way to determine whether a message was sent\nfrom you or from the transport, so this setting might help,\nbut"\
		" it will bring one bug: you wont be able to send any message if chat is not initialized). "
		"\nChat initializes when first message received after transport's boot", "value": 1}

	GLOBAL_USER_SETTINGS["force_vk_date_group"] = {"label": "Force VK timestamp for groupchat messages", "value": 1}

	TRANSPORT_SETTINGS["destroy_on_leave"] = {"label": "Destroy groupchat if user leaves it", "value": 0}

	TransportFeatures.add(xmpp.NS_GROUPCHAT)
	registerHandler("msg01", outgoingChatMessageHandler)
	registerHandler("msg02", incomingChatMessageHandler)
	registerHandler("prs01", handleChatErrors)
	registerHandler("prs01", handleChatPresences)
	registerHandler("evt01", initChatExtension)
	registerHandler("evt03", exterminateChats)
	logger.info("extension groupchats is loaded")

else:
	del setAffiliation, inviteUser, joinChat, leaveChat, \
		outgoingChatMessageHandler, chatMessage, Chat, \
		incomingChatMessageHandler, handleChatErrors, handleChatPresences, exterminateChats, \
		cleanTheChatsUp, initChatExtension
