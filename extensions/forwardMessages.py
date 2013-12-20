# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

from datetime import datetime

if not require("attachments"):
	raise

def parseForwardMessages(self, msg, depth = 0):
	body = ""
	if msg.has_key("fwd_messages"):
		body += _("\nForward messages:")
		fwd_messages = sorted(msg["fwd_messages"], msgSort)
		for fwd in fwd_messages:
			idFrom = fwd["uid"]
			date = fwd["date"]
			fwdBody = escapeMsg(uHTML(fwd["body"]))
			date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
			name = self.getUserData(idFrom)["name"]
			body += "\n[%s] <%s> %s" % (date, name, fwdBody)
			body += parseAttachments(self, fwd)
			if depth < MAXIMUM_FORWARD_DEPTH: # depth = 4
				depth += 1
				body += parseForwardMessages(self, fwd, depth)
	return body

Handlers["msg01"].append(parseForwardMessages)