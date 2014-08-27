# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *

def getUsersList():
	with Database(DatabaseFile) as db:
		db("select jid from users")
		result = db.fetchall()
	return result

def disco_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	ns = iq.getQueryNS()
	node = iq.getTagAttr("query", "node")
	
	if not node:
		queryPayload = []
		if destination == TransportID:
			features = TransportFeatures
		else:
			features = UserFeatures

		result = iq.buildReply("result")
		queryPayload.append(xmpp.Node("identity", IDENTIFIER))
		## collect all disco Nodes by handlers
		queryPayload.append(xmpp.Node("item", {"node": "Online users", "name": "Online users", "jid": TransportID }))
		if ns == xmpp.NS_DISCO_INFO:
			for key in features:
				xNode = xmpp.Node("feature", {"var": key})
				queryPayload.append(xNode)
			
			result.setQueryPayload(queryPayload)
		
		elif ns == xmpp.NS_DISCO_ITEMS:
			result.setQueryPayload(queryPayload)

	elif node:
		if node == "Online users":
			payload = []
			users = getUsersList()
			for user in users:
				user = user[0]
				payload.append(xmpp.Node("item", { "name": user, "jid": user   }))
			result.setQueryPayload(payload)

		elif node == xmpp.NS_COMMANDS:
			result = iq.buildReply("result")
			queryPayload=[]
			queryPayload.append(xmpp.Node("item", {"node": "Online users", "name": "Online users", "jid": TransportID }))
			queryPayload.append(xmpp.Node("item", {"node": "Delete users", "name": "Delete users", "jid": TransportID }))

			result.setQueryPayload(queryPayload)

		else:
			raise xmpp.NodeProcessed()
	else:
		raise xmpp.NodeProcessed()

	sender(cl, result) 


def delete_jids(jids):
	for key in jids:
		try:
			removeUser(key)
		except:
			pass

def commands_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	ns = iq.getQueryNS()
	cmd = iq.getTag("command", namespace=xmpp.NS_COMMANDS)
	if cmd:
		result = iq.buildReply("result")
		node = iq.getTagAttr("command", "node")
		form = cmd.getTag("x", namespace=xmpp.NS_DATA)
		if form:
			form = xmpp.DataForm(node=form).asDict()
			if form.has_key("jids") and form["jids"]:
				runThread(delete_jids, (form['jids'],))
		else:
			result_ = result.setTag("command", {"status": "executing", "node": "Delete users", "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
			form = utils.buildDataForm(None, None, 
				[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN}, {"var": "jids", "type": "jid-multi", "label": "Jabber ID's", "required": True}], "Type JabberID in lines to remove it from db")
			result_.addChild(node=form)

		sender(cl, result)



def load():
	Component.RegisterHandler("iq", disco_handler, "get")#), xmpp.NS_DISCO_INFO)
	Component.RegisterHandler("iq", commands_handler, "set")
