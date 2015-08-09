# coding: utf-8
# © simpleApps, 2014 — 2015.

# Big THANKS to AlKogrun who made it possible
# to write a single-threaded longpoll client

__authors__ = ("AlKorgun <alkorgun@gmail.com>", "mrDoctorWho <mrdoctorwho@gmail.com>")
__version__ = "2.2.1"
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

class Poll:
	"""
	Class used to handle longpoll
	"""
	__list = {}
	__buff = set()
	__lock = threading._allocate_lock()

	@classmethod
	def __add(cls, user):
		"""
		Issues readable socket to use it in select()
		Adds user in buffer on error occurred
		Adds user in self.__list if no errors
		"""
		try:
			opener = user.vk.makePoll()
		except Exception as e:
			if not isinstance(e, api.LongPollError):
				crashLog("poll.add")
			logger.error("longpoll: failed to make poll (jid: %s)" % user.source)
			cls.__addToBuff(user)
			return False
		else:
			cls.__list[opener.sock] = (user, opener)
		return opener

	@classmethod
	def __addToBuff(cls, user):
		"""
		Adds user to the list of "bad" users
		The list is mostly contain users whose poll
			request was failed for some reasons
		"""
		cls.__buff.add(user)
		logger.debug("longpoll: adding user to watcher (jid: %s)" % user.source)
		utils.runThread(cls.__initPoll, (user,), "__initPoll-%s" % user.source)

	@classmethod
	def add(cls, some_user):
		"""
		Adds the User class object to poll
		"""
		with cls.__lock:
			if some_user in cls.__buff:
				return None
			for sock, (user, opener) in cls.__list.iteritems():
				if some_user == user:
					break
			else:
				cls.__add(some_user)

	clear = staticmethod(__list.clear)

	@classmethod
	def __initPoll(cls, user):
		"""
		Tries to reinitialize poll if needed in 10 times (each 10 seconds)
		As soon as poll initialized user will be removed from buffer
		"""
		for x in xrange(10):
			if user.source not in Transport:
				logger.debug("longpoll: while we were wasting our time"
					", the user has left (jid: %s)" % user.source)
				with cls.__lock:
					if user in cls.__buff:
						cls.__buff.remove(user)
				return None

			if Transport[user.source].vk.initPoll():
				with cls.__lock:
					logger.debug("longpoll: successfully initialized longpoll (jid: %s)"
						% user.source)
					if user not in cls.__buff:
						return None
					cls.__buff.remove(user)
					# Check if user still in transport when we finally came down here
					if user.source in Transport:
						cls.__add(Transport[user.source])
					break
			time.sleep(10)
		else:
			with cls.__lock:
				if user not in cls.__buff:
					return None
				cls.__buff.remove(user)
			logger.error("longpoll: failed to add user to poll in 10 retries (jid: %s)"
				% user.source)

	@classmethod
	def process(cls):
		"""
		Processes poll sockets by select.select()
		As soon as socket will be ready to be read
			will be called user.processPollResult() function
		Read processPollResult.__doc__ to learn more about status codes
		"""
		while ALIVE:
			socks = cls.__list.keys()
			if not socks:
				time.sleep(0.02)
				continue
			try:
				ready, error = select.select(socks, [], socks, 2)[::2]
			except (select.error, socket.error) as e:
				logger.error("longpoll: %s", e.message)  # debug?

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

					# Check if user is still in the memory
					user = Transport.get(user.source)
					# Check if the user haven't left yet
					if not hasattr(user, "vk") or not user.vk.online:
						continue

					utils.runThread(cls.processResult, (user, opener),
						"poll.processResult-%s" % user.source)

			with cls.__lock:
				for sock, (user, opener) in cls.__list.items():
					if hasattr(user, "vk") and not user.vk.online:
						logger.debug("longpoll: user is not online, so removing them from poll"
							" (jid: %s)" % user.source)
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
			logger.debug("longpoll: result=%s (jid: %s)" % (result, user.source))
		if result == -1:
			return None
		# if we'll set user.vk.pollInitialized to False
		# then an exception will be raised
		# if we do that user will be reinitialized
		if not result:
			user.vk.pollInitialzed = False
		cls.add(user)

 
