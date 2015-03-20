# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.


def interpreter_msg02(msg):
	body = msg.getBody()
	jidTo = msg.getTo()
	destination = jidTo.getStripped()
	jidFrom = msg.getFrom()
	source = jidFrom.getStripped()
	
	if body:
		answer = None
		if jidTo == TransportID:
			raw = body.split(None, 1)
			if len(raw) > 1:
				text, args = raw
				args = args.strip()

				if text == "!eval" and args and source in ADMIN_JIDS:
					try:
						result = unicode(eval(args))
					except Exception:
						result = returnExc()
					sendMessage(Component, source, jidTo, result)

				elif text == "!exec" and args and source in ADMIN_JIDS:
					try:
						exec (unicode(args + "\n"), globals())
					except Exception:
						result = returnExc()
					else:
						result = "Done."
					sendMessage(Component, source, jidTo, result)

registerHandler("msg02", interpreter_msg02)