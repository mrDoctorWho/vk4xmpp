# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.
# This module depends on mod_xhtml.

from __main__ import *
import mod_xhtml

def xhtml_handler(cl, msg):
	destination = msg.getTo().getStripped()
	source = msg.getFrom().getStripped()
	if source in Transport:
		user = Transport[source]
		html = msg.getTag("html") 
		if html and html.getTag("body"): ## XHTML-IM!
			logger.debug("msgHandler: fetched xhtml image from %s" % source)
			try:
				xhtml = mod_xhtml.parseXHTML(user, html, source, destination)
			except Exception:
				xhtml = False
			if xhtml:
				raise xmpp.NodeProcessed()

def load():
	Component.RegisterHandler("message", xhtml_handler, "chat")


def unload():
	Component.UnregisterHandler("message", xhtml_handler, "chat")