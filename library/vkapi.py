# coding: utf-8
# © simpleApps, 2013 — 2016.

"""
Manages VK API requests
Provides password login and direct VK API calls
Designed for huge number of clients (per ip)
Which is why it has that lot of code
"""

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"

import cookielib
import httplib
import logging
import re
import socket
import ssl
import time
import threading
import urllib
import urllib2
import webtools
from printer import *

SOCKET_TIMEOUT = 20
REQUEST_RETRIES = 3

# VK APP ID
APP_ID = 3789129
# VK APP scope
SCOPE = 69638
# VK API VERSION
API_VERSION = "5.21"

socket.setdefaulttimeout(SOCKET_TIMEOUT)

logger = logging.getLogger("vk4xmpp")

token_exp = re.compile("(([\da-f]+){11,})", re.IGNORECASE)

ERRORS = (httplib.BadStatusLine,
	urllib2.URLError,
	socket.gaierror,
	socket.timeout,
	socket.error,
	ssl.SSLError)

METHOD_THROUGHPUT = 3.0

# Trying to use faster library usjon instead of simplejson
try:
	import ujson as json
	logger.debug("vkapi: using ujson instead of simplejson")
except ImportError:
	import json
	logger.warning("vkapi: ujson wasn't loaded, using simplejson instead")


def repeat(maxRetries, resultType, *errors):
	"""
	Tries to execute function ignoring specified errors specified number of
	times and returns specified result type on try limit.
	"""
	if not isinstance(resultType, type):
		resultType = lambda result = resultType: result
	if not errors:
		errors = Exception

	def decorator(func):

		def wrapper(*args, **kwargs):
			retries = 0
			while retries < maxRetries:
				try:
					data = func(*args, **kwargs)
				except errors as exc:
					retries += 1
					logger.warning("vkapi: trying to execute \"%s\" in #%d time",
						func.func_name, retries)
					time.sleep(0.2)
				else:
					break
			else:
				errno = getattr(exc, "errno", 0)
				if errno == 101:
					raise NetworkNotFound()
				elif errno == 104:
					raise NetworkError()
				data = resultType()
				logger.warning("vkapi: Error %s occurred on executing %s(*%s, **%s)",
					exc,
					func.func_name,
					str(args),
					str(kwargs))
			return data

		wrapper.__name__ = func.__name__
		return wrapper

	return decorator


class AsyncHTTPRequest(httplib.HTTPSConnection):
	"""
	A method to make asynchronous http requests
	Provides a way to get a socket object to use in select()
	"""
	def __init__(self, url, data=None, headers=(), timeout=SOCKET_TIMEOUT):
		host = urllib.splithost(urllib.splittype(url)[1])[0]
		httplib.HTTPSConnection.__init__(self, host, timeout=timeout)
		self.url = url
		self.data = data
		self.headers = headers or {}
		self.created = time.time()

	@repeat(REQUEST_RETRIES, None, *ERRORS)
	def open(self):
		self.connect()
		self.request(("POST" if self.data else "GET"), self.url, self.data,
			self.headers)
		return self

	def read(self):
		with self as resp:
			return resp.read()

	def __enter__(self):
		return self.getresponse()

	def __exit__(self, *args):
		self.close()

	@staticmethod
	def getOpener(url, query=None):
		"""
		Opens a connection to url and returns AsyncHTTPRequest() object
		Args: query a dict() of query parameters
		"""
		if query:
			url += "?%s" % urllib.urlencode(query)
		return AsyncHTTPRequest(url).open()


