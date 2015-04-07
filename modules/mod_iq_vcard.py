# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from __main__ import *
from __main__ import _

del Semaphore
Semaphore = threading.Semaphore()


def buildVcard(tags):
	vCard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			photo = vCard.setTag("PHOTO")
			photo.setTagData("BINVAL", utils.getLinkData(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard


def vcard_handler_threaded(cl, iq):
	# Vcard feature makes transport hang (especially the photo part)
	# Many clients love to query vcards so much, so the solution was in adding a semaphore and sleep() here
	# This is probably not a good idea, but for now this is the best one
	with Semaphore:
		jidFrom = iq.getFrom()
		jidTo = iq.getTo()
		source = jidFrom.getStripped()
		destination = jidTo.getStripped()
		result = iq.buildReply("result")
		_DESC = str.join(chr(10), (DESC, "_" * 16, AdditionalAbout)) if AdditionalAbout else DESC
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
				args = ["screen_name"]
				if user.friends.has_key(id):
					args.append(PhotoSize)
				json = user.vk.getUserData(id, args)
				name = json.get("name", str(json))
				screen_name = json.get("screen_name", str(json))
				values = {"NICKNAME": screen_name,
						"FN": name,
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
		time.sleep(1.5)


def vcard_handler(cl, iq):
	runThread(vcard_handler_threaded, (cl, iq))


def load():
	TransportFeatures.add(xmpp.NS_VCARD)
	Component.RegisterHandler("iq", vcard_handler, "get", xmpp.NS_VCARD)


def unload():
	TransportFeatures.remove(xmpp.NS_VCARD)
	Component.UnregisterHandler("iq", vcard_handler, "get", xmpp.NS_VCARD)