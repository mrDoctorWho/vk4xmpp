# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from __main__ import TransportID, sender
import xmpp
import utils

try:
	from __main__ import WhiteList
except ImportError:
	WhiteList = []

def main_iq_handler(cl, iq):
	source = iq.getFrom()
	if WhiteList:
		if source and source.getDomain() not in WhiteList:
			sender(cl, utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, "You're not in the white-list"))
			raise xmpp.NodeProcessed()

	ping = iq.getTag("ping")
	if ping and ping.getNamespace() == xmpp.NS_PING:
		jidTo = iq.getTo()
		if jidTo == TransportID:
			sender(cl, iq.buildReply("result"))


MOD_TYPE = "iq"
MOD_HANDLERS = ((main_iq_handler, "", "", True),)
MOD_FEATURES = [xmpp.NS_PING]