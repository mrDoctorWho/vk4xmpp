# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.
# Warning: This module contain non-optimal and really bad code.


from __main__ import *
from __main__ import _
from utils import buildDataForm as buildForm
from xmpp import DataForm as getForm
import modulemanager

NODES = {"admin": ("Delete users", 
					"Global message", 
					"Show crash logs", 
					"Reload config", 
					"Global Transport settings", 
					"Check an API token",
					"Unload modules",
					"(Re)load modules",
					"Reload extensions"), 
		"user": ("Edit settings",)}


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
			payload.append(xmpp.Node("item", {"node": "Online users", "name": "Online users", "jid": TransportID}))
			payload.append(xmpp.Node("item", {"node": "All users", "name": "All users", "jid": TransportID}))
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


getUsersList = lambda: runDatabaseQuery("select jid from users", many=True)
deleteUsers = lambda jids: [utils.execute(removeUser, (key,), False) for key in jids]


def sendAnnouncement(destination, body, subject):
	msg = xmpp.Message(destination, body, "normal", frm=TransportID)
	timestamp = time.gmtime(time.time())
	msg.setSubject(subject)
	msg.setTimestamp(time.strftime("%Y%m%dT%H:%M:%S", timestamp))
	sender(Component, msg)


def sendGlobalMessage(body, subject, online):
	if online:
		users = Transport.keys()
	else:
		users = getUsersList()
	for user in users:
		sendAnnouncement(user, body, subject)


def checkAPIToken(token):
	"""
	Checks API token, returns dict or error
	"""
	vk = VK(token)
	try:
		auth = vk.auth()
		if not auth:  # in case if VK() won't raise an exception
			raise api.AuthError("Auth failed")
		else:
			vk.online = True
			userID = vk.getUserID()
			name = vk.getUserData(userID)
			data = {"auth": auth, "name": name, "friends_count": len(vk.getFriends())}
	except (api.VkApiError, Exception):
		data = wException()
	return data


def dictToDataForm(_dict, _fields=None):
	"""
	Makes a buildForm()-compatible dict from a random key-value dict
	converts boolean types to a boolean field,
	converts multiline string to a text-multi field and so on.
	"""
	_fields = _fields or []
	for key, value in _dict.iteritems():
		result = {"var": key, "value": value}
		if isinstance(value, int) and not isinstance(value, bool):
			type = "text-signle"

		elif isinstance(value, bool):
			type = "boolean"
			value = utils.normalizeValue(value)

		elif isinstance(value, dict):
			dictToDataForm(value, _fields)

		elif isinstance(value, str):
			type = "text-single"
			if "\n" in value:
				type = "text-multi"
		_fields.append({"var": key, "label": key, "value": value, "type": type})
	return _fields


def getConfigFields(config):
	fields = []
	for key, values in config.items():
		fields.append({"var": key, "label": _(values["label"]), 
			"type": values.get("type", "boolean"),
			 "value": values["value"], "desc": _(values.get("desc"))})
	return fields


