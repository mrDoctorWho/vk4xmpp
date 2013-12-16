# /* coding: utf-8 */
# © simpleApps CodingTeam, 2013.
# Warning: Code in this module is ugly,
# but we can't do better.

import time
import ssl
import urllib
import urllib2
import cookielib
import webtools


# TODO: user ujson for speed?
try:
    import simplejson as json
except ImportError:
    import json


def try_execute(f, max_retries=5):
    """
    Executes function several times, omitting errors until
    reaching max retries
    """

    assert max_retries > 1

    def wrapper(*args, **kwargs):
        retries = 0
        while retries > max_retries:
            try:
                return f(*args, **kwargs)
            except (urllib2.URLError, ssl.SSLError):
                retries += 1
        return {}

    return wrapper


class RequestProcessor(object):
    headers = {"User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0)"
                             " Gecko/20130309 Firefox/21.0",
               "Content-Type": "application/x-www-form-urlencoded;"
                               " charset=UTF-8",
               "Accept-Language": "ru-RU, utf-8"}

    def __init__(self):
        self.cookie_jar = cookielib.CookieJar()
        self.cookie_processor = urllib2.HTTPCookieProcessor(self.cookie_jar)
        self.opener = urllib2.build_opener(self.cookie_processor)

    def get_cookie(self, name):
        for cookie in self.cookie_jar:
            if cookie.name == name:
                return cookie.value

    def request(self, url, data=None, headers=None):
        if not headers:
            headers = self.headers
        if data:
            data = urllib.urlencode(data)
        request = urllib2.Request(url, data, headers)
        return request

    def open(self, request, timeout=3):
        response = try_execute(self.opener.open)(request, None, timeout)
        return response

    def safe_execute_deprecated(self, func, args=None, retry_count=0):
        try:
            if retry_count > 5:    # We're hope that it will be never called
                raise RuntimeError
            result = func(*args)
        except (urllib2.URLError, ssl.SSLError):
            retry_count += 1
            result = self.safe_execute_deprecated(func, args, retry_count)
        except RuntimeError:    # Very sad
            result = {}
        return result

    @staticmethod
    def try_execute(f, *args, **kwargs):
        """
        Executes function several times, omitting errors until
        reaching max retries
        """
        retries = 0
        max_retries = 5
        while retries > max_retries:
            try:
                return f(*args, **kwargs)
            except (urllib2.URLError, ssl.SSLError):
                retries += 1
            except RuntimeError:
                return {}

    def post(self, url, data=None, retry_count=0):
        body = {}
        request = self.request(url, data)
        response = try_execute(self.open)(request)
        try:
            if response:
                body = response.read()        # we can't use safeExecution
                                              # because .read() method can
                                              # be used once
            if retry_count > 2:
                raise RuntimeError
        except (urllib2.URLError, ssl.SSLError):
            retry_count += 1
            return self.post(url, data, retry_count)
        except RuntimeError:
            body = {}
        return body, response

    def get(self, url, data=None):
        if data:
            url += "/?%s" % urllib.urlencode(data)
        request = self.request(url)
        response = try_execute(self.open)(request)     # Why again?
        body = response.read()
        return body, response