class RequestProcessor(object):
	"""
	Processes base requests:
		POST (application/x-www-form-urlencoded and multipart/form-data)
		GET
	"""
	headers = {"User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0)"
					" Gecko/20130309 Firefox/21.0",
				"Accept-Language": "ru-RU, utf-8"}
	boundary = "github.com/mrDoctorWho/vk4xmpp"

	def __init__(self, cook=False):
		if cook:
			cookieJar = cookielib.CookieJar()
			cookieProcessor = urllib2.HTTPCookieProcessor(cookieJar)
			self.open = urllib2.build_opener(cookieProcessor).open
			self.getCookie = lambda name: [c.value for c in cookieJar if c.name == name]
		else:
			self.open = urllib2.build_opener().open

	def multipart(self, key, name, ctype, data):
		"""
		Makes multipart/form-data encoding
		Parameters:
			key: form key (is there a form?)
			name: filename
			ctype: content type
			data: the data you want to send
		"""
		boundary = "--%s" % self.boundary
		disposition = "Content-Disposition: form-data; name=\"%s\"; filename=\"%s\""\
		% (key, name)
		ctype = "Content-Type: %s" % ctype
		header = "%(boundary)s\n%(disposition)s\n%(ctype)s\n\n" % vars()
		footer = "\n%s--\n" % boundary
		return header + data + footer

	def request(self, url, data=None, headers=None, urlencode=True):
		"""
		Makes a http(s) request
		Parameters:
			url: a request url
			data: a request data
			headers: a request headers (if not set, self.headers will be used)
			urlencode: urlencode flag
		"""
		headers = headers or self.headers
		if data and urlencode:
			headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
			data = urllib.urlencode(data)
		else:
			headers["Content-Type"] = "multipart/form-data; boundary=%s" % self.boundary
		request = urllib2.Request(url, data, headers)
		return request

	@repeat(REQUEST_RETRIES, tuple, *ERRORS)
	def post(self, url, data=None, urlencode=True):
		"""
		POST request
		"""
		resp = self.open(self.request(url, data, urlencode=urlencode))
		body = resp.read()
		return (body, resp)

	def get(self, url, query=None):
		"""
		GET request
		Args:
			query: a dict() of query parameters
		"""
		if query:
			url += "?%s" % urllib.urlencode(query)
		resp = self.open(self.request(url))
		body = resp.read()
		return (body, resp)


class PasswordLogin(RequestProcessor):
	"""
	Provides a way to log-in by a password
	"""
	def __init__(self, number, password):
		self.number = number
		self.password = password
		RequestProcessor.__init__(self, cook=True)

	def login(self):
		"""
		Logging in using password
		"""
		url = "https://login.vk.com/"
		values = {"act": "login", "email": self.number, "pass": self.password}

		body, response = self.post(url, values)

		if "sid=" in response.url:
			logger.error("vkapi: PasswordLogin ran into a captcha! (number: %s)",
				self.number)
			raise AuthError("Captcha!")

		if not self.getCookie("remixsid"):
			raise AuthError("Invalid password")

		if "security_check" in response.url:
			logger.warning("vkapi: PasswordLogin ran into a security check (number: %s)",
				self.number)
			hash = re.search("security_check.*?hash: '(.*?)'\};", body).group(0)
			if not self.number[0] == "+":
				self.number = "+" + self.number

			code = self.number[2:-2]  # valid for Russia only. Unfortunately.
			values = {"act": "security_check", "al": "1", "al_page": "3",
				"code": code, "hash": hash, "to": ""}
			post = self.post("https://vk.com/login.php", values)
			body, response = post
			if response and not body.split("<!>")[4] == "4":
				raise AuthError("Incorrect number")
		return self

	def confirm(self):
		"""
		Confirms the application and receives the token
		"""
		url = "https://oauth.vk.com/authorize/"
		values = {"display": "mobile", "scope": SCOPE,
			"client_id": APP_ID, "response_type": "token",
			"redirect_uri": "https://oauth.vk.com/blank.html"}

		token = None
		body, response = self.get(url, values)
		if response:
			if "access_token" in response.url:
				match = token_exp.search(response.url)
				if match:
					token = match.group(0)
				else:
					logger.error("token regexp doesn't match the url: %s", response.url)
					raise AuthError("Something went wrong. We're so sorry.")
			else:
				postTarget = webtools.getTagArg("form method=\"post\"", "action",
					body, "form")
				if postTarget:
					body, response = self.post(postTarget)
					token = token_exp.search(response.url).group(0)
				else:
					raise AuthError("Couldn't confirm the application!")
		return token


