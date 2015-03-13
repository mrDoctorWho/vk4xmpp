# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from __main__ import *


def last_handler_threaded(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped() ## By following standard we should use destination with resource, If we don't client must think user is offline. So, let it be.
	id = vk2xmpp(destination)
	if id == TransportID:
		last = int(time.time() - startTime)
		name = IDENTIFIER["name"]
	elif source in Transport and id in Transport[source].friends:
		last = Transport[source].vk.method("execute.getLastTime", {"uid": id}) or 0
		last = int(time.time() - last)
		name = Transport[source].vk.getUserData(id).get("name", "Unknown")
	else:
		raise xmpp.NodeProcessed()
	result = xmpp.Iq("result", to=jidFrom, frm=destination)
	result.setID(iq.getID())
	result.setTag("query", {"seconds": str(last)}, xmpp.NS_LAST)
	result.setTagData("query", name)
	sender(cl, result)

def last_handler(cl, iq):
	runThread(last_handler_threaded, (cl, iq))

def load():
	Component.RegisterHandler("iq", last_handler, "get", xmpp.NS_LAST)

def unload():
	Component.UnregisterHandler("iq", last_handler, "get", xmpp.NS_LAST)