# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

"""
Module purpose is to accept the captcha value from iq
"""

from __main__ import TransportID, Transport
import xmpp
import utils
import mod_msg_main as mod_msg

@utils.threaded
def captcha_handler(cl, iq):
	if iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		source = iq.getFrom().getStripped()
		if source in Transport:
			destination = iq.getTo()
			if destination == TransportID:
				capTag = iq.getTag("captcha")
				xTag = capTag.getTag("x", {}, xmpp.NS_DATA)
				ocrTag = xTag.getTag("field", {"var": "ocr"})
				value = ocrTag.getTagData("value")
				mod_msg.acceptCaptcha(value, source, destination)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_CAPTCHA]
MOD_HANDLERS = ((captcha_handler, "set", "", False),)