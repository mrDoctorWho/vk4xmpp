# coding: utf
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

def parseAttachments(self, msg):
	body = str()
	if msg.has_key("attachments"):
		if msg["body"]:
			body += _("\nAttachments:")
		attachments = msg["attachments"]
		for att in attachments:
			key = att.get("type")
			if key == "wall":
				continue	
			elif key == "photo":
				keys = ("src_big", "url", "src_xxxbig", "src_xxbig", "src_xbig", "src", "src_small")
				for dKey in keys:
					if att[key].has_key(dKey):
						body += "\n" + att[key][dKey]
						break
			elif key == "video":
				body += "\nVideo: http://vk.com/video%(owner_id)s_%(vid)s — %(title)s"
			elif key == "audio":
				body += "\nAudio: %(performer)s — %(title)s — %(url)s"
			elif key == "doc":
				body += "\nDocument: %(title)s — %(url)s"
			else:
				body += "\nUnknown attachment: " + str(att[key])
			body = body % att.get(key, {})
	return body

Handlers["msg01"].append(parseAttachments)