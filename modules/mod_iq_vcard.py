# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

from __main__ import *
from __main__ import _

def buildVcard(tags):
	vCard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			photo = vCard.setTag("PHOTO")
			photo.setTagData("BINVAL", utils.getLinkData(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard

def vcard_handler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	result = iq.buildReply("result")
	_DESC = '\n'.join((DESC, "_" * 16, AdditionalAbout)) if AdditionalAbout else DESC
	if destination == TransportID:
		vcard = buildVcard({"NICKNAME": "VK4XMPP Transport",
							"DESC": _DESC,
							"PHOTO": "https://raw.github.com/mrDoctorWho/vk4xmpp/master/vk4xmpp.png",
							"URL": "http://simpleapps.ru"
							})
		result.setPayload([vcard])

	elif source in Transport:
		user = Transport[source]
		if user.friends:
			id = vk2xmpp(destination)
			json = user.vk.getUserData(id, ["screen_name", PhotoSize])
			values = {"NICKNAME": json.get("name", str(json)),
					"URL": "http://vk.com/id%s" % id,
					"DESC": _("Contact uses VK4XMPP Transport\n%s") % _DESC
					}
			if id in user.friends.keys():
				values["PHOTO"] = json.get(PhotoSize) or URL_VCARD_NO_IMAGE
			vCard = buildVcard(values)
			result.setPayload([vCard])
		else:
			result = utils.buildIQError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is empty."))
	else:
		result = utils.buildIQError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
	sender(cl, result)


def load():
	Component.RegisterHandler("iq", vcard_handler, "get", xmpp.NS_VCARD)