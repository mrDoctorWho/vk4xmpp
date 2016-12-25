# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

"""
Module purpose is to accept the captcha value from iq
"""

from __main__ import TransportID, Users
import xmpp
import utils
import mod_msg_main as mod_msg


@utils.threaded
def captcha_handler(cl, iq):
	if iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		source = iq.getFrom().getStripped()
		result = iq.buildReply("result")
		if source in Users:
			destination = iq.getTo()
			if destination == TransportID:
				capTag = iq.getTag("captcha")
				xTag = capTag.getTag("x", {}, xmpp.NS_DATA)
				ocrTag = xTag.getTag("field", {"var": "ocr"})
				value = ocrTag.getTagData("value")
				if mod_msg.acceptCaptcha(value, source, destination):
					cl.send(result)
				else:
					result = buildIQError(iq, xmpp.ERR_NOT_ACCEPTABLE)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_CAPTCHA]
MOD_HANDLERS = ((captcha_handler, "set", "", False),)
