# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

"""
Module purpose is to receive and handle messages
"""

from __main__ import *
from __main__ import _


def reportReceived(msg, jidFrom, jidTo):
	"""
	Reports if message is received
	"""
	if msg.getTag("request"):
		answer = xmpp.Message(jidFrom, frm=jidTo)
		tag = answer.setTag("received", namespace=xmpp.NS_RECEIPTS)
		tag.setAttr("id", msg.getID())
		answer.setID(msg.getID())
		return answer


def acceptCaptcha(cl, args, jidTo, source):
	"""
	Accepts the captcha value in 2 possible ways:
		1. User sent a message
		2. User sent an IQ with the captcha value
	"""
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
				Presence = xmpp.Presence(source, show=None, frm=TransportID)
				sender(Component, Presence)
				user.tryAgain()
			else:
				answer = _("Captcha invalid.")
		else:
			answer = _("Not now. Ok?")
		if answer:
			sendMessage(cl, source, jidTo, answer)


def message_handler_threaded(cl, msg):
	body = msg.getBody()
	jidTo = msg.getTo()
	destination = jidTo.getStripped()
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	
	if msg.getType() == "chat" and source in Transport:
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
						acceptCaptcha(cl, args, jidTo, source)
						answer = reportReceived(msg, jidFrom, jidTo)
					elif text == "!eval" and args and source in ADMIN_JIDS:
						try:
							result = unicode(eval(args))
						except Exception:
							result = returnExc()
						sendMessage(cl, source, jidTo, result)
					elif text == "!exec" and args and source in ADMIN_JIDS:
						try:
							exec(unicode(args + "\n"), __main__.__builtins__.globals())
						except Exception:
							result = returnExc()
						else:
							result = "Done."
						sendMessage(cl, source, jidTo, result)
			else:
				uID = jidTo.getNode()
				vkMessage = user.vk.sendMessage(body, uID)
				if vkMessage:
					answer = reportReceived(msg, jidFrom, jidTo)
			if answer:
				sender(cl, answer)
	executeHandlers("msg02", (msg,))


def message_handler(cl, msg):
	runThread(message_handler_threaded, (cl, msg))


def load():
	TransportFeatures.add(xmpp.NS_RECEIPTS)
	Component.RegisterHandler("message", message_handler)


def unload():
	TransportFeatures.remove(xmpp.NS_RECEIPTS)
	Component.UnregisterHandler("message", message_handler)