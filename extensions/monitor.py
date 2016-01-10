# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, once upon a time

"""
Publishes your VK4XMPP instance in the public list
Which is located somewhere in Space
"""

def publishInstance():
	"""
	That's such a weird function just makes a post request
	to the vk4xmpp monitor which is located on http://xmppserv.ru/xmpp-monitor
	You can check out the source of The VK4XMPP Monitor utilty
		over there: https://github.com/aawray/xmpp-monitor
	"""
	if allowBePublic:
		if WhiteList:
			WhiteList.append(VK4XMPP_MONITOR_SERVER)
		if TransportID.split(".")[1] != "localhost":
			RIP = api.RequestProcessor()
			try:
				RIP.post(VK4XMPP_MONITOR_URL, {"add": TransportID})
				Print("#! Information about this transport has been successfully published.")
			except Exception:
				Print("#! Unable to publish information about the transport!")

registerHandler("evt01", publishInstance)
