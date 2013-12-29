# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

import urllib

def parseAttachments(self, msg):
	result = ""
	if msg.has_key("attachments"):
		if msg["body"]:
			result += _("\nAttachments:")
		searchlink = "https://vk.com/search?c[q]=%s&c[section]=audio"
		attachments = msg["attachments"]
		for att in attachments:
			body = ""
			key = att.get("type")
			if key == "wall":
				body += "\nWall: https://vk.com/feed?w=wall%(to_id)s_%(id)s"
			elif key == "photo":
				keys = ("src_xxxbig", "src_xxbig", "src_xbig", "src_big", "src", "url", "src_small")
				for dKey in keys:
					if att[key].has_key(dKey):
						body += "\n" + att[key][dKey]
						break
			elif key == "video":
				body += "\nVideo: http://vk.com/video%(owner_id)s_%(vid)s — %(title)s"
			elif key == "audio":
				url = searchlink % urllib.quote(str("%(performer)s %(title)s" % att[key]))
				att[key]["url"] = url
				body += "\nAudio: %(performer)s — %(title)s — %(url)s"
			elif key == "doc":
				body += "\nDocument: %(title)s — %(url)s"
			else:
				body += "\nUnknown attachment: " + str(att[key])
			result += body % att.get(key, {})
	return result

Handlers["msg01"].append(parseAttachments)