# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.
# This module depends on mod_xhtml.

from __main__ import Users, logger
import xmpp
import mod_xhtml

def xhtml_handler(cl, msg):
	destination = msg.getTo().getStripped()
	source = msg.getFrom()
	if isinstance(source, (str, unicode)):
		logger.warning("Received message did not contain a valid jid: %s", msg)
		raise xmpp.NodeProcessed()
	source = source.getStripped()
	if source in Users and msg.getType() == "chat":
		user = Users[source]
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
MOD_FEATURES = [xmpp.NS_XHTML_IM]
MOD_FEATURES_USER = [xmpp.NS_XHTML_IM]
