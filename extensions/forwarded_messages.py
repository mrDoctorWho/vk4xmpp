# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from datetime import datetime, timedelta, tzinfo, date

if not require("attachments"):
	raise AssertionError("'forwardMessages' requires 'attachments'")

BASE_SPACER = chr(32) + unichr(183) + chr(32)


class TimezoneOffset(tzinfo):

	def __init__(self, offset=0):
		self.offset = timedelta(hours=offset)

	def utcoffset(self, dt):
		return self.offset

	def tzname(self, dt):
		return None

	def dst(self, dt):
		return timedelta(0)


def parseForwardedMessages(self, msg, depth=0):
	body = ""
	if "fwd_messages" in msg:
		spacer = BASE_SPACER * depth
		body = "\n" + spacer
		body += _("Forwarded messages:")
		fwd_messages = sorted(msg["fwd_messages"], sortMsg)
		for fwd in fwd_messages:
			source = fwd["user_id"]
			fwdBody = escape("", uhtml(compile_eol.sub("\n" + spacer + BASE_SPACER, fwd["body"])))
			date = getUserDate(self, fwd["date"])
			name = self.vk.getName(source)
			body += "\n%s[%s] %s> %s" % (spacer + BASE_SPACER, date, name, fwdBody)
			body += parseAttachments(self, fwd, spacer + (BASE_SPACER * 2))
			if depth < MAXIMUM_FORWARD_DEPTH: 
				body += parseForwardedMessages(self, fwd, (depth + 1))
	return body


def getUserDate(user, timestamp):
	timezone = user.vk.getUserPreferences()[1]
	offset = TimezoneOffset(timezone)
	_date = datetime.fromtimestamp(timestamp, offset)
	today = datetime.fromtimestamp(time.time(), offset)
	_format = ""
	delta = today - _date
	if delta.days > 0:
		_format += "%d.%m"
	if delta.days > 300:
		_format += ".%Y"
	if _format:
		_format += " "
	_format += "%H.%M:%S"
	return _date.strftime(_format)


if not isdef("MAXIMUM_FORWARD_DEPTH"):
	MAXIMUM_FORWARD_DEPTH = 29

registerHandler("msg01", parseForwardedMessages)
