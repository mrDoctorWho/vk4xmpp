# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.
# This module depends on mod_xhtml.

from __main__ import Transport, logger
import xmpp
import mod_xhtml

def xhtml_handler(cl, msg):
	destination = msg.getTo().getStripped()
	source = msg.getFrom().getStripped()
	if source in Transport and msg.getType() == "chat":
		user = Transport[source]
		html = msg.getTag("html")
		if html and html.getTag("body"):  # XHTML-IM!
			logger.debug("fetched xhtml image from %s", source)
			try:
				xhtml = mod_xhtml.parseXHTML(user, html, source, destination)
			except Exception:
				xhtml = False
			if xhtml:
				raise xmpp.NodeProcessed()

MOD_TYPE = "message"
MOD_HANDLERS = ((xhtml_handler, "", "", True),)
MOD_FEATURES = []
MOD_FEATURES_USER = [xmpp.NS_XHTML_IM]
