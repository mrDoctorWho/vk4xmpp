# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

import urllib

VK_AUDIO_SEARCH = "https://vk.com/search?c[q]=%s&c[section]=audio"

def parseAttachments(self, msg, spacer=""):
	result = ""
	if msg.has_key("attachments"):

## Add new line and "Attachments"
		if msg["body"]:
			result += chr(10) + spacer + _("Attachments:") + chr(10)

		attachments = msg["attachments"]
		for num, att in enumerate(attachments):
			typ = att.get("type")
			body = spacer
			if num:
				body = chr(10) + spacer

			if typ == "wall":
				body += "Wall: https://vk.com/feed?w=wall%(to_id)s_%(id)s"

			elif typ == "photo":
				keys = ("src_xxxbig", "src_xxbig", "src_xbig", "src_big", "src", "url", "src_small")
				for key in keys:
					if key in att[typ]:
						body += att[typ][key] ## No new line needed if we have just one photo and no text
						break

			elif typ == "video":
				body += "Video: http://vk.com/video%(owner_id)s_%(vid)s — %(title)s"

			elif typ == "audio":
				for key in ("performer", "title"):
					if att[typ].has_key(key):
						att[typ][key] = uHTML(att[typ][key])

				url = VK_AUDIO_SEARCH % urllib.quote(str("%(performer)s %(title)s" % att[typ]))
				att[typ]["url"] = url
				body += "Audio: %(performer)s — %(title)s — %(url)s"

			elif typ == "doc":
				body += "Document: %(title)s — %(url)s"

			elif typ == "sticker":
				keys = ("photo_256", "photo_128", "photo_64")
				for key in keys:
					if key in att[typ]:
						body += "Sticker: " + att[typ][key]
						break

			else:
				body += "Unknown attachment: " + str(att[typ])
			result += body % att.get(typ, {})
	return result

registerHandler("msg01", parseAttachments)
