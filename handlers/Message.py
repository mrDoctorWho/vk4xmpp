# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

def msgRecieved(msg, jidFrom, jidTo):
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom)
		tag = answer.setTag("received", namespace = "urn:xmpp:receipts")
		tag.setAttr("id", msg.getID())
		answer.setFrom(jidTo)
		answer.setID(msg.getID())
		return answer

def msgHandler(cl, msg):
	mType = msg.getType()
	body = msg.getBody()
	jidTo = msg.getTo()
	jidToStr = jidTo.getStripped()
	jidFrom = msg.getFrom()
	jidFromStr = jidFrom.getStripped()
	if jidFromStr in Transport and mType == "chat":
		user = Transport[jidFromStr]
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
				Presence = xmpp.protocol.Presence(jidFromStr, frm = TransportID)
				Presence.setStatus("") # is it needed?
				Presence.setShow("available")
				Sender(Component, Presence)
				user.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, jidFromStr, answer, jidTo)
