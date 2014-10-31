# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

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
			query.setTagData("desc", "Enter api token")
			query.setTag("prompt")
			result.setPayload([query])

		elif iqChildren and itype == "set":
			token = ""
			for node in iqChildren:
				if node.getName() == "prompt":
					token = node.getData()
					break
			if token:
				xNode = xmpp.simplexml.Node("prompt")
				xNode.setData(token[0])
				result.setQueryPayload([xNode])
		else:
			raise xmpp.NodeProcessed()
		sender(cl, result)


def load():
	Component.RegisterHandler("iq", gateway_handler, "", xmpp.NS_GATEWAY)