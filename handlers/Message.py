# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

import urllib
import random

def msgRecieved(msg, jidFrom, jidTo):
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom)
		tag = answer.setTag("received", namespace = "urn:xmpp:receipts")
		tag.setAttr("id", msg.getID())
		answer.setFrom(jidTo)
		answer.setID(msg.getID())
		return answer


def sendPhoto(user, data, type, address):
	mask = user.vk.method("account.getAppPermissions")
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
			
			photo = user.vk.method("photos.saveMessagesPhoto", response)[0]
			id = photo["id"]
			user.msg("", vk2xmpp(address), more = {"attachment": id})
			logger.debug("sendPhoto: image was successfully sent by user %s" % user.source)
			answer = _("Your image was successfully sent.")
		else:
			answer = _("Sorry but we have failed to send this image."
				 	" Seems you haven't enough permissions. Your token should be updated, register again.")
	else:
		answer = _("Something went wrong. We are so sorry.")
	msgSend(Component, user.source, answer, address, timestamp = 1)


def msgHandler(cl, msg):
	mType = msg.getType()
	body = msg.getBody()
	jidTo = msg.getTo()
	jidToStr = jidTo.getStripped()
	jidFrom = msg.getFrom()
	jidFromStr = jidFrom.getStripped()
	html = msg.getTag("html")

	if jidFromStr in Transport and mType == "chat":
		user = Transport[jidFromStr]
		if msg.getTag("composing"):
			target = vk2xmpp(jidToStr)
			if target != TransportID:
				user.vk.method("messages.setActivity", {"user_id": target, "type": "typing"}, True)

		if html and html.getTag("body"): ## XHTML-IM!
			logger.debug("msgHandler: fetched xhtml image from %s" % jidFromStr)

			raw_data = html.getTag("body").getTagAttr("img", "src")
			raw_data = raw_data.split("data:")[1]
			mime_type = raw_data.split(";")[0]
			data = raw_data.split("base64,")[1]
			if data:
				try:
					data = urllib.unquote(data).decode("base64")
				except Exception:
					logger.error("msgHandler: fetched wrong xhtml image from %s" % jidFromStr)
					raise xmpp.NodeProcessed()
				threadRun(sendPhoto, (user, data, mime_type, jidToStr))
			raise xmpp.NodeProcessed() ## I think we shouldn't handle body then.

		if body:
			answer = None
			if jidTo == TransportID:
				raw = body.split(None, 1)
				if len(raw) > 1:
					text, args = raw
					args = args.strip()
					if text == "!captcha" and args:
						captchaAccept(cl, args, jidTo, jidFromStr)
						answer = msgRecieved(msg, jidFrom, jidTo)
					elif text == "!eval" and args and jidFromStr == evalJID:
						try:
							result = unicode(eval(args))
						except Exception:
							result = returnExc()
						msgSend(cl, jidFromStr, result, jidTo)
					elif text == "!exec" and args and jidFromStr == evalJID:
						try:
							exec(unicode(args + "\n"), globals())
						except Exception:
							result = returnExc()
						else:
							result = "Done."
						msgSend(cl, jidFromStr, result, jidTo)
			else:
				uID = jidTo.getNode()
				vkMessage = user.msg(body, uID)
				if vkMessage:
					answer = msgRecieved(msg, jidFrom, jidTo)
			if answer:
				Sender(cl, answer)
	for func in Handlers["msg02"]:
		func(msg)
		

def captchaAccept(cl, args, jidTo, jidFromStr):
	if args:
		answer = None
		user = Transport[jidFromStr]
		if user.vk.engine.captcha:
			logger.debug("user %s called captcha challenge" % jidFromStr)
			user.vk.engine.captcha["key"] = args
			retry = False
			try:
				logger.debug("retrying for user %s" % jidFromStr)
				retry = user.vk.engine.retry()
			except api.CaptchaNeeded:
				logger.error("retry for user %s failed!" % jidFromStr)
				user.vk.captchaChallenge()
			if retry:
				logger.debug("retry for user %s OK" % jidFromStr)
				answer = _("Captcha valid.")
				Poll.add(user)
				Presence = xmpp.protocol.Presence(jidFromStr, frm = TransportID)
				#Presence.setStatus("") # is it needed?
				Presence.setShow("available")
				Sender(Component, Presence)
				user.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, jidFromStr, answer, jidTo)
