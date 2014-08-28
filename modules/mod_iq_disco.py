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
		payload = []
		if destination == TransportID:
			features = TransportFeatures
		else:
			features = UserFeatures

		result = iq.buildReply("result")
		payload.append(xmpp.Node("identity", IDENTIFIER))
		## collect all disco Nodes by handlers
		if source == evalJID: 
			payload.append(xmpp.Node("item", {"node": "Online users", "name": "Online users", "jid": TransportID }))
			payload.append(xmpp.Node("item", {"node": "All users", "name": "All users", "jid": TransportID }))
		if ns == xmpp.NS_DISCO_INFO:
			for key in features:
				xNode = xmpp.Node("feature", {"var": key})
				payload.append(xNode)
			
			result.setQueryPayload(payload)
		
		elif ns == xmpp.NS_DISCO_ITEMS:
			result.setQueryPayload(payload)

	elif node:
		result = iq.buildReply("result")
		payload = []
		if node == "Online users":
			users = Transport.keys()
			for user in users:
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == "All users":
			users = getUsersList()
			for user in users:
				user = user[0]
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == xmpp.NS_COMMANDS:
#			payload.append(xmpp.Node("item", {"node": "Online users", "name": "Online users", "jid": TransportID }))
			print source, evalJID
			if source == evalJID:
				payload.append(xmpp.Node("item", {"node": "Delete users", "name": "Delete users", "jid": TransportID }))
				payload.append(xmpp.Node("item", {"node": "Global message", "name": "Global message", "jid": TransportID }))
				payload.append(xmpp.Node("item", {"node": "Show crashlogs", "name": "Show crashlogs", "jid": TransportID }))
			payload.append(xmpp.Node("item", {"node": "Edit settings", "name": "Edit settings", "jid": TransportID }))
			result.setQueryPayload(payload)

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

nodes = ["Delete users", "Global message", "Edit settings", "Show crashlogs"]

def normalizeValue(value):
	if isNumber(value):
		value = int(value)
	elif value and value.lower() == "true":
		value = 1
	else:
		value = 0
	return value


def commands_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	ns = iq.getQueryNS()
	cmd = iq.getTag("command", namespace=xmpp.NS_COMMANDS)
	if cmd:
		result = iq.buildReply("result")
		node = iq.getTagAttr("command", "node")
		form = cmd.getTag("x", namespace=xmpp.NS_DATA)
		action = cmd.getAttr("action")

		if node in nodes and action != "cancel":
			if not form:
				result_ = result.setTag("command", {"status": "executing", "node": node, "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
			if node == "Delete users":
				if not form:
					form = utils.buildDataForm(None, None, 
						[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN}, 
							{"var": "jids", "type": "jid-multi", "label": "Jabber ID's", "required": True}], 
								"Type JabberIDs in lines to remove them from db")
					result_.addChild(node=form)
				else:
					form = xmpp.DataForm(node=form).asDict()
					if form.has_key("jids") and form["jids"]:
						runThread(delete_jids, (form["jids"],))

			elif node == "Global message":
				if not form:
					form = utils.buildDataForm(None, None, 
						[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN}, 
							{"var": "text", "type": "text-multi", "label": "Message", "required": True}], "Type a message text" )
					result_.addChild(node=form)
				else:
					form = xmpp.DataForm(node=form).asDict()
					if form.has_key("text"):
						text = "\n".join(form["text"])

			elif node == "Show crashlogs":
				if not form:
					form = utils.buildDataForm(None, None, 
						[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN}, 
							{"var": "filename", "type": "list-single", "label": "Filename", "options": os.listdir("crash") if os.path.exists("crash") else []}], "Choose wisely")
					result_.addChild(node=form)
				else:
					form = xmpp.DataForm(node=form).asDict()
					if form.has_key("filename") and form["filename"]:
						filename = "crash/%s" % form["filename"]
						body = None
						if os.path.exists(filename):
							body = rFile(filename)
						result_ = result.setTag("command", {"status": "executing", "node": node, "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
						form = utils.buildDataForm(None, None,
							[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
								{"var": "body", "type": "text-multi", "label": "Error body", "value": body}]
							)
						result_.addChild(node=form)


			elif node == "Edit settings" and source in Transport:
				config = Transport[source].settings
				if not form:
					user = Transport[source]
					form = utils.buildDataForm(None, None,
						[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
						{"var": "groupchats", "type": "boolean", "label": "Handle groupchats", "value": config["groupchats"]},
						{"var": "status-to-vk", "type": "boolean", "label": "Publish my status in vk", "value": config["status-to-vk"]}
						], "Choose wisely")
					result_.addChild(node=form)
				elif form and source in Transport:
					form = xmpp.DataForm(node=form).asDict()
					## TODO: Check if boolean, use transquare's code to check
					if form.has_key("groupchats"):
						config["groupchats"] = normalizeValue(form["groupchats"])
					if form.has_key("status-to-vk"):
						config["status-to-vk"] = normalizeValue(form["status-to-vk"])



		sender(cl, result)


def c_ommands_handler(cl, iq):
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


		elif cmd.getAttr("action") != "cancel":
			result_ = result.setTag("command", {"status": "executing", "node": node, "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
			if node == "Delete users":
				pass
			
			elif node == "Global message":
				form = utils.buildDataForm(None, None, 
					[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN}, 
						{"var": "text", "type": "text-multi", "label": "Message", "required": True}
#							"Type a message text" 
						])


		sender(cl, result)



def load():
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_INFO)
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_ITEMS)
	Component.RegisterHandler("iq", commands_handler, "set")
