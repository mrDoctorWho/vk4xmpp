# coding: utf-8
# © simpleApps, 2013 — 2015.

import cookielib
import httplib
import logging
import mimetools
import socket
import ssl
import time
import re
import urllib
import urllib2
import webtools

SOCKET_TIMEOUT = 30
REQUEST_RETRIES = 6

socket.setdefaulttimeout(SOCKET_TIMEOUT)

logger = logging.getLogger("vk4xmpp")

token_exp = re.compile("(([\da-f]+){11,})", re.IGNORECASE)


## Trying to use faster library usjon instead of simplejson
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
					logger.warning("vkapi: trying to execute \"%s\" in #%d time" % (func.func_name, retries))
					time.sleep(0.2)
				else:
					break
			else:
				if hasattr(exc, "errno") and exc.errno == 101:
					raise NetworkNotFound()
				data = resultType()
				logger.warning("vkapi: Error %s occurred on executing %s" % (exc, func))
			return data

		wrapper.__name__ = func.__name__
		return wrapper

	return decorator


class AsyncHTTPRequest(httplib.HTTPConnection):
	"""
	Provides easy method to make asynchronous http requests and getting socket object from it
	"""
	def __init__(self, url, data=None, headers=(), timeout=SOCKET_TIMEOUT):
		host = urllib.splithost(urllib.splittype(url)[1])[0]
		httplib.HTTPConnection.__init__(self, host, timeout=timeout)
		self.url = url
		self.data = data
		self.headers = headers or {}

	def open(self):
		self.connect()
		self.request(("POST" if self.data else "GET"), self.url, self.data, self.headers)
		return self

	def read(self):
		with self as resp:
			return resp.read()

	def __enter__(self):
		return self.getresponse()

	def __exit__(self, *args):
		self.close()


class RequestProcessor(object):
	"""
	Processes base requests: POST (application/x-www-form-urlencoded and multipart/form-data) and GET.
	"""
	headers = {"User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0)"
					" Gecko/20130309 Firefox/21.0",
				"Accept-Language": "ru-RU, utf-8"}
	boundary = mimetools.choose_boundary()

	def __init__(self):
		self.cookieJar = cookielib.CookieJar()
		cookieProcessor = urllib2.HTTPCookieProcessor(self.cookieJar)
		self.open = urllib2.build_opener(cookieProcessor).open
		self.open.__func__.___defaults__ = (None, SOCKET_TIMEOUT)

	def getCookie(self, name):
		"""
		Gets cookie from cookieJar
		"""
		for cookie in self.cookieJar:
			if cookie.name == name:
				return cookie.value

	def multipart(self, key, name, ctype, data):
		"""
		Makes multipart/form-data encoding
		Parameters:
			key: a form key (is there a form?)
			name: file name
			ctype: Content-Type
			data: just data you want to send
		"""
		start = ["--" + self.boundary, "Content-Disposition: form-data; name=\"%s\"; filename=\"%s\"" % (key, name), \
									"Content-Type: %s" % ctype, "", ""] ## We already have content type so maybe we shouldn't detect it
		end = ["", "--" + self.boundary + "--", ""]
		start = "\n".join(start)
		end = "\n".join(end)
		data = start + data + end
		return data

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

	@attemptTo(REQUEST_RETRIES, tuple, urllib2.URLError, ssl.SSLError, httplib.BadStatusLine)
	def post(self, url, data="", urlencode=True):
		"""
		POST request
		"""
		resp = self.open(self.request(url, data, urlencode=urlencode))
		body = resp.read()
		return (body, resp)

	@attemptTo(REQUEST_RETRIES, tuple, urllib2.URLError, ssl.SSLError, httplib.BadStatusLine)
	def get(self, url, query={}):
		"""
		GET request
		"""
		if query:
			url += "?%s" % urllib.urlencode(query)
		resp = self.open(self.request(url))
		body = resp.read()
		return (body, resp)

## todo: move getOpener the hell out of here
	@attemptTo(REQUEST_RETRIES, tuple, socket.gaierror, socket.timeout, socket.error)
	def getOpener(self, url, query={}):
		"""
		Opens a connection to url and returns AsyncHTTPRequest() object
		"""
		if query:
			url += "?%s" % urllib.urlencode(query)
		return AsyncHTTPRequest(url).open()


