# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *
from __main__ import _


@utils.threaded
def initializeUser(user, cl, iq, kwargs):
	result = iq.buildReply("result")
	connect = False
	resource = iq.getFrom().getResource()
	source = user.source
	try:
		connect = user.connect(**kwargs)
	except (api.TokenError, api.AuthError) as e:
		result = utils.buildIQError(iq, xmpp.ERR_NOT_AUTHORIZED, _(str(e) + " Try logging in by token."))
	else:
		if connect:
			try:
				user.initialize(resource=resource)
			except api.CaptchaNeeded:
				user.vk.captchaChallenge()
			except Exception:
				crashLog("user.init")
				result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
			else:
				executeHandlers("evt08", (source,))
		else:
			logger.error("user connection failed (jid: %s)" % source)
			result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
	sender(cl, result)


import forms

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
			sender(cl, utils.buildIQError(iq, xmpp.ERR_NOT_ALLOWED, _("Transport's admins limited registrations, sorry.")))
			raise xmpp.NodeProcessed()

	if destination == TransportID:
		if iType == "get" and not queryChildren:
			logger.debug("Send registration form to user (jid: %s)", source)
			form = utils.buildDataForm(fields=forms.Forms.getComlicatedForm(), data=[_("Fill the fields below")])
			result.setQueryPayload([form])

		elif iType == "set" and queryChildren:
			phone, password, use_password, token, result = False, False, False, False, False # Why result is here?
			query = iq.getTag("query")
			data = query.getTag("x", namespace=xmpp.NS_DATA)
			if data:
				form = xmpp.DataForm(node=data).asDict()
				phone = str(form.get("phone", "")).lstrip("+")
				password = str(form.get("password", ""))
				use_password = utils.normalizeValue(form.get("use_password", ""))  # In case here comes some unknown crap

				if not password:
					result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("The token/password field can't be empty!"))
				else:
					if use_password:
						logger.debug("user want to use a password (jid: %s)" % source)
						if not phone or phone == "+":
							result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Phone is incorrect."))
					else:
						logger.debug("user won't use a password (jid: %s)" % source)
						token = password
						password = False
				
						## If not using a password, then we need to check if there a link or token. It's possible that user's wrong and that's a password.
						_token = api.token_exp.search(token)
						if _token:
							token = _token.group(0)
						elif phone:
							password = token
						else:
							result = utils.buildIQError(iq, xmpp.ERR_NOT_AUTHORIZED, _("Fill the fields!"))

					# If phone or password (token)
					if token or (phone and password):
						user = User(source)
						initializeUser(user, cl, iq, {"username": phone, "password": password, "token": token})
						result = None

			elif query.getTag("remove"):
				logger.debug("user %s want to remove me..." % source)
				if source in Transport:
					user = Transport[source]
					removeUser(user, True, False)
					result = iq.buildReply("result") # Is it required?
					result.setPayload([], add=False)
					executeHandlers("evt09", (source,))
				else:
					logger.debug("... but they don't know that they were removed already!")

		else:
			result = utils.buildIQError(iq, 0, _("Feature not implemented."))
	if result:
		sender(cl, result)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_DATA, xmpp.NS_REGISTER]
MOD_HANDLERS = ((register_handler, "", xmpp.NS_REGISTER, False),)
