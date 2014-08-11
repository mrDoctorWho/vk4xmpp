# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

import xmpp, urllib
from hashlib import sha1

def buildDataForm(form=None, type="submit", fields=[]):
	form = form or xmpp.DataForm(type)
	for key in fields:
		field = form.setField(key["var"], key.get("value"), key.get("type"))
		if key.get("payload"):
			field.setPayload(key["payload"])
		if key.get("label"):
			field.setLabel(key["label"])
	return form

def buildIQError(stanza, error=None, text=None):
	if not error:
		error = xmpp.ERR_FEATURE_NOT_IMPLEMENTED
	error = xmpp.Error(stanza, error, True)
	if text:
		eTag = error.getTag("error")
		eTag.setTagData("text", text)
	return error

def getLinkData(url, encode=True):
	opener = urllib.urlopen(url)
	data = opener.read()
	if data and encode:
		data = data.encode("base64")
	return data