class APIBinding:
	"""
	Provides simple VK API binding
	Translates VK errors to python exceptions
	Allows to make a password authorization
	"""
	def __init__(self, number=None, password=None, token=None, app_id=3789129,
	scope=69638, debug=[]):
		self.password = password
		self.number = number
		self.token = token
		self.app_id = app_id
		self.scope = scope

		self.sid = None
		self.captcha = {}
		self.last = []
		self.lastMethod = ()

		self.RIP = RequestProcessor()
		self.attempts = 0
		self.debug = ()

	def loginByPassword(self):
		"""
		Logging in using password
		"""
		url = "https://login.vk.com/"
		values = {"act": "login",
				"utf8": "1",
				"email": self.number,
				"pass": self.password}

		body, response = self.RIP.post(url, values)
		remixSID = self.RIP.getCookie("remixsid")

		if remixSID:
			self.sid = remixSID

		elif "sid=" in response.url:
			raise AuthError("Captcha!")
		else:
			raise AuthError("Invalid password")

		if "security_check" in response.url:
			# This code should be rewritten
			hash = re.search("security_check.*?hash: '(.*?)'\};", body).group(0)
			if not self.number[0] == "+":
				self.number = "+" + self.number

			code = self.number[2:-2]
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

	def checkSid(self):
		"""
		Checks sid to set the logged-in flag
		"""
		if self.sid:
			url = "https://vk.com/feed2.php"
			get = self.RIP.get(url)
			if get:
				body, response = get
				if body and response:
					data = json.loads(body)
					if data["user"]["id"] != -1:
						return data

	def confirmThisApp(self):
		"""
		Confirms your application and receives the token
		"""
		url = "https://oauth.vk.com/authorize/"
		values = {"display": "mobile",
				"scope": self.scope,
				"client_id": self.app_id,
				"response_type": "token",
				"redirect_uri": "https://oauth.vk.com/blank.html"}

		token = None
		body, response = self.RIP.get(url, values)
		if response:
			if "access_token" in response.url:
				token = token_exp.search(response.url).group(0)
			else:
				postTarget = webtools.getTagArg("form method=\"post\"", "action", body, "form")
				if postTarget:
					body, response = self.RIP.post(postTarget)
					token = token_exp.search(response.url).group(0)
				else:
					raise AuthError("Couldn't execute confirmThisApp()!")
		self.token = token


	def method(self, method, values=None, nodecode=False):
		"""
		Issues the VK method
		Parameters:
			method: vk method
			values: method parameters (no captcha_{sid,key}, access_token or v parameters needed)
			nodecode: decode flag
		"""
		values = values or {}
		url = "https://api.vk.com/method/%s" % method
		values["access_token"] = self.token
		values["v"] = "3.0"

		if self.captcha and self.captcha.has_key("key"):
			values["captcha_sid"] = self.captcha["sid"]
			values["captcha_key"] = self.captcha["key"]
			self.captcha = {}
		self.lastMethod = (method, values)
		self.last.append(time.time())
		if len(self.last) > 2:
			if (self.last.pop() - self.last.pop(0)) <= 1.25:
				time.sleep(0.34)

		response = self.RIP.post(url, values)
		if response and not nodecode:
			body, response = response
			if body:
				try:
					body = json.loads(body)
				except ValueError:
					return {}
#	 Debug:
			if method in self.debug:
				print "method %s with values %s" % (method, str(values))
				print "response for method %s: %s" % (method, str(body))

			if "response" in body:
				return body["response"] or {}

			elif "error" in body:
				error = body["error"]
				eCode = error["error_code"]
				eMsg = error.get("error_msg", "")
				logger.error("vkapi: error occured on executing method (%(method)s, code: %(eCode)s, msg: %(eMsg)s)" % vars())

				if eCode == 5:     # auth failed / invalid session(?)
					raise VkApiError(eMsg)
				elif eCode == 6:     # too fast
					time.sleep(1.25)
					return self.method(method, values)
				elif eCode == 7:     # not allowed
					raise NotAllowed(eMsg)
				elif eCode == 10:    # internal server error
					raise InternalServerError(eMsg)
				elif eCode == 13:    # runtime error
					raise RuntimeError(eMsg)
				elif eCode == 14:     # captcha
					if "captcha_sid" in error:
						self.captcha = {"sid": error["captcha_sid"], "img": error["captcha_img"]}
						raise CaptchaNeeded()
				elif eCode == 15:
					raise AccessDenied()
				elif eCode in (1, 9, 100): ## 1 is an unknown error / 9 is flood control / 100 is wrong method or parameters loss 
					return {"error": eCode}
				raise VkApiError(body["error"])

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
	And there's one of possible errors: captcha, invalid password and wrong phone
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
	Will be raised when happens error with code 5 and 3 retries to make request are failed
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
	Happens for an unknown reason with any GET-like method
	"""
	pass