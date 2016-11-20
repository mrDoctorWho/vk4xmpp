# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2016.

from __main__ import *
from __main__ import _

VCARD_SEMAPHORE = threading.Semaphore()

DESCRIPTION = "VK4XMPP Transport\n© simpleApps, 2013 — 2016."
GITHUB_URL = "https://github.com/mrDoctorWho/vk4xmpp"

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
KEY_PHONE_HOME = "PHONE_HOME"
KEY_PHONE_MOBILE = "PHONE_MOBILE"
KEY_TEL = "TEL"
KEY_NUMBER = "NUMBER"
KEY_VOICE = "VOICE"
KEY_LOCALITY = "LOCALITY"

if AdditionalAbout:
	DESCRIPTION = "%s\n%s" % (DESCRIPTION, AdditionalAbout)

VCARD_TEMPLATE = {KEY_NICKNAME: IDENTIFIER["name"],
	KEY_NAME: "Unknown",
	KEY_DESC: DESCRIPTION,
	KEY_PHOTO: URL_VCARD_NO_IMAGE,
	KEY_URL: GITHUB_URL,
	KEY_BDAY: None,
	KEY_CTRY: "United States",  # database.getCountriesById and database.getCitiesById
	KEY_PHONE_HOME: None,
	KEY_PHONE_MOBILE: None,
	}



VCARD_FIELDS = {KEY_NICKNAME: "screen_name",
				KEY_NAME: "name",
				KEY_URL: "https://vk.com/id%(id)s",
				KEY_BDAY: "bdate",
				KEY_CTRY: "country",
				KEY_LOCALITY: "home_town",
				KEY_PHONE_HOME: "home_phone",
				KEY_PHONE_MOBILE: "home_mobile",
#				KEY_URL: "site",
				KEY_PHOTO: PhotoSize,
				KEY_DESC: None,
				}


def buildVcard(data):
	"""
	Builds a vcard.
	Uses VCARD_TEMPLATE as the base, then adds values from data.
	Values from data are get with the help of the VCARD_FIELDS dict.
	Args:
		data: users.get result
	Returns:
		A user's VCARD.
	"""
	vcard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key, value in VCARD_TEMPLATE.iteritems():
		value = data.get(VCARD_FIELDS[key], value)
		if key == KEY_PHOTO:
			photo = vcard.setTag(KEY_PHOTO)
			photo.setTagData(KEY_BINVAL, utils.getLinkData(value))
		# todo: find a proper way to handle this
		elif key == KEY_URL:
			vcard.setTagData(key, VCARD_FIELDS[key] % data)
		elif key in (KEY_CTRY, KEY_LOCALITY) and value:
			adr = vcard.getTag(KEY_ADR) or vcard.setTag(KEY_ADR)
			if key == KEY_CTRY:
				adr.setTagData(KEY_CTRY, value)
			elif key == KEY_LOCALITY:
				adr.setTagData(KEY_LOCALITY, value)
		elif key in (KEY_PHONE_HOME, KEY_PHONE_MOBILE) and value:
			tel = vcard.getTag(KEY_TEL) or vcard.setTag(KEY_TEL)
			if key == KEY_PHONE_HOME:
				tel.setTagData(KEY_HOME, value)
			elif key == KEY_PHONE_MOBILE:
				tel.setTagData(KEY_NUMBER, value)
		elif value:
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

		if destination == TransportID:
			vcard = buildVcard(VCARD_TEMPLATE)
			result.setPayload([vcard])

		elif source in Transport:
			user = Transport[source]
			if user.friends:
				id = vk2xmpp(destination)
				args = ["screen_name", "bdate", "city", "country", "contacts", "home_town", PhotoSize]  # todo: a feature to show the user's site instead of their URL?
				data = user.vk.getUserData(id, args)
				data["id"] = id
				if not user.settings.use_nicknames:
					data["screen_name"] = data["name"]
				vCard = buildVcard(data)
				result.setPayload([vCard])
			else:
				result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is empty."))
		else:
			result = utils.buildIQError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
		sender(cl, result)


MOD_TYPE = "iq"
MOD_HANDLERS = ((vcard_handler, "get", xmpp.NS_VCARD, False),)
MOD_FEATURES = [xmpp.NS_VCARD]