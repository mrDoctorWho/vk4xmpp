# coding: utf-8
# © simpleApps, 2013 — 2015.

"""
Manages VK API requests
Provides password login and direct VK API calls
Designed for huge number of clients (per ip)
Which is why it has request retries
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

SOCKET_TIMEOUT = 30
REQUEST_RETRIES = 6

# VK APP ID
APP_ID = 3789129
# VK APP scope
SCOPE = 69638

socket.setdefaulttimeout(SOCKET_TIMEOUT)

logger = logging.getLogger("vk4xmpp")

token_exp = re.compile("(([\da-f]+){11,})", re.IGNORECASE)

ERRORS = (httplib.BadStatusLine,
	urllib2.URLError,
	socket.gaierror,
	socket.timeout,
	socket.error,
	ssl.SSLError)

# Trying to use faster library usjon instead of simplejson
try:
	import ujson as json
	logger.debug("vkapi: using ujson instead of simplejson")
except ImportError:
	import json
	logger.error("vkapi: ujson couldn't be loaded, using simplejson instead")


def attemptTo(maxRetries, resultType, *errors):
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
				if hasattr(exc, "errno") and exc.errno == 101:
					raise NetworkNotFound()
				data = resultType()
				logger.warning("vkapi: Error %s occurred on executing %s", exc, func)
			return data

		wrapper.__name__ = func.__name__
		return wrapper

	return decorator


class AsyncHTTPRequest(httplib.HTTPConnection):
	"""
	A method to make asynchronous http request
	Provides a way to get a socket object to use in select()
	"""

	def __init__(self, url, data=None, headers=(), timeout=SOCKET_TIMEOUT):
		host = urllib.splithost(urllib.splittype(url)[1])[0]
		httplib.HTTPConnection.__init__(self, host, timeout=timeout)
		self.url = url
		self.data = data
		self.headers = headers or {}

	@attemptTo(REQUEST_RETRIES, None, *ERRORS)
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

	@classmethod
	def getOpener(cls, url, query={}):
		"""
		Opens a connection to url and returns AsyncHTTPRequest() object
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

	@attemptTo(REQUEST_RETRIES, tuple, *ERRORS)
	def post(self, url, data="", urlencode=True):
		"""
		POST request
		"""
		resp = self.open(self.request(url, data, urlencode=urlencode))
		body = resp.read()
		return (body, resp)

	@attemptTo(REQUEST_RETRIES, tuple, *ERRORS)
	def get(self, url, query={}):
		"""
		GET request
		"""
		if query:
			url += "?%s" % urllib.urlencode(query)
		resp = self.open(self.request(url))
		body = resp.read()
		return (body, resp)


class PasswordLogin(object):
	"""
	Provides a way to log-in by a password
	"""
	def __init__(self, number, password):
		self.number = number
		self.password = password
		self.RIP = RequestProcessor(cook=True)

	def login(self):
		"""
		Logging in using password
		"""
		url = "https://login.vk.com/"
		values = {"act": "login",
		"utf8": "1",
		"email": self.number,
		"pass": self.password}

		body, response = self.RIP.post(url, values)

		if "sid=" in response.url:
			logger.error("vkapi: PasswordLogin ran into captcha! (number: %s)",
				self.number)
			raise AuthError("Captcha!")

		if not self.RIP.getCookie("remixsid"):
			raise AuthError("Invalid password")

		if "security_check" in response.url:
			logger.warning("vkapi: PasswordLogin ran into a security check (number: %s)",
				self.number)
			hash = re.search("security_check.*?hash: '(.*?)'\};", body).group(0)
			if not self.number[0] == "+":
				self.number = "+" + self.number

			code = self.number[2:-2]  # valid for Russia only. Unfrotunately.
			values = {"act": "security_check",
			"al": "1",
			"al_page": "3",
			"code": code,
			"hash": hash,
			"to": ""}
			post = self.RIP.post("https://vk.com/login.php", values)
			body, response = post
			if response and not body.split("<!>")[4] == "4":
				raise AuthError("Incorrect number")
		return self.confirm()

	def confirm(self):
		"""
		Confirms the application and receives the token
		"""
		url = "https://oauth.vk.com/authorize/"
		values = {"display": "mobile",
		"scope": SCOPE,
		"client_id": APP_ID,
		"response_type": "token",
		"redirect_uri": "https://oauth.vk.com/blank.html"}

		token = None
		body, response = self.RIP.get(url, values)
		if response:
			if "access_token" in response.url:
				token = token_exp.search(response.url).group(0)
			else:
				# What is it?
				postTarget = webtools.getTagArg("form method=\"post\"", "action",
					body, "form")
				if postTarget:
					body, response = self.RIP.post(postTarget)
					token = token_exp.search(response.url).group(0)
				else:
					raise AuthError("Couldn't confirm the application!")
		return token


class APIBinding(object):
	"""
	Provides simple VK API binding
	Translates VK errors to python exceptions
	Allows to make a password authorization
	"""
	def __init__(self, token, debug=[]):
		self.token = token
		self.debug = debug

		self.captcha = {}
		self.last = []
		self.lastMethod = ()

		self.timeout = 1.00

		self.RIP = RequestProcessor()

	def method(self, method, values=None, nodecode=False):
		"""
		Issues the VK method
		Parameters:
			method: vk method
			values: method parameters
		"""
		url = "https://api.vk.com/method/%s" % method
		values = values or {}
		values["access_token"] = self.token
		values["v"] = "3.0"

		if "key" in self.captcha:
			values["captcha_sid"] = self.captcha["sid"]
			values["captcha_key"] = self.captcha["key"]
			self.captcha = {}

		self.lastMethod = (method, values)
		self.last.append(time.time())
		if len(self.last) > 2:
			if (self.last.pop() - self.last.pop(0)) <= self.timeout:
				time.sleep(self.timeout / 3.0)

		if method in self.debug or self.debug == "all":
			start = time.time()
			print "issuing method %s with values %s in thread: %s" % (method,
				str(values), threading.currentThread().name)

		response = self.RIP.post(url, values)
		if response:
			body, response = response
			if body:
				try:
					body = json.loads(body)
				except ValueError:
					return {}

			if method in self.debug or self.debug == "all":
				print "response for method %s: %s in thread: %s (%0.2fs)" % (method,
					str(body), threading.currentThread().name, (time.time() - start))

			if "response" in body:
				return body["response"] or {}

			# according to vk.com/dev/errors
			elif "error" in body:
				error = body["error"]
				eCode = error["error_code"]
				eMsg = error.get("error_msg", "")
				logger.error("vkapi: error occured on executing method"
					" (%(method)s, code: %(eCode)s, msg: %(eMsg)s)" % vars())

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
				# 1 - unknown error / 100 - wrong method or parameters loss
				elif eCode in (1, 6, 9, 100):
					if eCode in (6, 9):   # 6 - too fast / 9 - flood control
						self.timeout += 0.05
						logger.warning("vkapi: got code 9, increasing timeout to %0.2f",
							self.timeout)
						time.sleep(self.timeout)
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
	This happens in a very weird situations
	Happened just once at 10.01.2014 (vk.com was down)
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


class AuthError(VkApiError):
	"""
	Happens when user is trying to login using password
	And there's one of possible errors: captcha,
		invalid password and wrong phone
	"""
	pass


class InternalServerError(VkApiError):
	"""
	Well, that error should be probably ignored
	"""
	pass


class CaptchaNeeded(VkApiError):
	"""
	Will be raised when happens error with code 14
	To prevent captchas, you should probably send less of queries
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
