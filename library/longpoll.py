# coding: utf-8
# © simpleApps, 2014 — 2016.

__authors__ = ("Al Korgun <alkorgun@gmail.com>", "John Smith <mrdoctorwho@gmail.com>")
__version__ = "2.3"
__license__ = "MIT"

"""
Implements a single-threaded longpoll client
"""

import select
import socket
import json
import httplib
import threading
import time
import vkapi as api

import utils

from __main__ import *

SOCKET_CHECK_TIMEOUT = 10
LONGPOLL_RETRY_COUNT = 10
LONGPOLL_RETRY_TIMEOUT = 10
SELECT_WAIT = 25
OPENER_LIFETIME = 60


CODE_SKIP = -1
CODE_FINE = 0
CODE_ERROR = 1

TYPE_MSG = 4
TYPE_MSG_EDIT = 5
TYPE_MSG_READ_IN = 6  # we read the message
TYPE_MSG_READ_OUT = 7  # they read the message
TYPE_PRS_IN = 8
TYPE_PRS_OUT = 9
TYPE_TYPING = 61

FLAG_OUT = 2
FLAG_CHAT = 16

MIN_CHAT_UID = 2000000000

TCP_KEEPINTVL = 60
TCP_KEEPIDLE = 60


def debug(message, *args):
	if DEBUG_POLL:
		logger.debug(message, *args)


def read(opener, source):
	"""
	Read a socket ignoring errors
	Args:
		opener: a socket to read
		source: the user's jid
	Returns:
		JSON data or an empty string
	"""
	try:
		data = opener.read()
	except (httplib.BadStatusLine, socket.error, socket.timeout) as e:
		data = ""
		logger.warning("longpoll: got error `%s` (jid: %s)", e.message, source)
	return data


def processPollResult(user, data):
	"""
	Processes a poll result
	Decides whether to send a chat/groupchat message or presence or just pass the iteration
	Args:
		user: the User object
		data: a valid json with poll result
	Returns:
		CODE_SKIP: just skip iteration, not adding the user to poll again
		CODE_FINE: add user for the next iteration
		CODE_ERROR: user should be added to the init buffer
	"""
	debug("longpoll: processing result (jid: %s)", user.source)

	retcode = CODE_FINE
	try:
		data = json.loads(data)
	except ValueError:
		logger.error("longpoll: no data. Gonna request again (jid: %s)",
					user.source)
		retcode = CODE_ERROR
		return retcode

	if "failed" in data:
		logger.debug("longpoll: failed. Searching for a new server (jid: %s)", user.source)
		retcode = CODE_ERROR
	else:
		user.vk.pollConfig["ts"] = data["ts"]
		for evt in data.get("updates", ()):
			typ = evt.pop(0)

			debug("longpoll: got updates, processing event %s with arguments %s (jid: %s)",
				typ, str(evt), user.source)

			if typ == TYPE_MSG:  # new message
				message = None
				mid, flags, uid, date, subject, body, attachments = evt
				out = flags & FLAG_OUT
				chat = (uid > MIN_CHAT_UID)  # a groupchat always has uid > 2000000000
				if not out:
					if not attachments and not chat:
						message = [{"out": 0, "uid": uid, "mid": mid, "date": date, "body": body}]
					utils.runThread(user.sendMessages, (False, message, mid - 1, uid), "sendMessages-%s" % user.source)

			elif typ == TYPE_MSG_READ_OUT:
				uid, mid = evt
				cache = user.msgCacheByUser.get(uid)
				if cache:
					xmppMID = cache["xmpp"]
					cache.clear()
					sendChatMarker(user.source, vk2xmpp(uid), xmppMID)

			elif typ == TYPE_PRS_IN:  # user has joined
				uid = abs(evt[0])
				sendPresence(user.source, vk2xmpp(uid), hash=USER_CAPS_HASH)

			elif typ == TYPE_PRS_OUT:  # user has left
				uid = abs(evt[0])
				sendPresence(user.source, vk2xmpp(uid), "unavailable")

			elif typ == TYPE_TYPING:  # user is typing
				uid = evt[0]
				if uid not in user.typing:
					sendMessage(user.source, vk2xmpp(uid), typ="composing")
				user.typing[uid] = time.time()
			retcode = CODE_FINE
	return retcode


def configureSocket(sock):
	# see man(7) tcp
	debug("setting socket parameters...")
	try:
		# enable keepalive probes
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		# the interval between subsequential keepalive probes, regardless of what the connection has exchanged in the meantime
		# overrides  tcp_keepalive_intvl
		sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, TCP_KEEPINTVL)
		# the interval between the last data packet sent (simple ACKs are not considered data) and the first keepalive probe;
		# after the connection is marked to need keepalive, this counter is not used any further
		# overrides tcp_keepalive_time
		sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, TCP_KEEPIDLE)
	except (AttributeError, OSError):
		debug("unable to set socket parameters")


