# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *
from __main__ import _
import forms


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
			user.initialize(resource=resource)
			executeHandlers("evt08", (source,))
		else:
			logger.error("user connection failed (jid: %s)" % source)
			result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
	sender(cl, result)


@utils.safe
def register_handler(cl, iq):
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	result = iq.buildReply("result")
	if USER_LIMIT:
		count = calcStats()[0]
		if count >= USER_LIMIT and source not in Users:
			sender(cl, utils.buildIQError(iq, xmpp.ERR_NOT_ALLOWED, _("The gateway admins limited registrations, sorry.")))
			raise xmpp.NodeProcessed()

	if destination == TransportID and iq.getQueryChildren():
		phone, password, use_password, token, result = None, None, None, None, None
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
					password = None
					# If not using a password, then we need to check if there a link or token. It's possible that user's wrong and that's a password.
					match = api.token_exp.search(token)
					if match:
						token = match.group(0)
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
			if source in Users:
				user = Transport[source]
				result = iq.buildReply("result")
				result.setPayload([], add=False)
				executeHandlers("evt09", (source,))

			elif findUserInDB(source):
				removeUser(source, True, False)
				sendPresence(TransportID, destination, "unsubscribe")
				executeHandlers("evt09", (source,))
	if result:
		sender(cl, result)


def sendRegisterForm(cl, iq):
	logger.debug("Send registration form to user (jid: %s)", iq.getFrom().getStripped())
	form = utils.buildDataForm(fields=forms.Forms.getComlicatedForm(), data=[_("Fill the fields below")])
	result = iq.buildReply("result")
	result.setQueryPayload([form])
	sender(cl, result)


MOD_TYPE = "iq"
MOD_FEATURES = [xmpp.NS_DATA, xmpp.NS_REGISTER]
MOD_HANDLERS = ((register_handler, "set", xmpp.NS_REGISTER, False), (sendRegisterForm, "get", xmpp.NS_REGISTER, False))
