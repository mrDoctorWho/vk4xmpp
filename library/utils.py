# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

import xmpp, urllib

def buildDataForm(form=None, type="submit", fields=[]):
	form = form or xmpp.DataForm(type)
	for key in fields:
		field = form.setField(key["var"], key.get("value"), key.get("type"))
		if key.get("payload"):
			field.setPayload(key["payload"])
		if key.get("label"):
			field.setLabel(key["label"])
	return form


def getLinkData(url, encode=True):
	opener = urllib.urlopen(url)
	data = opener.read()
	if data and encode:
		data = data.encode("base64")
	return data
