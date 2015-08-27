# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.


def watcherMsg(text):
	"""
	Send message to jids in watchers list
	"""
	for jid in WatcherList:
		sendMessage(jid, TransportID, text)

def watch_unregistered(source):
	watcherMsg(_("User has removed registration: %s") % source)

if not isdef("WatcherList"):
	WatcherList = []

def watch_registered(source):
	watcherMsg(_("New user registered: %s") % source)

registerHandler("evt08", watch_registered)
registerHandler("evt09", watch_unregistered)