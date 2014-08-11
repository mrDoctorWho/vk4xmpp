# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from __main__ import *
from __main__ import _
import random
import urllib

def sendPhoto(user, data, type, address, mType):
	mask = user.vk.method("account.getAppPermissions")

	if mType == "chat_id":
		address = address.split("@")[0].split("#")[1]
		send = False
	else:
		destination = address
		address = vk2xmpp(address)
		send = True

	if address == TransportID:
		answer = _("Are you kidding me?")
	elif mask:
		if mask & 4 == 4: ## we have enough access?
			ext = type.split("/")[1]
			name = "vk4xmpp_%s.%s" % (random.randint(1000, 9000), ext)
			server = str(user.vk.method("photos.getMessagesUploadServer")["upload_url"])
			response = json.loads(user.vk.engine.RIP.post(
					server, 
					user.vk.engine.RIP.multipart("photo", str(name), str(type), data),
					urlencode = False)[0])
			
			id = user.vk.method("photos.saveMessagesPhoto", response)[0].get("id", 0)
			user.msg("", address, mType, {"attachment": id})
			logger.debug("sendPhoto: image was successfully sent by user %s" % user.source)
			answer = _("Your image was successfully sent.")
		else:
			answer = _("Sorry but we have failed to send this image."
				 	" Seems you haven't enough permissions. Your token should be updated, register again.")
	else:
		answer = _("Something went wrong. We are so sorry.")
	if send:
		msgSend(Component, user.source, answer, destination, timestamp=1)


def parseXHTML(user, html, source, destination, mType="user_id"):
	body = html.getTag("body")
	if body:
		## TODO: Maybe would be better if we use regular expressions?
		src = body.getTagAttr("img", "src")
		raw_data = src.split("data:")[1]
		mime_type = raw_data.split(";")[0]
		data = raw_data.split("base64,")[1]
		if data:
			try:
				data = urllib.unquote(data).decode("base64")
			except Exception:
				logger.error("xhmtlParse: fetched wrong xhtml image (jid: %s)" % source)
				return False
			runThread(sendPhoto, (user, data, mime_type, destination, mType))
	return True 
