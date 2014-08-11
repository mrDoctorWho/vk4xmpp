# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *

def ping_handler(cl, iq):
	jidTo = iq.getTo()
	if jidTo == TransportID:
		sender(cl, iq.buildReply("result")) 

def load():
	Component.RegisterHandler("iq", ping_handler, "get", xmpp.NS_PING)