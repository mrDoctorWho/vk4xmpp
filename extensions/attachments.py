# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2016.

import urllib
from printer import *

VK_AUDIO_SEARCH_LINK = "https://vk.com/search?c[q]=%s&c[section]=audio"
WALL_LINK = "https://vk.com/wall%(to_id)s_%(id)s"
WALL_COMMENT_LINK = "https://vk.com/wall%(owner_id)s_%(post_id)s?w=wall%(owner_id)s3_%(post_id)s"
PHOTO_SIZES = ("src_xxxbig", "src_xxbig", "src_xbig", "src_big", "src", "url", "src_small")
STICKER_SIZES = ("photo_256", "photo_128", "photo_64")

GLOBAL_USER_SETTINGS["parse_wall"] = {"value": 0, "label": "Parse wall attachments"}

# The attachments that don't require any special movements
SIMPLE_ATTACHMENTS = {"doc": "Document: “%(title)s” — %(url)s",
	"link": "URL: %(title)s — %(url)s",
	"poll": "Poll: %(question)s",
	"page": "Page: %(title)s — %(view_url)s"}


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
		elif msg.get("body"):
			result += "\n"

		for num, attachment in enumerate(attachments):
			body = spacer
			type = attachment.get("type")
			current = attachment[type]
			if num > 0:
				body = chr(10) + spacer

			if type == "wall":
				if self.settings.parse_wall:
					tid = current.get("to_id", 1)
					if tid > 0:
						name = "%s's" % self.vk.getUserData(tid)["name"]
					else:
						name = "“%s”" % self.vk.getGroupData(tid)["name"]
					body += "Post on %s wall:\n" % name
					if current.get("text") or current.get("copy_text"):
						body += spacer + uhtml(compile_eol.sub("\n" + spacer, current["text"] or current.get("copy_text"))) + "\n"
					if current.get("attachments"):
						body += spacer + parseAttachments(self, current, spacer) + "\n" + spacer + "\n"
				body += spacer + ("Wall: %s" % WALL_LINK % current)

			elif type == "photo":
				for key in PHOTO_SIZES:
					if key in current:
						body += "Photo: %s" % current[key]  # No new line needed if we have just one photo and no text
						break

			elif type == "audio":
				current["performer"] = uhtml(current.get("performer", ""))
				current["title"] = uhtml(current.get("title", ""))
				current["url"] = VK_AUDIO_SEARCH_LINK % urllib.quote(str("%(artist)s %(title)s" % current))
				current["time"] = current["duration"] / 60.0
				body += "Audio: %(artist)s — “%(title)s“ (%(time)s min) — %(url)s" % current

			elif type == "sticker":
				for key in STICKER_SIZES:
					if key in current:
						body += "Sticker: %s" % current[key]
						break

			elif type == "wall_reply":
				# TODO: What if it's a community? from_id will be negative.
				# TODO: Remove "[idxxx|Name]," from the text or make it a link if XHTML is allowed
				current["name"] = self.vk.getUserData(current["uid"])["name"]
				current["text"] = uhtml(compile_eol.sub("\n" + spacer, current["text"]))
				current["url"] = WALL_COMMENT_LINK % current

				body += "Commentary to the post on a wall:\n"
				body += spacer + "<%(name)s> %(text)s\n" % current
				body += spacer + "Post URL: %(url)s" % current

			elif type == "video":
				current["title"] = current.get("title", "Untitled")
				current["desc"] = ("(%(description)s, %(views)d views)" if current.get("description", "") == "" else "%(views)d views") % current
				current["type"] = "Live" if current.get("live", "") == "1" else "Video"

				# Question: maybe use "player" against videos page?
				current["url"] = "https://vk.com/video%(owner_id)s_%(id)s" % current
				current["time"] = "%d:%d" % (current["duration"] // 60, current["duration"] % 60)

				body += "%(type)s: %(title)s (%(desc)s, %(time)s) — %(url)s"

			elif type in SIMPLE_ATTACHMENTS:
				body += SIMPLE_ATTACHMENTS[type] % current

			else:
				body += "Unknown attachment: %s\n%s" % (type, str(current))
			result += body
	return result

registerHandler("msg01", parseAttachments)