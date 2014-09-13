# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.

import xmpp
import urllib
from socket import error
from hashlib import sha1


def apply(instance, args=()):
	"""
	Executes instance(*args), but just return None on error occurred
	"""
	try:
		code = instance(*args)
	except Exception:
		code = None
	return code

isNumber = lambda obj: (not apply(int, (obj,)) is None)

def buildDataForm(form=None, type="submit", fields=[], title=None, data=[]):
	"""
	Provides easier method to build data forms using dict for each form object
	Parameters:
		form: xmpp.DataForm object
		type: form type
		fields: list of form objects represented as dict, e.g. 
			[{"var": "cool", "type": "text-single", 
			"desc": "my cool description", "value": "cool"}]
		title: form title
		data: advanced data for form. e.g. instructions (if string in the list), look at xmpp/protocol.py:1326
	"""
	form = form or xmpp.DataForm(type, data, title)
	for key in fields:
		field = form.setField(key["var"], key.get("value"), 
					key.get("type"), key.get("desc"), key.get("options"))
		if key.has_key("payload"):
			field.setPayload(key["payload"])
		if key.has_key("label"):
			field.setLabel(key["label"])
		if key.has_key("requred"):
			field.setRequired()
	return form

def buildIQError(stanza, error=xmpp.ERR_FEATURE_NOT_IMPLEMENTED, text=None):
	"""
	Provides a way to build IQ error reply
	"""
	error = xmpp.Error(stanza, error, True)
	if text:
		eTag = error.getTag("error")
		eTag.setTagData("text", text)
	return error

def normalizeValue(value):
	"""
	Normalizes boolean values from dataform replies
	"""
	if isNumber(value):
		value = int(value)
	elif value and value.lower() == "true":
		value = 1
	else:
		value = 0
	return value

def getLinkData(url, encode=True):
	"""
	Gets link data and ignores any exceptions
	Parameters:
		encode: base64 data encode
	"""
	try:
		opener = urllib.urlopen(url)
	except (Exception, error):
		return ""
	data = opener.read()
	if data and encode:
		data = data.encode("base64")
	return data
