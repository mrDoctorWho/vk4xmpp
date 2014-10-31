# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.
## TODO: Handle set/get in separate functions.

from __main__ import *
from __main__ import _

URL_ACCEPT_APP = "http://simpleapps.ru/vk4xmpp.html#%d" % VK_ACCESS


def initializeUser(user, cl, iq):
	source = user.source
	result = iq.buildReply("result")
	connect = False
	try:
		connect = user.connect(True)
	except api.AuthError, e:
		result = utils.buildIQError(iq, xmpp.ERR_NOT_AUTHORIZED, _(str(e) + " Try to logging in by token."))
	else:
		if connect:
			try:
				user.initialize()
			except api.CaptchaNeeded:
				user.vk.captchaChallenge()
			except Exception: ## is there could be any other exception?
				crashLog("user.init")
				result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
			else:
				watcherMsg(_("New user registered: %s") % source)
		else:
			logger.error("user connection failed (jid: %s)" % source)
			result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
	sender(cl, result)

def register_handler(cl, iq):
	jidTo = iq.getTo()
	jidFrom = iq.getFrom()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	iType = iq.getType()
	queryChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if USER_LIMIT:
		count = calcStats()[0]
		if count >= USER_LIMIT and not source in Transport:
			cl.send(utils.buildIQError(iq, xmpp.ERR_NOT_ALLOWED, _("Transport's admins limited registrations, sorry.")))
			raise xmpp.NodeProcessed()

	if destination == TransportID:
		if iType == "get" and not queryChildren:
			logger.debug("Send registration form to user (jid: %s)" % source)
			form = utils.buildDataForm(fields = [
				{"var": "link", "type": "text-single", "label": _("Autorization page"),
					"desc": ("If you won't get access-token automatically, please, follow authorization link and authorize app,\n"\
						   "and then paste url to password field."), "value": URL_ACCEPT_APP},
				{"var": "phone", "type": "text-single", "desc": _("Enter phone number in format +71234567890"), "value": "+"},
				{"var": "use_password", "type": "boolean", "label": _("Get access-token automatically"), "desc": _("Try to get access-token automatically. (NOT recommended, password required!)")}, #"value": "0"},#, "0"}
				{"var": "password", "type": "text-private", "label": _("Password/Access-token"), "desc": _("Type password, access-token or url (recommended)")}],
			data = [_("Type data in fields")])
			result.setQueryPayload([form])

		elif iType == "set" and queryChildren:
			phone, password, use_password, token = False, False, False, False #?
			query = iq.getTag("query")
			data = query.getTag("x", namespace=xmpp.NS_DATA)
			if data:
				form = xmpp.DataForm(node=data).asDict()
				phone = form.get("phone", "")
				password = form.get("password", "")
				use_password = utils.normalizeValue(form.get("use_password", ""))

				if not password:
					result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Empty password/token field"))

	## Some clients send "true" or "false" instead of 1/0
				user = User(source=source)
				use_password = int(use_password)


	## If user won't use password so we need token
				if not use_password:
					logger.debug("user won't use a password (jid: %s)" % source)
					token = password
					password = False
				else:
					logger.debug("user want to use a password (jid: %s)" % source)
					if not phone:
						result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Phone incorrect."))
					user.password = password
					user.username = phone
		
	## Check if user already registered. If registered, delete him then
				if source in Transport:
					user = Transport[source]
					removeUser(user, semph=False, notify=False)

	## If we not using a password so we need to check if there a link or token. Or maybe user's wrong and that's his password.
				if not use_password:
					_token = api.token_exp.search(token)
					if _token:
						_token = _token.group(0)
						user.token = _token
					else:
						user.password = token
						user.username = phone
					
		## Check if all data is correct.
				runThread(initializeUser, (user, cl, iq))
				result = None

			elif query.getTag("remove"):
				logger.debug("user %s want to remove me..." % source)
				if source in Transport:
					user = Transport[source]
					removeUser(user, True, False)
					result.setPayload([], add = 0)
					watcherMsg(_("User has removed registration: %s") % source)
				else:
					logger.debug("... but he don't know that he was removed already!")

		else:
			result = utils.buildIQError(iq, 0, _("Feature not implemented."))
	if result: sender(cl, result)

def load():
	Component.RegisterHandler("iq", register_handler, "", xmpp.NS_REGISTER)
