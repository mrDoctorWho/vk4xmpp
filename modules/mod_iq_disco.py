# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *
from __main__ import _
from utils import buildDataForm as buildForm
from xmpp import DataForm as getForm

NODES = {"admin": ("Delete users", 
					"Global message", 
					"Show crashlogs", 
					"Reload config", 
					"Global Transport settings", 
					"Check an API token"), 
		"user": ("Edit settings",)}

FORM_TYPES = ("text-single", "text-multi", "jid-multi")

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
		if source in ADMIN_JIDS:
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
		if node == "Online users" and source in ADMIN_JIDS:
			users = Transport.keys()
			for user in users:
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == "All users" and source in ADMIN_JIDS:
			users = getUsersList()
			for user in users:
				user = user[0]
				payload.append(xmpp.Node("item", { "name": user, "jid": user }))
			result.setQueryPayload(payload)

		elif node == xmpp.NS_COMMANDS:
			if source in ADMIN_JIDS:
				for node in NODES["admin"]:
					payload.append(xmpp.Node("item", {"node": node, "name": node, "jid": TransportID}))
			for node in NODES["user"]:
				payload.append(xmpp.Node("item", {"node": node, "name": node, "jid": TransportID}))
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


def checkAPIToken(token):
	vk = VK()
	try:
		auth = vk.auth(token, True, False)
		if not auth:    # in case if VK() won't raise an exception
			raise api.AuthError("Auth failed")
		else:
			vk.online = True
			userID = vk.getUserID()
			name = vk.getUserData(userID)
			data = {"auth": auth, "name": name, "id": str(userID), "friends_count": len(vk.getFriends())}
	except (api.VkApiError, Exception):
		data = wException()
	return data


def dictToDataForm(_dict, _fields=None):
	_fields = _fields or []
	for key, value in _dict.iteritems():
		result = {"var": key, "value": value}
		if isinstance(value, int) and not isinstance(value, bool):
			type = "text-signle"

		elif isinstance(value, bool):
			print key, value
			type = "boolean"
			value = utils.normalizeValue(value)
			print key,value

		elif isinstance(value, dict):
			dictToDataForm(value, _fields)
		elif isinstance(value, str):
			type = "text-single"
			if "\n" in value:
				type = "text-multi"
		_fields.append({"var": key, "label": key, "value": value, "type": type})
	return _fields


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
		simpleForm = buildForm(fields=[dict(var="FORM_TYPE", type="hidden", value=xmpp.NS_ADMIN)])
		if node and action != "cancel":
			if not form:
				commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": iq.getID()}, xmpp.NS_COMMANDS)
			if source in ADMIN_JIDS:
				if node == "Delete users":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "jids", "type": "jid-multi", "label": _("Jabber ID's"), "required": True}])
					else:
						form = getForm(node=form).asDict()
						if form.get("jids"):
							runThread(deleteUsers, (form["jids"],))
						completed = True

				elif node == "Global message":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "text", "type": "text-multi", "label": _("Message"), "required": True}], 
							title=_("Enter the message text"))
					else:
						form = getForm(node=form).asDict()
						if form.has_key("text"):
							text = "\n".join(form["text"])
							runThread(sendGlobalMessage, (text,))
						completed = True

				elif node == "Show crashlogs":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "filename", "type": "list-single", "label": "Filename", 
								"options": os.listdir("crash") if os.path.exists("crash") else []}], 
							title="Choose wisely")

					else:
						form = getForm(node=form).asDict()
						if form.get("filename"):
							filename = "crash/%s" % form["filename"]
							body = None
							if os.path.exists(filename):
								body = rFile(filename)
							commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": sessionid}, xmpp.NS_COMMANDS)
							simpleForm = buildForm(simpleForm, 
								fields=[{"var": "body", "type": "text-multi", "label": "Error body", "value": body}]								)
							commandTag.addChild(node=simpleForm)
							completed = True

				elif node == "Check an API token":
					
						if not form:
							simpleForm = buildForm(simpleForm, 
								fields=[{"var": "token", "type": "text-single", "label": "API Token"}],
								title=_("Enter the API token"))
						else:
							commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": sessionid}, xmpp.NS_COMMANDS)
							form = getForm(node=form).asDict()
							if form.get("token"):
								token = form["token"]
								_result = checkAPIToken(token)

								if isinstance(_result, dict):
									_fields = dictToDataForm(_result)
								else:
									_fields = [{"var": "body", "value": str(_result), "type": "text-multi" }]

								simpleForm = buildForm(simpleForm, fields=_fields)
								commandTag.addChild(node=simpleForm)
								completed = True
		
				elif node == "Reload config":
					try:
						execfile(Config, globals())
					except Exception:
##						commandTag = result.setTag("command", {"status": "executing", "node": node, "sessionid": sessionid}, xmpp.NS_COMMANDS)
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "body", "type": "text-multi", "label": "Error while loading the config file", "value": wException()}])
						
					completed = True

				elif node == "Global Transport settings":
					config = transportSettings.settings
					if not form:
						_fields = []
						for key, values in config.items():
							_fields.append({"var": key, "label": _(values["label"]), 
								"type": values.get("type", "boolean"),
								 "value": values["value"], "desc": _(values.get("desc"))})
						simpleForm = buildForm(simpleForm, fields=_fields, title="Choose wisely")

					elif form and source in Transport:
						form = getForm(node=form).asDict()
						for key in form.keys():
							if key in config.keys():
								transportSettings.settings[key]["value"] = utils.normalizeValue(form[key])
						completed = True

			if node == "Edit settings" and source in Transport:
				logger.info("user want to edit his settings (jid: %s)" % source)
				config = Transport[source].settings
				if not form:
					user = Transport[source]
					_fields = []
					for key, values in config.items():
						_fields.append({"var": key, "label": _(values["label"]), 
							"type": values.get("type", "boolean"), 
							"value": values["value"], "desc": _(values.get("desc"))})

					simpleForm = buildForm(simpleForm, fields=_fields, title="Choose wisely")

				elif form and source in Transport:
					form = getForm(node=form).asDict()
					for key in form.keys():
						if key in config.keys():
							Transport[source].settings[key] = utils.normalizeValue(form[key])
					completed = True
			
			if completed:
				result.setTag("command", {"status": "completed", "node": node, "sessionid": sessionid}, namespace=xmpp.NS_COMMANDS)
			elif not form:
				commandTag.addChild(node=simpleForm)

		sender(cl, result)


def load():
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_INFO)
	Component.RegisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_ITEMS)
	Component.RegisterHandler("iq", commands_handler, "set")


def unload():
	Component.UnregisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_INFO)
	Component.UnregisterHandler("iq", disco_handler, "get", xmpp.NS_DISCO_ITEMS)
	Component.UnregisterHandler("iq", commands_handler, "set")