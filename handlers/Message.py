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

def xhtmlParse(user, html, source, destination):
	body = html.getTag("body")
	if body:
		## TODO: Maybe would be better if use regular expressions?
		src = body.getTagAttr("img", "src")
		raw_data = src.split("data:")[1]
		mime_type = raw_data.split(";")[0]
		data = raw_data.split("base64,")[1]
		if data:
			try:
				data = urllib.unquote(data).decode("base64")
			except Exception:
				logger.error("msgHandler: fetched wrong xhtml image from %s" % source)
				return False
			threadRun(sendPhoto, (user, data, mime_type, destination))
	return True

def msgHandler(cl, msg):
	mType = msg.getType()
	body = msg.getBody()
	jidTo = msg.getTo()
	destination = jidTo.getStripped()
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	html = msg.getTag("html")

	if source in Transport and mType == "chat":
		user = Transport[source]
		if msg.getTag("composing"):
			target = vk2xmpp(destination)
			if target != TransportID:
				user.vk.method("messages.setActivity", {"user_id": target, "type": "typing"}, True)

		if html and html.getTag("body"): ## XHTML-IM!
			logger.debug("msgHandler: fetched xhtml image from %s" % source)
			try:
				xhtml = xhtmlParse(user, html, source, destination)
			except Exception:
				xhtml = False
			if xhtml:
				raise xmpp.NodeProcessed()

		if body:
			answer = None
			if jidTo == TransportID:
				raw = body.split(None, 1)
				if len(raw) > 1:
					text, args = raw
					args = args.strip()
					if text == "!captcha" and args:
						captchaAccept(cl, args, jidTo, source)
						answer = msgRecieved(msg, jidFrom, jidTo)
					elif text == "!eval" and args and source == evalJID:
						try:
							result = unicode(eval(args))
						except Exception:
							result = returnExc()
						msgSend(cl, source, result, jidTo)
					elif text == "!exec" and args and source == evalJID:
						try:
							exec(unicode(args + "\n"), globals())
						except Exception:
							result = returnExc()
						else:
							result = "Done."
						msgSend(cl, source, result, jidTo)
			else:
				uID = jidTo.getNode()
				vkMessage = user.msg(body, uID)
				if vkMessage:
					answer = msgRecieved(msg, jidFrom, jidTo)
			if answer:
				Sender(cl, answer)
	for func in Handlers["msg02"]:
		func(msg)
		

def captchaAccept(cl, args, jidTo, source):
	if args:
		answer = None
		user = Transport[source]
		if user.vk.engine.captcha:
			logger.debug("user %s called captcha challenge" % source)
			user.vk.engine.captcha["key"] = args
			retry = False
			try:
				logger.debug("retrying for user %s" % source)
				retry = user.vk.engine.retry()
			except api.CaptchaNeeded:
				logger.error("retry for user %s failed!" % source)
				user.vk.captchaChallenge()
			if retry:
				logger.debug("retry for user %s OK" % source)
				answer = _("Captcha valid.")
				Poll.add(user)
				Presence = xmpp.protocol.Presence(source, frm = TransportID)
				#Presence.setStatus("") # is it needed?
				Presence.setShow("available")
				Sender(Component, Presence)
				user.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, source, answer, jidTo)
