# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 14:58PM GMT) — 2015.

from hashlib import sha1

"""
Implements XEP-0153: vCard-Based Avatars
"""

def makePhotoHash(user, list=None):
	"""
	Makes sha1 photo hash
	Parameters:
		list is a list of user ids to make hash from
	"""
	list = list or []
	if not hasattr(user, "hashes"):
		user.hashes = {}
	if user.settings.avatar_hash:
		photos = []
		if not list:
			list = user.friends.keys()
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
			x = prs.setTag("x", namespace=xmpp.NS_VCARD_UPDATE)
		 	uid = vk2xmpp(source)
		 	user = Transport[destination]
		 	hashes = getattr(user, "hashes", {})
		 	hash = hashes.get(uid)
		 	if hash:
				x.setTagData("photo", hash)
			else:
				utils.runThread(makePhotoHash, (user, [uid] if hashes else []))


if isdef("ENABLE_PHOTO_HASHES") and ENABLE_PHOTO_HASHES:
	GLOBAL_USER_SETTINGS["avatar_hash"] = {"label": "Show my friends avatars", "value": 1}
	logger.debug("extension avatar_hash is loaded")
	registerHandler("evt05", makePhotoHash)
	registerHandler("prs02", addPresenceHash)

else:
	del makePhotoHash, addPresenceHash