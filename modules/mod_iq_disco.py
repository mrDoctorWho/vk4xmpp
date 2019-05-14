# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.
# Warning: This module contains not optimal and really ugly code.


from __main__ import *
from __main__ import _
from utils import buildDataForm as buildForm, buildIQError
from xmpp import DataForm
from traceback import format_exc

import xmpp
import modulemanager


class Node(object):
	"""
	Ad-Hoc nodes
	"""
	DELETE_USERS = "Delete users"
	GLOBAL_MESSAGE = "Global message"
	SHOW_CRASH_LOGS = "Show crash logs"
	RELOAD_CONFIG = "Reload config"
	GLOBAL_SETTINGS = "Global Transport Settings"
	CHECK_API_TOKEN = "Check an API token"
	UNLOAD_MODULES = "Unload modules"
	RELOAD_MODULES = "(Re)load modules"
	RELOAD_EXTENSIONS = "Reload extensions"
	EDIT_SETTINGS = "Edit settings"
	EXTERMINATE_CHATS = "Exterminate chats"
	USERS_ONLINE = "Online users"
	USERS_TOTAL = "All users"


NODES = {"admin": (Node.DELETE_USERS,
					Node.GLOBAL_MESSAGE,
					Node.SHOW_CRASH_LOGS,
					Node.RELOAD_CONFIG,
					Node.GLOBAL_SETTINGS,
					Node.CHECK_API_TOKEN,
					Node.UNLOAD_MODULES,
					Node.RELOAD_MODULES,
					Node.RELOAD_EXTENSIONS),
		"user": (Node.EDIT_SETTINGS,
				Node.EXTERMINATE_CHATS)}


def getFeatures(destination, source, ns, disco=False):
	if destination == TransportID:
		features = TransportFeatures
	else:
		features = UserFeatures
	payload = [xmpp.Node("identity", IDENTIFIER)]
	if source in ADMIN_JIDS and disco:
		payload.append(xmpp.Node("item", {"node": Node.USERS_ONLINE, "name": Node.USERS_ONLINE, "jid": TransportID}))
		payload.append(xmpp.Node("item", {"node": Node.USERS_TOTAL, "name": Node.USERS_TOTAL, "jid": TransportID}))
	if ns == xmpp.NS_DISCO_INFO:
		for key in features:
			node = xmpp.Node("feature", {"var": key})
			payload.append(node)
	return payload


def disco_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	ns = iq.getQueryNS()
	node = iq.getTagAttr("query", "node")
	result = iq.buildReply("result")
	payload = []
	if node:
		if source in ADMIN_JIDS:
			users = []
			if node == "Online users":
				users = Users.keys()
			elif node == "All users":
				users = getUsersList()
				users = [user[0] for user in users]

			for user in users:
				payload.append(xmpp.Node("item", {"name": user, "jid": user}))

		if node == xmpp.NS_COMMANDS:
			nodes = NODES["user"]
			if source in ADMIN_JIDS:
				nodes += NODES["admin"]
			for node in nodes:
				payload.append(xmpp.Node("item", {"node": node, "name": node, "jid": TransportID}))

		elif CAPS_NODE in node:
			payload = getFeatures(destination, source, ns)

		elif not payload:
			result = buildIQError(iq, xmpp.ERR_BAD_REQUEST)

	else:
		payload = getFeatures(destination, source, ns, True)

	if payload:
		result.setQueryPayload(payload)
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
		users = Users.keys()
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
			raise api.AuthError("Auth failed!")
		else:
			vk.online = True
			userID = vk.getUserPreferences()[0]
			name = vk.getUserData(userID)
			data = {"auth": auth, "name": name, "friends_count": len(vk.getFriends())}
	except (api.VkApiError, Exception):
		data = format_exc()
	return data


