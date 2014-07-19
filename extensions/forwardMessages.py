# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from datetime import datetime

if not require("attachments"):
	raise AssertionError("'forwardMessages' requires 'attachments'")

def parseForwardMessages(self, msg, depth = 0):
	spacer = u" · " * depth
	body = "\n" + spacer
	if msg.has_key("fwd_messages"):

#		body += tab
		body += _("Forward messages:")
		fwd_messages = sorted(msg["fwd_messages"], msgSort)
		for fwd in fwd_messages:
			idFrom = fwd["uid"]
			date = fwd["date"]
			fwdBody = escape("", uHTML(fwd["body"]))
			date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
			name = self.getUserData(idFrom)["name"]
			body += "\n%s[%s] <%s> %s" % (spacer, date, name, fwdBody)
			body += parseAttachments(self, fwd)
			if depth < MAXIMUM_FORWARD_DEPTH: 
				depth += 1
				body += parseForwardMessages(self, fwd, depth)
	return body


Handlers["msg01"].append(parseForwardMessages)
