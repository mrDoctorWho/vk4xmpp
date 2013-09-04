# /* coding: utf-8 */
# based on VKApi module by Kirill Python
# Modifications © simpleApps.

import re, time
import requests, webtools

class VkApi:
	def __init__(self, number, password = None, 
				 sid = None, token= None, app_id = 3789129, 
				 scope = 69634, proxies = None):
		self.password = password
		self.number = number

		self.sid = sid
		self.token = token
		self.captcha = {}
		self.settings = {}
		self.lastMethod = None

		self.app_id = app_id
		self.scope = scope

		self.http = requests.Session()
		self.http.proxies = proxies
		self.http.headers = {"User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20130309 Firefox/21.0",
							 "Accept-Language":"ru-RU, utf-8"}
		self.http.verify = False


	def vk_login(self, cSid=None, cKey = None):
		url = "https://login.vk.com/"
		values = {"act": "login",
				  "utf8": "1",
				  "email": self.number,
				  "pass": self.password}

		if cSid and cKey:
			values["captcha_sid"] = cSid
			values["captcha_key"] = cKey

		self.http.cookies.clear()
		response = self.http.post(url, values)
		if "remixsid" in self.http.cookies:
			remixsid = self.http.cookies["remixsid"]
			self.settings["remixsid"] = remixsid

			self.settings["forapilogin"] = {"p": self.http.cookies["p"],
											"l": self.http.cookies["l"] }

			self.sid = remixsid

		elif "sid=" in response.url:
			raise authError("Authorization error (captcha)")
		else:
			raise authError("Authorization error (bad password)")

		if "security_check" in response.url:
			number_hash = regexp(r"security_check.*?hash: '(.*?)'\};", response.text)[0]

			code = self.number[2:-2]			
			if len(self.number) == 12:
				if not self.number.startswith("+"):
					code = self.number[3:-2]  		# may be +375123456789 
	
			elif len(self.number) == 13:			# so we need 1234567
				if self.number.startswith("+"):
					code = self.number[4:-2] 

			values = {"act": "security_check",
					  "al": "1",
					  "al_page": "3",
					  "code": code,
					  "hash": number_hash,
					  "to": ""}
			response = self.http.post("https://vk.com/login.php", values)
			if response.text.split("<!>")[4] == "4":
				return

			raise authError("Incorrect number")

	def check_sid(self):
		"""Valiating cookies remixsid"""
		if self.sid:
			url = "https://vk.com/feed2.php"
			self.http.cookies.update({
				"remixsid": self.sid,
				"remixlang": "0",
				"remixsslsid": "1"
			})

			response = self.http.get(url).json()

			if response["user"]["id"] != -1:
				return response

	def api_login(self):
		url = "https://oauth.vk.com/authorize"
		values = {"display": "mobile",
				  "scope": self.scope,
				  "client_id": self.app_id,
				  "response_type": "token",
				  "redirect_uri": "https://oauth.vk.com/blank.html"}

		token = None
		GET = self.http.get(url, params = values)
		getUrl = GET.url
		if "access_token" in getUrl:
			token = getUrl.split("=")[1].split("&")[0]
		else:
			POST = webtools.getTagArg("form method=\"post\"", "action", GET.text, "form")
			if POST:
				response = self.http.post(POST)
				token = response.url.split("=")[1].split("&")[0]
			else:
				raise authError("ApiError")
		self.token = token


	def method(self, method, values={}):
		url = "https://api.vk.com/method/%s" % method
		values["access_token"] = self.token
		if self.captcha and self.captcha.has_key("key"):
			values["captcha_sid"] = self.captcha["sid"]
			values["captcha_key"] = self.captcha["key"]
		self.lastMethod = (method, values)
##		print "method %s with values %s" % (method, str(values))
		## This code can be useful when we're loaded too high
		try:
			json = self.http.post(url, values).json()
		except requests.ConnectionError:
			try:
				time.sleep(1)
				json = self.http.post(url, values).json()
			except:
				return {}
##		print "response:%s"% str(json)
		if json.has_key("response"):
			return json["response"]

		elif json.has_key("error"):
			error = json["error"]
			eCode = error["error_code"]
			if eCode == 6: # too fast
				time.sleep(3)
				return self.method(method, values)
			elif eCode == 5: # auth failed
				raise apiError("Logged out")
			if eCode == 14:
				if "captcha_sid" in error: # maybe we need check if exists self.captcha
					self.captcha = {"sid": error["captcha_sid"], "img": error["captcha_img"]}
					raise captchaNeeded
			raise apiError(json["error"])

	def retry(self):
		if self.lastMethod: 
			return self.method(*self.lastMethod)

def regexp(reg, string, findall = 1):
	u""" Поиск по регулярке """

	reg = re.compile(reg, re.IGNORECASE | re.DOTALL)
	if findall:
		reg = reg.findall(string)
	else:
		return reg.search(string)
	return reg


class vkApiError(Exception):
	pass


class authError(vkApiError):
	pass


class apiError(vkApiError):
	pass

class tokenError(vkApiError):
	pass

class captchaNeeded(vkApiError):
	pass