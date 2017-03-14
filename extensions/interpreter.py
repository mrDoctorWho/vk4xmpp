# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

import traceback

def interpreter_msg02(msg):
	body = msg.getBody()
	destination = msg.getTo().getStripped()
	source = msg.getFrom().getStripped()
	if body:
		if destination == TransportID:
			raw = body.split(None, 1)
			if len(raw) > 1:
				text, args = raw
				args = args.strip()
				if source in Users:
					user = Users[source]
				if text == "!eval" and args and source in ADMIN_JIDS:
					try:
						result = unicode(eval(args))
					except Exception:
						result = traceback.format_exc()
					sendMessage(source, destination, result)

				elif text == "!exec" and args and source in ADMIN_JIDS:
					try:
						exec (unicode(args + "\n"), globals())
					except Exception:
						result = traceback.format_exc()
					else:
						result = "Done."
					sendMessage(source, destination, result)

registerHandler("msg02", interpreter_msg02)