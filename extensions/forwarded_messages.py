# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from datetime import datetime

if not require("attachments"):
	raise AssertionError("'forwardMessages' requires 'attachments'")

def parseForwardedMessages(self, msg, depth = 0):
	body = ""
	if msg.has_key("fwd_messages"):
		spacer = (chr(32) + unichr(183) + chr(32)) * depth
		body = "\n" + spacer
		body += _("Forwarded messages:")
		fwd_messages = sorted(msg["fwd_messages"], sortMsg)
		for fwd in fwd_messages:
			source = fwd["uid"]
			date = fwd["date"]
			fwdBody = escape("", uHTML(fwd["body"]))
			date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
			name = self.vk.getUserData(source)["name"]
			body += "\n%s[%s] <%s> %s" % (spacer, date, name, fwdBody)
			body += parseAttachments(self, fwd)
			if depth < MAXIMUM_FORWARD_DEPTH: 
				body += parseForwardedMessages(self, fwd, (depth + 1))
	return body


Handlers["msg01"].append(parseForwardedMessages)
