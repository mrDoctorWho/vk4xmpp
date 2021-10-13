# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2016.

from __main__ import *
from __main__ import _

VCARD_SEMAPHORE = threading.Semaphore()

DESCRIPTION = "VK4XMPP Transport\n© simpleApps, 2013 — 2016."
GITHUB_URL = "https://github.com/mrDoctorWho/vk4xmpp"
BIRTHDAY = "30.08.2013"

KEY_NICKNAME = "NICKNAME"
KEY_NAME = "FN"
KEY_DESC = "DESC"
KEY_PHOTO = "PHOTO"
KEY_BINVAL = "BINVAL"
KEY_URL = "URL"
KEY_ADR = "ADR"
KEY_HOME = "HOME"
KEY_BDAY = "BDAY"
KEY_CTRY = "CTRY"
KEY_PHONE_HOME = "HOME"
KEY_PHONE_MOBILE = "MOBILE"
KEY_TEL = "TEL"
KEY_NUMBER = "NUMBER"
KEY_VOICE = "VOICE"
KEY_LOCALITY = "LOCALITY"

if AdditionalAbout:
	DESCRIPTION = "%s\n%s" % (DESCRIPTION, AdditionalAbout)


# Vcard defaults
VCARD_TEMPLATE = {KEY_NICKNAME: IDENTIFIER["short"],
	KEY_NAME: IDENTIFIER["name"],
	KEY_DESC: DESCRIPTION,
	KEY_PHOTO: URL_VCARD_NO_IMAGE,
	KEY_URL: GITHUB_URL,
	KEY_BDAY: BIRTHDAY,
	KEY_CTRY: "United States",  # database.getCountriesById and database.getCitiesById
	KEY_PHONE_HOME: None,
	KEY_PHONE_MOBILE: None,
	KEY_LOCALITY: {"title": "Los Angeles"}  # you'd love it here (yeah, here...)
	}


VCARD_FIELDS = {KEY_NICKNAME: "screen_name",
				KEY_NAME: "name",
				KEY_URL: "https://vk.com/id%(id)s",
				KEY_BDAY: "bdate",
				KEY_CTRY: "country",
				KEY_LOCALITY: "city",
				KEY_PHONE_HOME: "home_phone",
				KEY_PHONE_MOBILE: "mobile_phone",
				KEY_URL: "site",
				KEY_PHOTO: PhotoSize,
				KEY_DESC: None,
				}


def buildVcard(data, template=VCARD_TEMPLATE, fields=VCARD_FIELDS, user=None):
	"""
	Builds a vcard.
	Uses VCARD_TEMPLATE as the base, then adds values from data.
	Values from data are get with the help of the VCARD_FIELDS dict.
	Args:
		data: users.get result
		user: the user object
	Returns:
		The user's VCARD.
	"""
	vcard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key, value in template.iteritems():
		value = data.get(fields[key], value)
		if key == KEY_PHOTO:
			photo = vcard.setTag(KEY_PHOTO)
			photo.setTagData(KEY_BINVAL, utils.getLinkData(value))

		elif key in (KEY_CTRY, KEY_LOCALITY) and value:
			adr = vcard.getTag(KEY_ADR) or vcard.setTag(KEY_ADR)
			adr.setTagData(key, value.get("title"))

		elif key == KEY_PHONE_MOBILE and value:
			tel = vcard.getTag(KEY_TEL) or vcard.setTag(KEY_TEL)
			tel.setTagData(KEY_NUMBER, value)

		elif key == KEY_PHONE_HOME and value:
			tel = vcard.getTag(KEY_TEL) or vcard.setTag(KEY_TEL)
			tel.setTagData(KEY_PHONE_HOME, value)

		elif key == KEY_BDAY and value:
			if value.count(".") == 1:
				value += time.strftime(".%Y")
			value = time.strftime("%Y-%m-%d", time.strptime(value, "%d.%m.%Y"))
			vcard.setTagData(key, value)

		elif value and value != "None":
			vcard.setTagData(key, value)
	return vcard


@utils.threaded
def vcard_handler(cl, iq):
	# Vcard feature makes transport hang (especially the photo part)
	# Many clients love to query vcards so much, so the solution was in adding a semaphore here and sleep() at the bottom
	# This is probably not a good idea, but for now this is the best one
	with VCARD_SEMAPHORE:
		jidFrom = iq.getFrom()
		jidTo = iq.getTo()
		source = jidFrom.getStripped()
		destination = jidTo.getStripped()
		result = iq.buildReply("result")

		logger.debug("got vcard request to %s (jid: %s)", destination, source)
		if destination == TransportID:
			template = VCARD_TEMPLATE.copy()
			vcard = buildVcard(template, template, template)
			result.setPayload([vcard])

		elif source in Users:
			user = Users[source]
			if user.friends:
				id = vk2xmpp(destination)
				args = ("screen_name", "bdate", "city", "country", "contacts", "home_town", "site", PhotoSize)  # todo: a feature to show the user's site instead of their URL?
				data = user.vk.getData(id, args)
				data["id"] = id
				if not user.settings.use_nicknames:
					data["screen_name"] = data["name"]
				vCard = buildVcard(data, VCARD_TEMPLATE, VCARD_FIELDS, user)
				result.setPayload([vCard])
			else:
				result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is empty."))
		else:
			result = utils.buildIQError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
		sender(cl, result)


MOD_TYPE = "iq"
MOD_HANDLERS = ((vcard_handler, "get", xmpp.NS_VCARD, False),)
MOD_FEATURES = [xmpp.NS_VCARD]
