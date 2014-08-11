# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *

def disco_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	ns = iq.getQueryNS()
	node = iq.getTagAttr("query", "node")
	if not node:
		queryPayload = []
		if destination == TransportID:
			features = TransportFeatures
		else:
			features = UserFeatures

		result = iq.buildReply("result")
		queryPayload.append(xmpp.Node("identity", IDENTIFIER))
		if ns == xmpp.NS_DISCO_INFO:
			for key in features:
				xNode = xmpp.Node("feature", {"var": key})
				queryPayload.append(xNode)
			result.setQueryPayload(queryPayload)
		
		elif ns == xmpp.NS_DISCO_ITEMS:
			result.setQueryPayload(queryPayload)

		sender(cl, result) 

def load():
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_INFO)
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_ITEMS)