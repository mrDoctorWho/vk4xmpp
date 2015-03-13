# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from __main__ import *

def main_handler(cl, iq):
	jidFrom = iq.getFrom()
	if WhiteList:
		if jidFrom and jidFrom.getDomain() not in WhiteList:
			sender(cl, utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, "You're not in the white-list"))
			raise xmpp.NodeProcessed()

	ping = iq.getTag("ping")
	if ping and ping.getNamespace() == xmpp.NS_PING:
		jidTo = iq.getTo()
		if jidTo == TransportID:
			sender(cl, iq.buildReply("result"))


def load():
	Component.RegisterHandler("iq", main_handler, makefirst=True)


def unload():
	Component.UnregisterHandler("iq", main_handler)