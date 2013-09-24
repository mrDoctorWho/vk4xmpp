# coding: utf
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

if not require("attachments"):
	raise

def parseForwardMessages(self, msg):
	body = ""
	if msg.has_key("fwd_messages"):
		body += _("\nForward messages:")
		fwd_messages = sorted(msg["fwd_messages"], msgSort)
		for fwd in fwd_messages:
			idFrom = fwd["uid"]
			date = fwd["date"]
			fwdBody = uHTML(fwd["body"])
			date = datetime.fromtimestamp(date).strftime("%d.%m.%Y %H:%M:%S")
			name = self.getUserName(idFrom)
			body += "\n[%s] <%s> %s" % (date, name, fwdBody)
			body += parseAttachments(self, fwd)
	return body

Handlers["msg01"].append(parseForwardMessages)