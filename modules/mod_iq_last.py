# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from __main__ import *
import xmpp
import utils


@utils.threaded
def last_handler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	id = vk2xmpp(destination)
	if id == TransportID:
		last = int(time.time() - startTime)
		name = IDENTIFIER["name"]
	elif source in Users and id in Users[source].friends:
		last = Users[source].vk.method("execute.getLastTime", {"uid": id}) or 0
		last = int(time.time() - last)
		name = Users[source].vk.getUserData(id).get("name", "Unknown")
	else:
		raise xmpp.NodeProcessed()
	result = xmpp.Iq("result", to=jidFrom, frm=destination)
	result.setID(iq.getID())
	result.setTag("query", {"seconds": str(last)}, xmpp.NS_LAST)
	result.setTagData("query", name)
	sender(cl, result)


MOD_TYPE = "iq"
MOD_HANDLERS = ((last_handler, "get", xmpp.NS_LAST, False),)
MOD_FEATURES = [xmpp.NS_LAST]
MOD_FEATURES_USER = [xmpp.NS_LAST]
