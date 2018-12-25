# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2016.

import re
import urllib
from printer import *

VK_AUDIO_SEARCH_LINK = "https://vk.com/search?c[q]=%s&c[section]=audio"
WALL_LINK = "https://vk.com/wall%(to_id)s_%(id)s"
WALL_COMMENT_LINK = "https://vk.com/wall%(owner_id)s_%(post_id)s?w=wall%(owner_id)s3_%(post_id)s"
PHOTO_SIZES = ("src_xxxbig", "src_xxbig", "src_xbig", "src_big", "src", "url", "src_small")
STICKER_SIZES = ("photo_256", "photo_128", "photo_64")

ATTACHMENT_REGEX = re.compile(r"^(Photo|Document|Sticker)\:\s(“.+?”\s—\s)?"\
	r"(?P<url>http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+$)", re.UNICODE)

GLOBAL_USER_SETTINGS["parse_wall"] = {"value": 0, "label": "Parse wall attachments"}
GLOBAL_USER_SETTINGS["make_oob"] = {"value": 0, "label": "Allow OOB for attachments",
	"desc": "Attach incoming files as attachments,\nso they would be displayed by your client (if supported)"}


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
	if "attachments" in msg:
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

				current["desc"] = ""
				if current.get("description"):
					current["desc"] += uhtml(compile_eol.sub(" / ", "%(description)s, " % current))

				current["desc"] += "%(views)d views" % current
				current["time"] = "%d:%d" % (current["duration"] // 60, current["duration"] % 60)

				body += "Video: %(title)s (%(desc)s, %(time)s min) — https://vk.com/video%(owner_id)s_%(vid)s" % current

			elif type in SIMPLE_ATTACHMENTS:
				body += SIMPLE_ATTACHMENTS[type] % current

			else:
				body += "Unknown attachment: %s\n%s" % (type, str(current))
			result += body
	return result


def attachments_msg03(msg, destination, source):
	body = msg.getBody()
	if body:
		if msg.getType() == "groupchat":
			user = Chat.getUserObject(destination)
		else:
			user = Users.get(destination)
		if user and user.settings.make_oob:
			match = ATTACHMENT_REGEX.match(body.encode("utf-8"))
			if match:
				link = match.group("url")
				url = msg.setTag("x", namespace=xmpp.NS_OOB)
				url.setTagData("url", link)
				msg.setBody(link)



registerHandler("msg03", attachments_msg03)
registerHandler("msg01", parseAttachments)
