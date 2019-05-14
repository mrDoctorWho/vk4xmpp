# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (30.08.14 14:58PM GMT) — 2015.

from hashlib import sha1

"""
Implements XEP-0153: vCard-Based Avatars
"""

class AvatarHash(object):
	def __init__(self):
		runDatabaseQuery("create table if not exists avatar_hash "
			"(id text unique, sha text, updated integer)", set=True)

		self.baseHash = self.hashPhotos([{"uid": TransportID, "photo": URL_VCARD_NO_IMAGE}])
		self.pending = set([])

	join = lambda uids: ",".join([str(uid) for uid in uids])
	join = staticmethod(join)

	def getLocalHashes(self, uids):
		data = runDatabaseQuery("select id, sha, updated from avatar_hash where id in (%s)" % self.join(uids)) or []
		result = {}
		for key in data:
			uid, (sha, updated) = int(key[0]), key[1:]
			if (time.time() - updated) >= PHOTO_LIFE_DURATION:  # Better to send something instead of nothing
				self.pending.add(uid)
			result[uid] = sha
		result.update(self.baseHash)
		return result

	def getPhotos(self, user, uids=None):
		length = len(uids)
		data = []
		if length > PHOTO_REQUEST_LIMIT:
			for i in xrange(0, length, PHOTO_REQUEST_LIMIT):
				current = uids[i:i+PHOTO_REQUEST_LIMIT]
				data += self.sendPhotoRequest(user, current)
		else:
			data = self.sendPhotoRequest(user, uids)
		return data

	def sendPhotoRequest(self, user, uids):
		data = user.vk.method("execute.getPhotos_new",
			{"users": self.join(uids), "size": PhotoSize}) or []
		return data

	def hashPhotos(self, photos):
		result = {}
		for key in photos:
			url, uid = key["photo"], key["uid"]
			result[uid] = sha1(utils.getLinkData(url, False)).hexdigest()
		return result

	def getHashes(self, user, uids):
		photos = self.getPhotos(user, uids)
		hashes = self.hashPhotos(photos)
		date = time.time()
		return (hashes, date)

	def makeHashes(self, user, uids=None):
		uids = uids or user.friends.keys()
		local = self.getLocalHashes(uids)
		if len(local) > 1:
			for uid in uids:
				if uid not in local:
					self.pending.add(uid)
		else:
			logger.debug("avatar_hash: updating hash database for user (jid: %s)", user.source)
			hashes, date = self.getHashes(user, uids)
			if hashes:
				sql = "insert into avatar_hash (id, sha, updated) values "
				for uid, value in hashes.iteritems():
					sql += "(%s, %s, %s)," % (uid, repr(value), date)
					local[uid] = value
				runDatabaseQuery(sql[:-1], set=True)
		local.update(self.baseHash)
		return local

	def updateHashes(self, user):
		hashes, date = self.getHashes(user, list(self.pending))
		for uid, hash in hashes.iteritems():
			runDatabaseQuery("update avatar_hash set sha=?, updated=? where id=?", (hash, date, uid), set=True)


def addPresenceHash(prs, destination, source):
	if destination in Users and not prs.getType():
		user = Users[destination]
		if user.settings.avatar_hash:
			x = prs.setTag("x", namespace=xmpp.NS_VCARD_UPDATE)
			uid = vk2xmpp(source)
			hashes = getattr(user, "hashes", {})
			if not hashes:
				user.hashes = hashes = Avatars.getLocalHashes(user.friends)
			hash = hashes.get(uid)
			if hash:
				x.setTagData("photo", hash)

@utils.threaded
def handleQueue():
	while ALIVE:
		if Queue:
			user = Queue.pop()
			user.hashes = Avatars.makeHashes(user)
			if Avatars.pending:
				utils.runThread(Avatars.updateHashes, (user,))
				Avatars.pending = set([])
		time.sleep(10)


def addUserToQueue(user):
	Queue.add(user)


if isdef("ENABLE_PHOTO_HASHES") and ENABLE_PHOTO_HASHES:
	if not isdef("PHOTO_REQUEST_LIMIT"):
		PHOTO_REQUEST_LIMIT = 280  # 280 folks
	if not isdef("PHOTO_LIFE_DURATION"):
		PHOTO_LIFE_DURATION = 604800  # 1 week
	Avatars = AvatarHash()
	Queue = set([])
	GLOBAL_USER_SETTINGS["avatar_hash"] = {"label": "Show my friends avatars", "value": 0}
	logger.debug("extension avatar_hash is loaded")
	registerHandler("evt01", handleQueue)
	registerHandler("evt05", addUserToQueue)
	registerHandler("prs02", addPresenceHash)

else:
	del AvatarHash, addPresenceHash, handleQueue, addUserToQueue
