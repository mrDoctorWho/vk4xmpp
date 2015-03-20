# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

"""
Module purpose is to accept the captcha value from iq
"""

from __main__ import *
import mod_msg_main as mod_msg

def captcha_handler_threaded(cl, iq):
	if iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		source = iq.getFrom().getStripped()
		if source in Transport:
			jidTo = iq.getTo()
			if jidTo == TransportID:
				capTag = iq.getTag("captcha")
				xTag = capTag.getTag("x", {}, xmpp.NS_DATA)
				ocrTag = xTag.getTag("field", {"var": "ocr"})
				value = ocrTag.getTagData("value")
				mod_msg.acceptCaptcha(cl, value, jidTo, source)


def captcha_handler(cl, iq):
	runThread(captcha_handler_threaded, (cl, iq))


def load():
	TransportFeatures.add(xmpp.NS_CAPTCHA)
	Component.RegisterHandler("iq", captcha_handler, "set")


def unload():
	TransportFeatures.remove(xmpp.NS_CAPTCHA)
	Component.UnregisterHandler("iq", captcha_handler, "set")