# TODO: make it abstract, to reuse in Steampunk
class Poll(object):
	"""
	Class used to handle longpoll
	"""
	__list = {}
	__buff = set()
	__lock = threading.Lock()
	clear = staticmethod(__list.clear)
	watchdogRunning = False

	@classmethod
	def init(cls):
		cls.watchdogRunning ^= True
		cls.watchdog()

	@classmethod
	def __add(cls, user):
		"""
		Issues a readable socket to use it in select()
		Adds user in buffer if a error occurred
		Adds user in cls.__list if no errors
		"""
		if user.source in Users:
			# in case the new instance was created
			user = Users[user.source]
			opener = user.vk.makePoll()
			debug("longpoll: user has been added to poll (jid: %s)", user.source)
			if opener:
				sock = opener.sock
				configureSocket(sock)
				cls.__list[sock] = (user, opener)
				return opener
			logger.warning("longpoll: got null opener! (jid: %s)", user.source)
			cls.__addToBuffer(user)

	@classmethod
	def add(cls, some_user):
		"""
		Adds the User class object to poll
		"""
		debug("longpoll: adding user to poll (jid: %s)", some_user.source)
		with cls.__lock:
			if some_user in cls.__buff:
				return None
			# check if someone is trying to add an already existing user
			for sock, (user, opener) in cls.__list.iteritems():
				if some_user == user:
					break
			else:
				try:
					cls.__add(some_user)
				except api.LongPollError:
					logger.error("longpoll: failed to make poll (jid: %s)", some_user.source)
					cls.__addToBuffer(some_user)
				except Exception:
					crashLog("poll.add")

	@classmethod
	def __addToBuffer(cls, user):
		"""
		Adds user to the list of "bad" users
		The list is mostly contain users whose poll
			request was failed for some reasons
		Args:
			user: the user object
		"""
		cls.__buff.add(user)
		logger.debug("longpoll: adding user to the init buffer (jid: %s)", user.source)
		utils.runThread(cls.handleUser, (user,), "handleBuffer-%s" % user.source)

	@classmethod
	def __removeFromBuffer(cls, user):
		"""
		Instantly removes a user from the buffer
		Args:
			user: the user object
		"""
		if user in cls.__buff:
			cls.__buff.remove(user)

	@classmethod
	def removeFromBuffer(cls, user):
		"""
		Removes a user from the buffer
		Args:
			user: the user object
		"""
		with cls.__lock:
			cls.__removeFromBuffer(user)

	@classmethod
	def handleUser(cls, user):
		"""
		Tries to reinitialize poll for LONGPOLL_RETRY_COUNT every LONGPOLL_RETRY_TIMEOUT seconds
		As soon as poll is initialized the user will be removed from buffer
		Args:
			user: the user object
		"""
		for _ in xrange(LONGPOLL_RETRY_COUNT):
			if user.source in Users:
				user = Users[user.source]  # we  might have a new instance here
				if user.vk.initPoll():
					with cls.__lock:
						logger.debug("longpoll: successfully initialized longpoll (jid: %s)",
								user.source)
						cls.__add(user)
						cls.__removeFromBuffer(user)
					break
			else:
				logger.debug("longpoll: while we were wasting our time"
							", the user has left (jid: %s)", user.source)
				cls.removeFromBuffer(user)
				return None
			time.sleep(LONGPOLL_RETRY_TIMEOUT)
		else:
			cls.removeFromBuffer(user)
			logger.error("longpoll: failed to add user to poll in 10 retries"
					" (jid: %s)", user.source)

	@classmethod
	def process(cls):
		"""
		Processes poll sockets by select.select()
		As soon as socket will be ready for reading,  user.processPollResult() is called
		Read processPollResult.__doc__ to learn more about status codes
		"""
		while ALIVE:
			socks = cls.__list.keys()
			if not socks:
				time.sleep(0.02)
				continue
			try:
				ready, error = select.select(socks, [], socks, SELECT_WAIT)[::2]
			except (select.error, socket.error, socket.timeout) as e:
				logger.error("longpoll: %s", e.message)
				continue

			for sock in error:
				with cls.__lock:
					# We will just re-add the user to poll
					# in case if anything weird happen to the socket
					try:
						cls.__add(cls.__list.pop(sock)[0])
					except KeyError:
						continue

			for sock in ready:
				with cls.__lock:
					try:
						user, opener = cls.__list.pop(sock)
					except KeyError:
						continue

					# Update the user instance
					user = Users.get(user.source)
					if user:
						cls.processResult(user, opener)

			with cls.__lock:
				for sock, (user, opener) in cls.__list.items():
					if hasattr(user, "vk") and not user.vk.online:
						logger.debug("longpoll: user is not online, so removing them from poll"
									" (jid: %s)", user.source)
						try:
							del cls.__list[sock]
						except KeyError:
							pass

	@classmethod
	@utils.threaded
	def processResult(cls, user, opener):
		"""
		Processes the select result (see above)
		Handles answers from user.processPollResult()
		Decides if need to add user to poll or not
		"""
		data = read(opener, user.source)
		result = utils.execute(processPollResult, (user, data,))
		debug("longpoll: result=%s (jid: %s)", result, user.source)
		if result == CODE_SKIP:
			return None
		# if we set user.vk.pollInitialized to False
		# then makePoll() will throw an exception
		# by doing so, we force the user's poll to be reinitialized
		if result == CODE_ERROR:
			user.vk.pollInitialized = False
		cls.add(user)

	@classmethod
	@utils.threaded
	def watchdog(cls):
		while cls.watchdog:
			for sock, (user, opener) in cls.__list.items():
				if (time.time() - opener.created) > OPENER_LIFETIME:
					with cls.__lock:
						try:
							del cls.__list[sock]
							cls.processResult(user, opener)
						except KeyError:
							pass
			time.sleep(SOCKET_CHECK_TIMEOUT)
