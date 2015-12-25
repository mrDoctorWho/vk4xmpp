# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *

def version_handler(cl, iq):
	jidTo = iq.getTo()
	if jidTo == TransportID:
		result = iq.buildReply("result")
		query = result.getTag("query")
		query.setTagData("name", IDENTIFIER["name"])
		query.setTagData("version", REVISION)
		query.setTagData("os", "%s / %s" % (OS, PYTHON_VERSION))
		sender(cl, result)


MOD_TYPE = "iq"
MOD_HANDLERS = ((version_handler, "get", xmpp.NS_VERSION, False),)
MOD_FEATURES = [xmpp.NS_VERSION]