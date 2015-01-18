# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 14:58PM GMT) — 2015.

from hashlib import sha1

try:
	ENABLE_PHOTO_HASHES is False
except NameError:
	ENABLE_PHOTO_HASHES = False

GLOBAL_USER_SETTINGS["avatar_hash"] = {"label": "Show my friends avatars", "value": 1}


def makePhotoHash(user, list=None):
	"""
	Makes sha1 photo hash
	Parameters:
		list is a list of user ids to make hash from
	"""
	if user.settings.avatar_hash:
		photos = []
		if not list:
			list = user.vk.method("friends.getOnline")
			user.hashes = {}

		if TransportID in list:
			list.remove(TransportID)

		if list:
			list = ",".join((str(x) for x in list))
			data = user.vk.method("execute.getPhotos", {"users": list, "size": PhotoSize}) or []
			photos = photos + data

		photos.append({"uid": TransportID, "photo": URL_VCARD_NO_IMAGE})

		for key in photos:
			user.hashes[key["uid"]] = sha1(utils.getLinkData(key["photo"], False)).hexdigest()

def addPresenceHash(prs, destination, source):
	if destination in Transport and not prs.getType():
		if Transport[destination].settings.avatar_hash:
		 	uid = vk2xmpp(source)
		 	user = Transport[destination]
		 	if not uid in user.hashes:
				runThread(makePhotoHash, (user, [uid])) # To prevent blocking here (if VK will not answer, its possible, trust me)
			hash = user.hashes.get(uid)
			x = prs.setTag("x", namespace=xmpp.NS_VCARD_UPDATE)
		 	if hash:
				x.setTagData("photo", hash)


if ENABLE_PHOTO_HASHES:
	logger.debug("extension avatar_hash is loaded")
	registerHandler("evt05", makePhotoHash)
	registerHandler("prs02", addPresenceHash)