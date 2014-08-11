# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.
## TODO: Handle set/get in separate functions.

from __main__ import *
from __main__ import _

URL_ACCEPT_APP = "http://simpleapps.ru/vk4xmpp.html"


def initializeUser(user, cl, iq):
	source = user.source
	result = iq.buildReply("result")
	if not user.connect():
		logger.error("user connection failed (jid: %s)" % source)
		result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
	else:
		try:
			user.initialize()
		except api.CaptchaNeeded:
			user.vk.captchaChallenge()
		except Exception:
			crashLog("user.init")
			result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
		else:
			Transport[source] = user
			watcherMsg(_("New user registered: %s") % source)
	sender(cl, result)

def register_handler(cl, iq):
	jidTo = iq.getTo()
	jidFrom = iq.getFrom()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	iType = iq.getType()
	queryChildren = iq.getqueryChildren()
	result = iq.buildReply("result")
	if USER_LIMIT:
		count = calcStats()[0]
		if count >= USER_LIMIT and not source in Transport:
			cl.send(utils.buildIQError(iq, xmpp.ERR_NOT_ALLOWED, _("Transport's admins limited registrations, sorry.")))
			raise xmpp.NodeProcessed()

	if destination == TransportID:
		if iType == "get" and not queryChildren:
			logger.debug("Sending register form to user (jid: %s)" % source)
			form = xmpp.DataForm()
			form.addChild(node=xmpp.Node("instructions")).setData(_("Type data in fields")) ## TODO: Complete this by forms
			link = form.setField("link", URL_ACCEPT_APP, "text-single")
			link.setLabel(_("Autorization page"))
			link.setDesc(_("If you won't get access-token automatically, please, follow authorization link and authorize app,\n"\
						   "and then paste url to password field."))
			phone = form.setField("phone", "+", "text-single")
			phone.setLabel(_("Phone number"))
			phone.setDesc(_("Enter phone number in format +71234567890"))
			use_password = form.setField("use_password", "0", "boolean")
			use_password.setLabel(_("Get access-token automatically"))
			use_password.setDesc(_("Try to get access-token automatically. (NOT recommended, password required!)"))
			password = form.setField("password", None, "text-private")
			password.setLabel(_("Password/Access-token"))
			password.setDesc(_("Type password, access-token or url (recommended)"))
			result.setqueryPayload((form,))

		elif iType == "set" and queryChildren:
			phone, password, use_password, token = False, False, False, False
			query = iq.getTag("query")
			if query.getTag("x"):
				for node in iq.getTags("query", namespace=xmpp.NS_REGISTER):
					for node in node.getTags("x", namespace=xmpp.NS_DATA):
						phone = node.getTag("field", {"var": "phone"})
						phone = phone and phone.getTagData("value")
						password = node.getTag("field", {"var": "password"})
						password = password and password.getTagData("value")
						use_password = node.getTag("field", {"var": "use_password"})
						use_password = use_password and use_password.getTagData("value")

				if not password:
					result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Empty password"))

	## Some clients send "true" or "false" instead of 1/0
				if not isNumber(use_password):
					if use_password and use_password.lower() == "true":
						use_password = 1
					else:
						usd_password = 0

				user = User(source=source)
				use_password = int(use_password)


	## If user won't use password so we need token
				if not use_password:
					logger.debug("user %s won't use password" % source)
					token = password
					password = False
				else:
					logger.debug("user %s wants use password" % source)
					if not phone:
						result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Phone incorrect."))
					user.password = password
					user.username = phone
		
	## Check if user already registered. If registered, delete him then
				if source in Transport:
					user = Transport[source]
					removeUser(user, semph=False)

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
				logger.debug("... but he don't know that he is removed already!")

		else:
			result = utils.buildIQError(iq, 0, _("Feature not implemented."))
	if result: sender(cl, result) 

def load():
	Component.RegisterHandler("iq", register_handler, "", xmpp.NS_REGISTER)
 