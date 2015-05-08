# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *
from __main__ import _

VCARD_SEMAPHORE = threading.Semaphore()

DESCRIPTION = "VK4XMPP Transport\n© simpleApps, 2013 — 2015."
GITHUB_URL = "https://github.com/mrDoctorWho/vk4xmpp"

if AdditionalAbout:
	DESCRIPTION = "%s\n%s" % (DESCRIPTION, AdditionalAbout)

VCARD_FIELDS = {"NICKNAME": IDENTIFIER["name"],
	"DESC": DESCRIPTION,
	"PHOTO": URL_VCARD_NO_IMAGE,
	"URL": GITHUB_URL}

def buildVcard(tags):
	vCard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			photo = vCard.setTag("PHOTO")
			photo.setTagData("BINVAL", utils.getLinkData(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard


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
			vcard = buildVcard(VCARD_FIELDS)
			result.setPayload([vcard])

		elif source in Transport:
			user = Transport[source]
			if user.friends:
				id = vk2xmpp(destination)
				args = ["screen_name"]
				values = VCARD_FIELDS.copy()
				if id in user.friends.keys():
					args.append(PhotoSize)
				data = user.vk.getUserData(id, args)
				name = data.get("name", str(data))
				screen_name = data.get("screen_name")
				if not user.settings.use_nicknames:
					screen_name = name
				values["NICKNAME"] = screen_name
				values["FN"] = name
				values["URL"] = "http://vk.com/id%s" % id
				if id in user.friends.keys():
					values["PHOTO"] = data.get(PhotoSize) or URL_VCARD_NO_IMAGE
				vCard = buildVcard(values)
				result.setPayload([vCard])
			else:
				result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is empty."))
		else:
			result = utils.buildIQError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
		sender(cl, result)
		time.sleep(1.5)


MOD_TYPE = "iq"
MOD_HANDLERS = ((vcard_handler, "get", xmpp.NS_VCARD, False),)
MOD_FEATURES = [xmpp.NS_VCARD]