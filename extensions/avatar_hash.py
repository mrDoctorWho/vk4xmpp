# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 14:58PM GMT)

ENABLE_PHOTO_HASHES = False

def makePhotoHash(user, list=None):
	"""
	Makes sha1 photo hash
	Parameters:
		list is a list of user ids to make hash from
	"""

	if not list:
		list = user.vk.method("friends.getOnline")
		user.hashes = {}
		photos = [{"uid": TransportID, "photo": URL_VCARD_NO_IMAGE}]
	else:
		photos = []

	list = ",".join((str(x) for x in list))
	data = user.vk.method("execute.getPhotos", {"users": list, "size": PhotoSize}) or []
	photos = photos + data

	for key in photos:
		user.hashes[key["uid"]] = sha1(utils.getLinkData(key["photo"], False)).hexdigest()
 

def addPresenceHash(prs, destination, source):
 	uid = vk2xmpp(uid)
 	user = Transport[source]
 	if not uid in user.hashes:
		runThread(makePhotoHash, (user, [uid])) # To prevent blocking here (if VK will not answer, he can, trust me)
	hash = user.hashes.get(uid)
 	if hash:
		x = prs.setTag("x", namespace=xmpp.NS_VCARD_UPDATE)
		x.setTagData("photo", hash)


if ENABLE_PHOTO_HASHES:
	registerHandler("evt05", makePhotoHash)
	registerHandler("prs02", addPresenceHash)