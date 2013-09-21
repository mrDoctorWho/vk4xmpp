# /* coding: utf-8 */
# © simpleApps CodingTeam, 2013.

import re, time
import ssl, urllib, urllib2, cookielib, webtools, json
import traceback

class RequestProcessor(object):

	headers = { "User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0)"\
									" Gecko/20130309 Firefox/21.0",
		   	   	"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
				"Accept-Language": "ru-RU, utf-8"
			  }
	def __init__(self):
		self.cookieJar = cookielib.CookieJar()
		self.cookieProcessor = urllib2.HTTPCookieProcessor(self.cookieJar)
		self.Opener = urllib2.build_opener(self.cookieProcessor)

	def getCookie(self, name):
		for cookie in self.cookieJar:
			if cookie.name == name:
				return cookie.value

	def request(self, url, data = None, headers = {}):
		if not headers:
			headers = self.headers
		if data:
			data = urllib.urlencode(data)
		request = urllib2.Request(url, data, headers)
		return request

	def open(self, request, timeout = 3, retryCount = 0):
		try:
			if retryCount > 4:
				raise RuntimeError
			response = self.Opener.open(request, timeout = timeout)
		except (urllib2.URLError, ssl.SSLError):
			traceback.print_exc()
			retryCount += 1
			response = self.open(request, timeout, retryCount)
		except RuntimeError:
			return {}
		return response

	def post(self, url, data = {}):
		request = self.request(url, data)
		response = self.open(request)
		body = response.read()
		return (body, response)

	def get(self, url, data = {}):
		if data:
			url = url + "/?%s" % urllib.urlencode(data)
		request = self.request(url)
		response = self.open(request)
		body = response.read()
		return (body, response)


class APIBinding:
	def __init__(self, number, password = None, token = None, app_id = 3789129, 
				 scope = 69634):
		self.password = password
		self.number = number

		self.sid = None
		self.token = token
		self.captcha = {}
		self.last = []
		self.lastMethod = None

		self.app_id = app_id
		self.scope = scope

		self.RIP = RequestProcessor()

	def loginByPassword(self):
		url = "https://login.vk.com/"
		values = { "act": "login",
				   "utf8": "1", # check if it needed
				   "email": self.number,
				   "pass": self.password 
				  }

		post = self.RIP.post(url, values)
		body, response = post
		RemixSID = self.RIP.getCookie("remixsid")

		if RemixSID:
			self.sid = RemixSID

		elif "sid=" in response.url:
			raise AuthError("Captcha!")
		else:
			raise AuthError("Invalid password")

		if "security_check" in response.url:
			Hash = webtools.regexp(r"security_check.*?hash: '(.*?)'\};", body)[0]
			code = self.number[2:-2]			
			if len(self.number) == 12:
				if not self.number.startswith("+"):
					code = self.number[3:-2]  		# may be +375123456789 
	
			elif len(self.number) == 13:			# so we need 1234567
				if self.number.startswith("+"):
					code = self.number[4:-2]

			values = { "act": "security_check",
					   "al": "1",
					   "al_page": "3",
					   "code": code,
					   "hash": Hash,
					   "to": ""
					  }
			post = self.RIP.post("https://vk.com/login.php", values)
			body, response = post
			if not body.split("<!>")[4] == "4":
				raise AuthError("Incorrect number")

	def checkSid(self):
		if self.sid:
			url = "https://vk.com/feed2.php"
			get = self.RIP.get(url)
			body, response = get
			if body:
				data = json.loads(body)
				if data["user"]["id"] != -1:
					return data

	def confirmThisApp(self):
		url = "https://oauth.vk.com/authorize"
		values = { "display": "mobile",
				   "scope": self.scope,
				   "client_id": self.app_id,
				   "response_type": "token",
				   "redirect_uri": "https://oauth.vk.com/blank.html"
				  }

		token = None
		get = self.RIP.get(url, values)
		body, response = get
		if "access_token" in response.url:
			token = response.url.split("=")[1].split("&")[0]
		else:
			PostTarget = webtools.getTagArg("form method=\"post\"", "action", body, "form")
			if PostTarget:
				post = self.RIP.post(PostTarget) # why no data?
				body, response = post
				token = response.url.split("=")[1].split("&")[0]
			else:
				raise AuthError("Couldn't execute confirmThisApp()!")
		self.token = token


	def method(self, method, values={}):
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
			if (self.last.pop() - self.last.pop(0)) < 1.1:
				time.sleep(0.3) # warn: it was 0.4

		post = self.RIP.post(url, values)

		body, response = post
		body = json.loads(body)
# Debug:
#		if method == "messages.get":
#			print "method %s with values %s" % (method, str(values))
#			print "response for method %s: %s" % (method, str(body))
		if body.has_key("response"):
			return body["response"]

		elif body.has_key("error"):
			error = body["error"]
			eCode = error["error_code"]
## TODO: Check this code
			if eCode == 5: # invalid token
#				print error
				raise TokenError(error["error_msg"])
			if eCode == 6: # too fast
				time.sleep(3)
				return self.method(method, values)
			elif eCode == 5: # auth failed
				raise VkApiError("Logged out")
			elif eCode == 9:
				return {}
			if eCode == 14: # captcha
				if error.has_key("captcha_sid"):
					self.captcha = {"sid": error["captcha_sid"], "img": error["captcha_img"]}
					raise CaptchaNeeded
			raise VkApiError(body["error"])

	def retry(self):
		if self.lastMethod: 
			return self.method(*self.lastMethod)

class VkApiError(Exception):
	pass

class AuthError(VkApiError):
	pass

class CaptchaNeeded(VkApiError):
	pass

class TokenError(VkApiError):
	pass
