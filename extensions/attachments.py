# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

import urllib

VK_AUDIO_SEARCH = "https://vk.com/search?c[q]=%s&c[section]=audio"

GLOBAL_USER_SETTINGS["parse_wall"] = {"value": 0, "label": "Parse wall attachments"}


def parseAttachments(self, msg, spacer=""):
	"""
	“parses” attachments from the json to a string
	"""
	result = ""
	if msg.has_key("attachments"):
		attachments = msg["attachments"]
		# Add new line and "Attachments" if there some text added
		if msg.get("body") and len(attachments) > 1:
			result += chr(10) + spacer + _("Attachments:")
		if spacer:
			result += "\n"
		if not spacer and msg.get("body"):
			result += "\n"

		for num, attachment in enumerate(attachments):
			body = spacer
			type = attachment.get("type")
			current = attachment[type]
			if num > 0:
				body = chr(10) + spacer

			if type == "wall":
				if self.settings.parse_wall:
					body += "Wall post"
					# TODO: Rewrite me
					if current.get("to_id", 0) < 0:
						name = self.vk.method("groups.getById", {"group_id": abs(current.get("to_id", 0)), "fields": "name"})
						if name:
							name = name[0].get("name")
							body += " in community “%s”:" % name
					body += "\n"
					if current.get("text"):
						body += spacer + uhtml(compile_eol.sub("\n" + spacer, current["text"])) + "\n"
					body += spacer + parseAttachments(self, current, spacer) + "\n" + spacer + "\n"
				body += spacer + ("Wall: https://vk.com/feed?w=wall%(to_id)s_%(id)s" % current)

			elif type == "photo":
				keys = ("src_xxxbig", "src_xxbig", "src_xbig", "src_big", "src", "url", "src_small")
				for key in keys:
					if key in current:
						body += "Photo: %s" % current[key]  # No new line needed if we have just one photo and no text
						break

			elif type == "video":
				body += "Video: %(title)s — https://vk.com/video%(owner_id)s_%(vid)s" % current

			elif type == "audio":
				for key in ("performer", "title"):
					if current.has_key(key):
						current[key] = uhtml(current[key])

				current["url"] = VK_AUDIO_SEARCH % urllib.quote(str("%(performer)s %(title)s" % current))
				body += "Audio: %(performer)s — “%(title)s“ — %(url)s" % current

			elif type == "doc":
				body += "Document: “%(title)s” — %(url)s" % current

			elif type == "sticker":
				keys = ("photo_256", "photo_128", "photo_64")
				for key in keys:
					if key in current:
						body += "Sticker: %s" % current[key]
						break

			elif type == "page":
				body += "Page: %(view_url)s — %(title)s" % current

			elif type == "link":
				body += "URL: %(url)s — %(title)s" % current

			elif type == "poll":
				body += "Poll: %(question)s" % current

			elif type == "wall_reply":
				current["name"] = self.vk.getUserData(current["uid"])["name"]
				current["text"] = uhtml(compile_eol.sub("\n" + spacer, current["text"]))
				current["url"] = "https://vk.com/feed?w=wall%(owner_id)s_%(post_id)s" % current
				body += "Commentary to the post on a community wall:\n"
				body += spacer + "<%(name)s> %(text)s\n" % current
				body += spacer + "Community: %(url)s" % current

			else:
				body += "Unknown attachment: %s\n%s" % (type, str(current))
			result += body
	return result

registerHandler("msg01", parseAttachments)