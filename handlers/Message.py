# coding: utf
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
	jidFrom = msg.getFrom()
	jidFromStr = jidFrom.getStripped()
	if jidFromStr in Transport and mType == "chat":
		Class = Transport[jidFromStr]
		jidTo = msg.getTo()
		body = msg.getBody()
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
							msg = unicode(eval(args))
						except Exception, ErrorMsg:
							try:
								ErrorMsg = str(ErrorMsg)
							except:
								ErrorMsg = unicode(ErrorMsg)
							msg = 'Error! %s' % ErrorMsg
						msgSend(cl, jidFromStr, msg, jidTo)
			else:
				uID = jidTo.getNode()
				vkMessage = Class.msg(body, uID)
				if vkMessage:
					answer = msgRecieved(msg, jidFrom, jidTo)
			if answer:
				Sender(cl, answer)
		else:
			raise xmpp.NodeProcessed()

def captchaAccept(cl, args, jidTo, jidFromStr):
	if args:
		answer = None
		Class = Transport[jidFromStr]
		if Class.vk.engine.captcha:
			logger.debug("user %s called captcha challenge" % jidFromStr)
			Class.vk.engine.captcha["key"] = args
			retry = False
			try:
				logger.debug("retrying for user %s" % jidFromStr)
				retry = Class.vk.engine.retry()
			except api.CaptchaNeeded:
				logger.error("retry for user %s failed!" % jidFromStr)
				Class.vk.captchaChallenge()
			if retry:
				logger.debug("retry for user %s OK" % jidFromStr)
				answer = _("Captcha valid.")
				Presence = xmpp.protocol.Presence(self.jidFrom, frm = TransportID)
				Presence.setStatus("") # is it needed?
				Presence.setShow("available")
				Sender(Presence)
				Class.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, jidFromStr, answer, jidTo)
