# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from datetime import datetime

if not require("attachments"):
	raise AssertionError("'forwardMessages' requires 'attachments'")

BASE_SPACER = chr(32) + unichr(183) + chr(32)

def parseForwardedMessages(self, msg, depth=0):
	body = ""
	if msg.has_key("fwd_messages"):
		spacer = BASE_SPACER * depth
		body = "\n" + spacer
		body += _("Forwarded messages:")
		fwd_messages = sorted(msg["fwd_messages"], sortMsg)
		for fwd in fwd_messages:
			source = fwd["uid"]
			date = fwd["date"]
			fwdBody = escape("", uhtml(compile_eol.sub("\n" + spacer + BASE_SPACER, fwd["body"])))
			date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
			name = self.vk.getUserData(source)["name"]
			body += "\n%s[%s] <%s> %s" % (spacer + BASE_SPACER, date, name, fwdBody)
			body += parseAttachments(self, fwd, spacer + (BASE_SPACER * 2))
			if depth < MAXIMUM_FORWARD_DEPTH: 
				body += parseForwardedMessages(self, fwd, (depth + 1))
	return body

if not isdef("MAXIMUM_FORWARD_DEPTH"):
	MAXIMUM_FORWARD_DEPTH = 28

registerHandler("msg01", parseForwardedMessages)

