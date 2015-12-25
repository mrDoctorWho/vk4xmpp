# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

"""
Module purpose is to receive and handle messages
"""

from __main__ import *
from __main__ import _
import utils


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


def acceptCaptcha(key, source, destination):
	"""
	Accepts the captcha value in 2 possible ways:
		1. User sent a message
		2. User sent an IQ with the captcha value
	"""
	if args:
		user = Transport[source]
		logger.debug("user %s called captcha challenge" % source)
		try:
			user.captchaChallenge(key)
			valid = True
		except api.CaptchaNeeded:
			valid = False
			answer = _("Captcha invalid.")
		else:
			logger.debug("retry for user %s successed!" % source)
			answer = _("Captcha valid.")
			sendPresence(source, TransportID, caps=True)

		sendMessage(source, destination, answer, mtype="normal")
		if not valid:
			executeHandlers("evt04", (user, user.vk.engine.captcha["img"]))


@utils.threaded
def message_handler(cl, msg):
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
				with user.sync:
					user.vk.method("messages.setActivity", {"user_id": target, "type": "typing"}, True)

		if body:
			answer = None
			if jidTo == TransportID:
				raw = body.split(None, 1)
				if len(raw) > 1:
					text, args = raw
					args = args.strip()
					if text == "!captcha" and args:
						acceptCaptcha(args, source, jidTo)
						answer = reportReceived(msg, jidFrom, jidTo)

			else:
				uID = jidTo.getNode()
				with user.sync:
					if user.vk.sendMessage(body, uID):
						answer = reportReceived(msg, jidFrom, jidTo)
			if answer:
				sender(cl, answer)
	executeHandlers("msg02", (msg,))


MOD_TYPE = "message"
MOD_FEATURES = [xmpp.NS_RECEIPTS]
MOD_FEATURES_USER = MOD_FEATURES
MOD_HANDLERS = ((message_handler, "", "", False),)
