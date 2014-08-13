# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from __main__ import *
from __main__ import _

def reportReceived(msg, jidFrom, jidTo):
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom)
		tag = answer.setTag("received", namespace = "urn:xmpp:receipts")
		tag.setAttr("id", msg.getID())
		answer.setFrom(jidTo)
		answer.setID(msg.getID())
		return answer

def accpeptCaptcha(cl, args, jidTo, source):
	if args:
		answer = None
		user = Transport[source]
		if user.vk.engine.captcha:
			logger.debug("user %s called captcha challenge" % source)
			user.vk.engine.captcha["key"] = args
			success = False
			try:
				logger.debug("retrying for user %s" % source)
				success = user.vk.engine.retry()
			except api.CaptchaNeeded:
				logger.error("retry for user %s failed!" % source)
				user.vk.captchaChallenge()
			if success:
				logger.debug("retry for user %s successed!" % source)
				answer = _("Captcha valid.")
				Presence = xmpp.Presence(source, frm = TransportID)
				Presence.setShow("available")
				sender(Component, Presence)
				user.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			msgSend(cl, source, jidTo, answer)


def message_handler(cl, msg):
	mType = msg.getType()
	body = msg.getBody()
	jidTo = msg.getTo()
	destination = jidTo.getStripped()
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	
	if source in Transport:
		user = Transport[source]
		if msg.getTag("composing"):
			target = vk2xmpp(destination)
			if target != TransportID:
				user.vk.method("messages.setActivity", {"user_id": target, "type": "typing"}, True)

		if body:
			answer = None
			if jidTo == TransportID:
				raw = body.split(None, 1)
				if len(raw) > 1:
					text, args = raw
					args = args.strip()
					if text == "!captcha" and args:
						captchaAccept(cl, args, jidTo, source)
						answer = reportReceived(msg, jidFrom, jidTo)
					elif text == "!eval" and args and source == evalJID:
						try:
							result = unicode(eval(args))
						except Exception:
							result = returnExc()
						sendMessage(cl, source, jidTo, result)
					elif text == "!exec" and args and source == evalJID:
						try:
							exec(unicode(args + "\n"), globals())
						except Exception:
							result = returnExc()
						else:
							result = "Done."
						msgSend(cl, source, jidTo, result)
			else:
				uID = jidTo.getNode()
				vkMessage = user.vk.sendMessage(body, uID)
				if vkMessage:
					answer = reportReceived(msg, jidFrom, jidTo)
			if answer:
				sender(cl, answer)
	for func in Handlers["msg02"]:
		func(msg)
		

def load():
	Component.RegisterHandler("message", message_handler, "chat")