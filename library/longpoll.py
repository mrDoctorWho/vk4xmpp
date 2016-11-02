# coding: utf-8
# © simpleApps, 2014 — 2016.

__authors__ = ("Al Korgun <alkorgun@gmail.com>", "John Smith <mrdoctorwho@gmail.com>")
__version__ = "2.2.2"
__license__ = "MIT"

"""
Implements a single-threaded longpoll client
"""

import threading
import time
import vkapi as api
import select
import socket
import utils
from __main__ import Transport, logger, ALIVE, DEBUG_POLL, crashLog

LONGPOLL_RETRY_COUNT = 10
LONGPOLL_RETRY_TIMEOUT = 10


# TODO: make it an abstract, to reuse in Steampunk
class Poll(object):
	"""
	Class used to handle longpoll
	"""
	__list = {}
	__buff = set()
	__lock = threading.Lock()
	clear = staticmethod(__list.clear)

	@classmethod
	def __add(cls, user):
		"""
		Issues readable socket to use it in select()
		Adds user in buffer on error occurred
		Adds user in self.__list if no errors
		"""
		if user.source in Transport:
			# in case the new instance was created
			user = Transport[user.source]
			opener = user.vk.makePoll()
			if DEBUG_POLL:
				logger.debug("longpoll: user has been added to poll (jid: %s)", user.source)
			if opener:
				cls.__list[opener.sock] = (user, opener)
				return opener
			logger.warning("longpoll: got null opener! (jid: %s)", user.source)
			cls.__addToBuffer(user)
			return None

	@classmethod
	def add(cls, some_user):
		"""
		Adds the User class object to poll
		"""
		if DEBUG_POLL:
			logger.debug("longpoll: adding user to poll (jid: %s)", some_user.source)
		with cls.__lock:
			if some_user in cls.__buff:
				return None
			# check if someone tries to add an already existing user
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
		for i in xrange(LONGPOLL_RETRY_COUNT):
			if user.source in Transport:
				user = Transport[user.source]  # we  might have a new instance here
				if user.vk.initPoll():
					with cls.__lock:
						logger.debug("longpoll: successfully initialized longpoll (jid: %s)", user.source)
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
			# TODO: epoll()?
			try:
				ready, error = select.select(socks, [], socks, 2)[::2]
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
					user = Transport.get(user.source)
					utils.runThread(cls.processResult, (user, opener),
						"poll.processResult-%s" % user.source)

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
	def processResult(cls, user, opener):
		"""
		Processes the select result (see above)
		Handles answers from user.processPollResult()
		Decides if need to add user to poll or not
		"""
		result = utils.execute(user.processPollResult, (opener,))
		if DEBUG_POLL:
			logger.debug("longpoll: result=%s (jid: %s)", result, user.source)
		if result == -1:
			return None
		# if we'll set user.vk.pollInitialized to False
		# then makePoll() will raise an exception
		# by doing that, we force user's poll reinitialization
		if not result:
			user.vk.pollInitialized = False
		cls.add(user)