def dictToDataForm(_dict, _fields=None):
	"""
	Makes a buildForm()-compatible dict from a random key-value dict
	converts boolean types to a boolean field,
	converts multiline string to a text-multi field and so on.
	"""
	_fields = _fields or []
	for key, value in _dict.iteritems():
		if isinstance(value, int) and not isinstance(value, bool):
			fieldType = "text-single"

		elif isinstance(value, bool):
			fieldType = "boolean"
			value = utils.normalizeValue(value)

		elif isinstance(value, dict):
			dictToDataForm(value, _fields)

		elif isinstance(value, (str, unicode)):
			fieldType = "text-single"
			if "\n" in value:
				fieldType = "text-multi"
		else:
			logger.warning("unknown type \"%s\" for value %s", type(value), value)
			fieldType = "text-single"
		_fields.append({"var": key, "label": key, "value": value, "type": fieldType})
	return _fields


def getConfigFields(config):
	fields = []
	for key, values in config.items():
		fields.append({"var": key, "label": _(values["label"]),
			"type": values.get("type", "boolean"),
			"value": values["value"], "desc": _(values.get("desc"))})
	fields = sorted(fields, key=lambda x: x["label"])
	return fields


def getUserChats(source):
	result = runDatabaseQuery("select jid, owner, user from groupchats where user=?", (source,), many=True)
	return result


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
			dictForm = DataForm(node=form).asDict()
			if source in ADMIN_JIDS:
				if node == Node.DELETE_USERS:
					if not form:
						simpleForm = buildForm(simpleForm,
							fields=[{"var": "jids", "type": "jid-multi", "label": _("Jabber ID's"), "required": True}])
					else:
						if dictForm.get("jids"):
							utils.runThread(deleteUsers, (dictForm["jids"],))
						simpleForm = None
						completed = True

				elif node == Node.GLOBAL_MESSAGE:
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

				elif node == Node.SHOW_CRASH_LOGS:
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

				elif node == Node.CHECK_API_TOKEN:
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

				elif node == Node.RELOAD_CONFIG:
					simpleForm = None
					completed = True
					try:
						execfile(Config, globals())
						note = "Reloaded well. You might need to reload modules for the settings to take effect"
					except Exception:
						note = format_exc()

				elif node == Node.RELOAD_EXTENSIONS:
					simpleForm = None
					completed = True
					try:
						loadExtensions("extensions")
						note = "Reloaded well."
					except Exception:
						note = format_exc()

				elif node == Node.GLOBAL_SETTINGS:
					config = Transport.settings
					if not form:
						simpleForm = buildForm(simpleForm, fields=getConfigFields(config), title="Choose wisely")

					elif form:
						for key in dictForm.keys():
							if key in config.keys():
								config[key]["value"] = utils.normalizeValue(dictForm[key])
						note = "The settings were changed."
						simpleForm = None
						completed = True

				elif node == Node.RELOAD_MODULES:
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

				elif node == Node.UNLOAD_MODULES:
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

			if node == Node.EDIT_SETTINGS and source in Users:
				logger.info("user want to edit their settings (jid: %s)" % source)
				config = Users[source].settings
				if not form:
					simpleForm = buildForm(simpleForm, fields=getConfigFields(config), title="Choose wisely")

				elif form:
					for key in dictForm.keys():
						if key in config:
							config[key] = utils.normalizeValue(dictForm[key])
					note = "The settings were changed."
					simpleForm = None
					completed = True

			elif node == Node.EXTERMINATE_CHATS:
				if not form:
					chats = getUserChats(source)
					if chats:
						_fields = dictToDataForm(dict([(chat[0], False) for chat in chats]))
						simpleForm = buildForm(simpleForm, fields=_fields, title="Delete chats")
					else:
						note = "Nothing to delete"
						completed = True
						simpleForm = None
				elif form:
					# all user's chats
					chats = getUserChats(source)
					newChats = dictForm.keys()
					exterminateChats(chats=filter(lambda chat: chat[0] in newChats, chats))
					note = "Yay! Everything deleted!"
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
MOD_FEATURES_USER = [xmpp.NS_DISCO_INFO]
MOD_HANDLERS = ((disco_handler, "get", [xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS], False), (commands_handler, "set", "", False))
FORM_TYPES = ("text-single", "text-multi", "jid-multi")
