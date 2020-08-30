# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2016.

import re
import urllib
import time
from printer import *

VK_AUDIO_SEARCH_LINK = "https://vk.com/search?c[q]=%s&c[section]=audio"
WALL_LINK = "https://vk.com/wall%(to_id)s_%(id)s"
WALL_COMMENT_LINK = "https://vk.com/wall%(owner_id)s_%(post_id)s?w=wall%(owner_id)s_%(post_id)s"

PHOTO_SIZES = ("w", "z", "y", "x", "q", "p", "m", "o", "s")
STICKER_SIZES = (512, 352, 256, 128, 64)


ATTACHMENT_REGEX = re.compile(r"^(?P<type>Photo|Document|Sticker|Audio message)\:\s(?P<name>“.+?”\s—\s)?(?P<url>http[s]?:\/\/[^\s]+)$", re.UNICODE)

GLOBAL_USER_SETTINGS["parse_wall"] = {"value": 1, "label": "Parse wall attachments"}
GLOBAL_USER_SETTINGS["make_oob"] = {"value": 1, "label": "Allow OOB for attachments",
	"desc": "Attach incoming files as attachments,\nso they would be displayed by your client (if supported)"}


# The attachments that don't require any special movements
SIMPLE_ATTACHMENTS = {"doc": "Document: “%(title)s” — %(url)s",
	"link": "URL: %(title)s — %(url)s",
	"poll": "Poll: %(question)s",
	"page": "Page: %(title)s — %(view_url)s"}


timeFormat = lambda seconds: time.strftime('%H:%M:%S', time.gmtime(seconds))


def parseAttachments(self, msg, spacer=""):
	"""
	“parses” attachments from the json to a string
	"""
	result = (MSG_APPEND, "")
	final_body = ""
	if "attachments" in msg:
		attachments = msg["attachments"]
		# Add new line and "Attachments" if there some text added
		if msg.get("text") and len(attachments) > 1:
			final_body += chr(10) + spacer + _("Attachments:")
		if spacer:
			final_body += "\n"
		elif msg.get("text"):
			final_body += "\n"

		for num, attachment in enumerate(attachments):
			body = spacer
			type = attachment.get("type")
			current = attachment[type]
			if num > 0:
				body = chr(10) + spacer

			if type == "wall":
				if self.settings.parse_wall:
					tid = current.get("to_id", 1)
					name_ = self.vk.getName(tid)
					if tid > 0:
						name = "%s's" % name_
					else:
						name = "“%s”" % name_

					body += "Post on %s wall:\n" % name
					if current.get("text") or current.get("copy_text"):
						body += spacer + uhtml(compile_eol.sub("\n" + spacer, current["text"] or current.get("copy_text"))) + "\n"
					if current.get("attachments"):
						body += spacer + parseAttachments(self, current, spacer)[1] + "\n" + spacer + "\n"
				body += spacer + ("Wall: %s" % WALL_LINK % current)

			elif type == "photo":
				sizes = current.get("sizes", [])
				found = False
				for key in PHOTO_SIZES:
					for size in sizes:
						if size.get("type") == key:
							body += "Photo: %s" % size.get("url")  # No new line needed if we have just one photo and no text
							found = True
							break
					if found:
						break

			elif type == "audio":
				current["performer"] = uhtml(current.get("performer", ""))
				current["title"] = uhtml(current.get("title", ""))
				current["url"] = VK_AUDIO_SEARCH_LINK % urllib.quote(str("%(artist)s %(title)s" % current))
				current["time"] = timeFormat(current["duration"])
				body += "Audio: %(artist)s — “%(title)s“ (%(time)s min) — %(url)s" % current

			elif type == "audio_message":
				link = current.get("link_ogg") or current.get("link_mp3")
				body += "Audio message: %s (%s)" % (link, timeFormat(current["duration"]))

			elif type == "sticker":
				images = current.get("images", [])
				found = False
				for size in STICKER_SIZES:
					for image in images:
						if image.get("width") == size or image.get("height") == size:
							body += "Sticker: %s" % image["url"]
							found = True
							break
					if found:
						break

			elif type == "wall_reply":
				# TODO: What if it's a community? from_id will be negative.
				# TODO: Remove "[idxxx|Name]," from the text or make it a link if XHTML is allowed
				current["name"] = self.vk.getName(current["from_id"])
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
				current["time"] = timeFormat(current["duration"])

				body += "Video: %(title)s (%(desc)s, %(time)s min) — https://vk.com/video%(owner_id)s_%(id)s" % current

			elif type in SIMPLE_ATTACHMENTS:
				body += SIMPLE_ATTACHMENTS[type] % current

			else:
				body += "Unknown attachment: %s\n%s" % (type, str(current))
			final_body += body
			result = (MSG_APPEND, final_body)
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
				oob = msg.setTag("x", namespace=xmpp.NS_OOB)
				oob.setTagData("url", link)
				msg.setBody(link)



registerHandler("msg03", attachments_msg03)
registerHandler("msg01", parseAttachments)