@utils.safe
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
		note = None
		simpleForm = buildForm(fields=[dict(var="FORM_TYPE", type="hidden", value=xmpp.NS_ADMIN)])
		if node and action != "cancel":
			dictForm = getForm(node=form).asDict()
			if source in ADMIN_JIDS:
				if node == "Delete users":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "jids", "type": "jid-multi", "label": _("Jabber ID's"), "required": True}])
					else:
						if dictForm.get("jids"):
							utils.runThread(deleteUsers, (dictForm["jids"],))
						simpleForm = None
						completed = True

				elif node == "Global message":
					if not form:
						simpleForm = buildForm(simpleForm,
							fields=[
								{"var": "subject", "type": "text-single", "label": _("Subject"), "value": "Announcement"},
								{"var": "body", "type": "text-multi", "label": _("Message"), "required": True},
								{"var": "online", "type": "boolean", "label": "Online users only"}
							],
							title=_("Enter the message text"))
					else:
						body = "\n".join(dictForm["body"])
						subject = dictForm["subject"]
						online = dictForm["online"]
						utils.runThread(sendGlobalMessage, (body, subject, online))
						note = "The message was sent."
						simpleForm = None
						completed = True

				elif node == "Show crash logs":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "filename", "type": "list-single", "label": "Filename", 
								"options": os.listdir("crash") if os.path.exists("crash") else []}], 
							title="Choose wisely")

					else:
						if dictForm.get("filename"):
							filename = "crash/%s" % dictForm["filename"]
							body = None
							if os.path.exists(filename):
								body = rFile(filename)
							simpleForm = buildForm(simpleForm, 
								fields=[{"var": "body", "type": "text-multi", "label": "Error body", "value": body}])
							completed = True

				elif node == "Check an API token":
					if not form:
						simpleForm = buildForm(simpleForm, 
							fields=[{"var": "token", "type": "text-single", "label": "API Token"}],
							title=_("Enter the API token"))
					else:
						if dictForm.get("token"):
							token = dictForm["token"]
							_result = checkAPIToken(token)

							if isinstance(_result, dict):
								_fields = dictToDataForm(_result)
							else:
								_fields = [{"var": "body", "value": str(_result), "type": "text-multi"}]

							simpleForm = buildForm(simpleForm, fields=_fields)
							completed = True
	
				elif node == "Reload config":
					simpleForm = None
					completed = True
					try:
						execfile(Config, globals())
						note = "Reloaded well."
					except Exception:
						note = wException()

				elif node == "Reload extensions":
					simpleForm = None
					completed = True
					try:
						loadExtensions("extensions")
						note = "Reloaded well."
					except Exception:
						note = wException()

				elif node == "Global Transport settings":
					config = transportSettings.settings
					if not form:
						simpleForm = buildForm(simpleForm, fields=getConfigFields(config), title="Choose wisely")

					elif form:
						for key in dictForm.keys():
							if key in config.keys():
								transportSettings.settings[key]["value"] = utils.normalizeValue(dictForm[key])
						note = "The settings were changed."
						simpleForm = None
						completed = True

				elif node == "(Re)load modules":
					Manager = modulemanager.ModuleManager
					modules = Manager.list()
					if not form:
						_fields = dictToDataForm(dict([(mod, mod in Manager.loaded) for mod in modules]))
						simpleForm = buildForm(simpleForm, fields=_fields, title="(Re)load modules", 
							data=[_("Modules can be loaded or reloaded if they already loaded")])

					elif form:
						keys = []
						for key in dictForm.keys():
							if key in modules and utils.normalizeValue(dictForm[key]):
								keys.append(key)

						loaded, errors = Manager.load(list=keys)
						_fields = []
						if loaded:
							_fields.append({"var": "loaded", "label": "loaded", "type":
								"text-multi", "value": str.join("\n", loaded)})
						if errors:
							_fields.append({"var": "errors", "label": "errors", "type":
								"text-multi", "value": str.join("\n", errors)})

						simpleForm = buildForm(simpleForm, fields=_fields, title="Result")
						completed = True

				elif node == "Unload modules":
					Manager = modulemanager.ModuleManager
					modules = Manager.loaded.copy()
					modules.remove("mod_iq_disco")
					if not form:
						_fields = dictToDataForm(dict([(mod, False) for mod in modules]))
						if _fields:
							simpleForm = buildForm(simpleForm, fields=_fields, title="Unload modules")
						else:
							note = "Nothing to unload."
							completed = True
							simpleForm = None

					elif form:
						keys = []
						for key in dictForm.keys():
							if key in Manager.loaded and utils.normalizeValue(dictForm[key]):
								keys.append(key)

						unload = Manager.unload(list=keys)
						_fields = [{"var": "loaded", "label": "unloaded", "type": "text-multi", "value": str.join("\n", unload)}]

						simpleForm = buildForm(simpleForm, fields=_fields, title="Result")
						completed = True


			if node == "Edit settings" and source in Transport:
				logger.info("user want to edit their settings (jid: %s)" % source)
				config = Transport[source].settings
				if not form:
					user = Transport[source]
					simpleForm = buildForm(simpleForm, fields=getConfigFields(config), title="Choose wisely")

				elif form:
					for key in dictForm.keys():
						if key in config.keys():
							Transport[source].settings[key] = utils.normalizeValue(dictForm[key])
					note = "The settings were changed."
					simpleForm = None
					completed = True
			
			if completed:
				commandTag = result.setTag("command", {"status": "completed", 
					"node": node, "sessionid": sessionid}, namespace=xmpp.NS_COMMANDS)
				if simpleForm:
					commandTag.addChild(node=simpleForm)
				if note:
					commandTag.setTag("note", {"type": "info"})
					commandTag.setTagData("note", note)

			elif not form and simpleForm:
				commandTag = result.setTag("command", {"status": "executing", 
					"node": node, "sessionid": sessionid}, namespace=xmpp.NS_COMMANDS)
				commandTag.addChild(node=simpleForm)
		sender(cl, result)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_COMMANDS, xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS, xmpp.NS_DATA]
MOD_HANDLERS = ((disco_handler, "get", [xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS], False), (commands_handler, "set", "", False))
FORM_TYPES = ("text-single", "text-multi", "jid-multi")
