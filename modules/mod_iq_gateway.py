# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *


def gateway_handler(cl, iq):
	jidTo = iq.getTo()
	itype = iq.getType()
	destination = jidTo.getStripped()
	iqChildren = iq.getQueryChildren()
	if destination == TransportID:
		result = iq.buildReply("result")
		if itype == "get" and not iqChildren:
			query = xmpp.Node("query", {"xmlns": xmpp.NS_GATEWAY})
			query.setTagData("desc", "Enter user ID")
			query.setTag("prompt")
			result.setPayload([query])

		elif iqChildren and itype == "set":
			user = ""
			for node in iqChildren:
				if node.getName() == "prompt":
					user = node.getData()
					break
			if user:
				xNode = xmpp.simplexml.Node("jid")
				xNode.setData("%s@%s" % (user[0], TransportID))
				result.setQueryPayload([xNode])
		else:
			raise xmpp.NodeProcessed()
		sender(cl, result)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_GATEWAY]
MOD_HANDLERS = ((gateway_handler, "", xmpp.NS_GATEWAY, False),)
