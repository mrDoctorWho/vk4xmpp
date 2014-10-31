# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *

def version_handler(cl, iq):
	jidTo = iq.getTo()
	if jidTo == TransportID:
		result = iq.buildReply("result")
		query = result.getTag("query")
		query.setTagData("name", IDENTIFIER["name"])
		query.setTagData("version", Revision)
		query.setTagData("os", "%s / %s" % (OS, Python))
		sender(cl, result)


def load():
	Component.RegisterHandler("iq", version_handler, "get", xmpp.NS_VERSION)