class APIBinding:
    def __init__(self, number, password=None, token=None, app_id=3789129,
                 scope=69634):
        self.password = password
        self.number = number

        self.sid = None
        self.token = token
        self.captcha = {}
        self.last = []
        self.last_method = None

        self.app_id = app_id
        self.scope = scope

        self.rip = RequestProcessor()
        self.attempts = 0

    def login_by_password(self):
        url = "https://login.vk.com/"
        values = {"act": "login",
                  "utf8": "1",  # check if it needed
                  "email": self.number,
                  "pass": self.password}

        post = self.rip.post(url, values)
        body, response = post
        remix_sid = self.rip.get_cookie("remixsid")

        if remix_sid:
            self.sid = remix_sid

        elif "sid=" in response.url:
            raise AuthError("Captcha!")
        else:
            raise AuthError("Invalid password")

        if "security_check" in response.url:
            security_regexp = r"security_check.*?hash: '(.*?)'\};"
            security_hash = webtools.regexp(security_regexp, body)[0]
            code = self.number[2:-2]
            if len(self.number) == 12:
                if not self.number.startswith("+"):
                    code = self.number[3:-2]        # may be +375123456789

            elif len(self.number) == 13:            # so we need 1234567
                if self.number.startswith("+"):
                    code = self.number[4:-2]

            values = {"act": "security_check",
                      "al": "1",
                      "al_page": "3",
                      "code": code,
                      "hash": security_hash,
                      "to": ""}

            post = self.rip.post("https://vk.com/login.php", values)
            body, response = post
            if response and not body.split("<!>")[4] == "4":
                raise AuthError("Incorrect number")

    def check_sid(self):
        if self.sid:
            url = "https://vk.com/feed2.php"
            get = self.rip.get(url)
            body, response = get
            if body and response:
                data = json.loads(body)
                if data["user"]["id"] != -1:
                    return data

    def confirm_app(self):
        url = "https://oauth.vk.com/authorize"
        values = {"display": "mobile",
                  "scope": self.scope,
                  "client_id": self.app_id,
                  "response_type": "token",
                  "redirect_uri": "https://oauth.vk.com/blank.html"}

        token = None
        get = self.rip.get(url, values)
        body, response = get
        if response:
            if "access_token" in response.url:
                token = response.url.split("=")[1].split("&")[0]
            else:
                post_target = webtools.getTagArg("form method=\"post\"",
                                                 "action", body, "form")
                if post_target:
                    post = self.rip.post(post_target)   # why no data?
                    body, response = post
                    token = response.url.split("=")[1].split("&")[0]
                else:
                    raise AuthError("Couldn't execute confirmThisApp()!")
        self.token = token

    def method(self, method, values=None):
        if not values:
            values = {}
        url = "https://api.vk.com/method/%s" % method
        values["access_token"] = self.token
        values["v"] = "3.0"

        if self.captcha and 'key' in self.captcha:
            values["captcha_sid"] = self.captcha["sid"]
            values["captcha_key"] = self.captcha["key"]
            self.captcha = {}
        self.last_method = (method, values)
        self.last.append(time.time())
        if len(self.last) > 2:
            if (self.last.pop() - self.last.pop(0)) < 1.1:
                time.sleep(0.3)     # warn: it was 0.4 // does it matter?

        post = self.rip.post(url, values)

        body, response = post
        if body:
            body = json.loads(body)
            # Debug:
        ##		if method == "users.get":##("messages.get", "messages.send"):
        ##			print "method %s with values %s" % (method, str(values))
        ##			print "response for method %s: %s" % (method, str(body))
        if "response" in body:
            return body["response"]

        elif "error" in body:
            error = body["error"]
            error_code = error["error_code"]

            # TODO: Check this code
            # TODO: refactor to exception-base handling

            if error_code == 5:     # invalid token
                self.attempts += 1
                if self.attempts < 3:
                    retry = self.retry()
                    if retry:
                        self.attempts = 0
                        return retry
                else:
                    raise TokenError(error["error_msg"])
            if error_code == 6:     # too fast
                time.sleep(3)
                return self.method(method, values)
            elif error_code == 5:   # auth failed
                raise VkApiError("Logged out")
            if error_code == 7:
                raise NotAllowed
            elif error_code == 9:
                return {}
            if error_code == 14:    # captcha
                if "captcha_sid" in error:
                    self.captcha = {"sid": error["captcha_sid"],
                                    "img": error["captcha_img"]}
                    raise CaptchaNeeded
            raise VkApiError(body["error"])

    def retry(self):
        if self.last_method:
            return self.method(*self.last_method)


class VkApiError(Exception):
    pass


class AuthError(VkApiError):
    pass


class CaptchaNeeded(VkApiError):
    pass


class TokenError(VkApiError):
    pass


class NotAllowed(VkApiError):
    pass