class APIBinding(RequestProcessor):
	"""
	Provides simple VK API binding
	Translates VK errors to python exceptions
	"""
	def __init__(self, token, debug=None, logline=""):
		self.token = token
		self.debug = debug
		self.last = []
		self.captcha = {}
		self.lastMethod = ()
		self.delay = 1.00
		# to use it in logs without showing the token
		self.logline = logline
		RequestProcessor.__init__(self)


	def __delay(self):
		"""
		Delaying method execution to prevent "too fast" errors from happening
		Typically VK allows us execution of 3 methods per second.
		"""
		self.last.append(time.time())
		if len(self.last) > 2:
			if (self.last.pop() - self.last.pop(0)) <= self.delay:
				time.sleep(self.delay / METHOD_THROUGHPUT)
				self.last = [time.time()]

	def method(self, method, values=None, notoken=False):
		"""
		Issues a VK method
		Args:
			method: vk method
			values: method parameters
			notoken: whether to cut the token out of the request
		Returns:
			The method execution result
		"""
		self.__delay()
		url = "https://api.vk.com/method/%s" % method
		values = values or {}
		if not notoken:
			values["access_token"] = self.token
		values["v"] = API_VERSION

		if "key" in self.captcha:
			values["captcha_sid"] = self.captcha["sid"]
			values["captcha_key"] = self.captcha["key"]
			self.captcha = {}

		self.lastMethod = (method, values)

		start = time.time()
		if self.debug == "all" or method in self.debug:
			Print("SENT: method %s with values %s in thread: %s" % (method,
				colorizeJSON(values), threading.currentThread().name))

		response = self.post(url, values)
		if response:
			body, response = response
			if body:
				try:
					body = json.loads(body)
				except ValueError:
					return {}

			if self.debug:
				end = time.time()
				dbg = (method, colorizeJSON(body), threading.currentThread().name, (end - start), self.logline)
				if method in self.debug or self.debug == "all":
					Print("GOT: for method %s: %s in thread: %s (%0.2fs) for %s" % dbg)

				if self.debug == "slow":
					if (end - start) > 3:
						Print("GOT: (slow) response for method %s: %s in thread: %s (%0.2fs) for %s" % dbg)

			if "response" in body:
				return body["response"] or {}

			# according to vk.com/dev/errors
			elif "error" in body:
				error = body["error"]
				eCode = error["error_code"]
				eMsg = error.get("error_msg", "")
				logger.error("vkapi: error occured on executing method"
					" (%s(%s), code: %s, msg: %s), (for: %s)" % (method, values, eCode, eMsg, self.logline))

				if eCode == 7:  # not allowed
					raise NotAllowed(eMsg)

				elif eCode == 10:  # internal server error
					raise InternalServerError(eMsg)

				elif eCode == 13:  # runtime error
					raise RuntimeError(eMsg)

				elif eCode == 14:  # captcha
					if "captcha_sid" in error:
						self.captcha = {"sid": error["captcha_sid"], "img": error["captcha_img"]}
						raise CaptchaNeeded()

				elif eCode == 15:
					raise AccessDenied(eMsg)

				elif eCode == 17:
					raise ValidationRequired(eMsg)

				# 1 - unknown error / 100 - wrong method or parameters loss
				# todo: where we going we NEED constants
				elif eCode in (1, 6, 9, 100):
					if eCode in (6, 9):   # 6 - too fast / 9 - flood control
						self.delay += 0.15
						# logger doesn't seem to support %0.2f
						logger.warning("vkapi: got code %s, increasing timeout to %0.2f (for: %s)" %
							(eCode, self.delay, self.logline))
						# rying to execute te method again (it will sleep a while in __delay())
						return self.method(method, values)
					return {"error": eCode}
				raise VkApiError(eMsg)

	def retry(self):
		"""
		Tries to execute last method again
		Usually called after captcha is entered
		"""
		result = None
		if self.lastMethod:
			try:
				result = self.method(*self.lastMethod)
			except CaptchaNeeded:
				raise
			except Exception:
				pass
		return result


class NetworkNotFound(Exception):
	"""
	This happens in very weird situations
	Happened just once at 10.01.2014 (vk.com was down)
	"""
	pass


class NetworkError(Exception):
	"""
	Common network error
	"""
	pass


class LongPollError(Exception):
	"""
	Should be raised when longpoll exception occurred
	"""
	pass


class VkApiError(Exception):
	"""
	Base VK API Error
	"""
	pass


class CaptchaNeeded(Exception):
	"""
	Will be raised when captcha appears
	"""
	pass


class AuthError(VkApiError):
	"""
	Happens when user is trying to login using password
	"""
	pass


class InternalServerError(VkApiError):
	"""
	Well, that error should be probably ignored
	"""
	pass


class TokenError(VkApiError):
	"""
	Will be raised if Token Error occurred
	"""
	pass


class NotAllowed(VkApiError):
	"""
	Will be raised when happens error with code 7
	Happens usually when someone's added our user in the black-list
	"""
	pass


class AccessDenied(VkApiError):
	"""
	This one should be ignored as well.
	Happens for an unknown reason with any method
	"""
	pass


class ValidationRequired(VkApiError):
	"""
	New in API v4
	Happens if VK thinks we're
	logging in from an unusual location
	"""
	pass
