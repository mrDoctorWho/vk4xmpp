# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2020.


def parseReplyMessages(self, msg):
	body = ""
	result = (MSG_APPEND, "")
	if msg.get("reply_message"):
		# todo: add date if the message wasn't sent today
		reply = msg["reply_message"]
		text = escape("", uhtml(reply["text"])) 
		attachments = parseAttachments(self, reply)[1]
		forwarded_messages = parseForwardedMessages(self, reply)[1]
		if text:
			body += "> " + text
		if attachments:
			body += "> " + attachments
		if forwarded_messages:
			body += forwarded_messages.replace("\n", "\n>")
		body += "\n"
		result = (MSG_PREPEND, body)
	return result


registerHandler("msg01", parseReplyMessages)