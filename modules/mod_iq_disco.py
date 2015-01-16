# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *


NODES = {"admin": ("Delete users", "Global message", "Show crashlogs", "Reload config"), "user": ("Edit settings",)}

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
		if node == "Online users" and source == evalJID:
			users = Transport.keys()
			for user in users:
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == "All users" and source == evalJID:
			users = getUsersList()
			for user in users:
				user = user[0]
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == xmpp.NS_COMMANDS:
			if source == evalJID:
				for node in NODES["admin"]:
					payload.append(xmpp.Node("item", {"node": node, "name": node, "jid": TransportID }))
			for node in NODES["user"]:
				payload.append(xmpp.Node("item", {"node": node, "name": node, "jid": TransportID }))
			result.setQueryPayload(payload)

		else:
			raise xmpp.NodeProcessed()

	sender(cl, result)


def getUsersList():
	with Database(DatabaseFile) as db:
		db("select jid from users")
		result = db.fetchall()
	return result

def deleteUsers(jids):
	for key in jids:
		try:
			removeUser(key)
		except Exception:
			pass

def sendGlobalMessage(text):
	jids = getUsersList()
	for jid in jids:
		sendMessage(Component, jid[0], TransportID, text)


def commands_handler(cl, iq):
	source = iq.getFrom().getStripped()
	cmd = iq.getTag("command", namespace=xmpp.NS_COMMANDS)
	if cmd:
		result = iq.buildReply("result")
		node = iq.getTagAttr("command", "node")
		sessionid = iq.getTagAttr("command", "sessionid")
		form = cmd.getTag("x", namespace=xmpp.NS_DATA)
		action = cmd.getAttr("action")
		completed = False
		if node and action != "cancel":
			if not form:
				commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
			if source == evalJID:
				if node == "Delete users":
					if not form:
						form = utils.buildDataForm(None, None,
							[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
								{"var": "jids", "type": "jid-multi", "label": "Jabber ID's", "required": True}],
									"Type JabberIDs in lines to remove them from db")
						commandTag.addChild(node=form)
					else:
						form = xmpp.DataForm(node=form).asDict()
						if form.has_key("jids") and form["jids"]:
							runThread(deleteUsers, (form["jids"],))
						completed = True

				elif node == "Global message":
					if not form:
						form = utils.buildDataForm(None, None,
							[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
								{"var": "text", "type": "text-multi", "label": "Message", "required": True}], "Type a message text" )
						commandTag.addChild(node=form)
					else:
						form = xmpp.DataForm(node=form).asDict()
						if form.has_key("text"):
							text = "\n".join(form["text"])
							runThread(sendGlobalMessage, (text,))
						completed = True

				elif node == "Show crashlogs":
					if not form:
						form = utils.buildDataForm(None, None,
							[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
								{"var": "filename", "type": "list-single", "label": "Filename", "options": os.listdir("crash") if os.path.exists("crash") else []}], "Choose wisely")
						commandTag.addChild(node=form)
					else:
						form = xmpp.DataForm(node=form).asDict()
						if form.has_key("filename") and form["filename"]:
							filename = "crash/%s" % form["filename"]
							body = None
							if os.path.exists(filename):
								body = rFile(filename)
							commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": sessionid}, xmpp.NS_COMMANDS)
							form = utils.buildDataForm(None, None,
								[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
									{"var": "body", "type": "text-multi", "label": "Error body", "value": body}]
								)
							commandTag.addChild(node=form)
							completed = True
				elif node == "Reload config":
					try:
						execfile(Config, globals())
					except Exception:
						commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": sessionid}, xmpp.NS_COMMANDS)
						form = utils.buildDataForm(None, None, 
							[{"var": "FORM_TYPE", "type": "hidden", "value": xmpp.NS_ADMIN},
								{"var": "body", "type": "text-multi", "label": "Error while loading the config file", "value": wException()}])
						commandTag.addChild(node=form)
					completed = True


			if node == "Edit settings" and source in Transport:
				logger.info("user want to edit his settings (jid: %s)" % source)
				config = Transport[source].settings
				if not form:
					user = Transport[source]
					form_fields = [{"var": "FORM_TYPE", "type": "hidden"}]
					for key, values in config.items():
						form_fields.append({"var": key, "label": values["label"], "type": values.get("type", "boolean"), "value": values["value"]}) ## todo: Add support for list-multi and others?

					form = utils.buildDataForm(None, None, form_fields,	"Choose wisely")
					commandTag.addChild(node=form)
				elif form and source in Transport:
					form = xmpp.DataForm(node=form).asDict()
					for key in form.keys():
						if key in config.keys():
							Transport[source].settings[key] = utils.normalizeValue(form[key])
					completed = True
			
			if completed:
				result.setTag("command", {"status": "completed", "node": node, "sessionid": sessionid}, namespace=xmpp.NS_COMMANDS)

		sender(cl, result)



def load():
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_INFO)
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_ITEMS)
	Component.RegisterHandler("iq", commands_handler, "set")
