# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from hashlib import sha1

def sendCaptcha(user, url):
	logger.debug("VKLogin: sending message with captcha to %s" % user.source)
	body = _("WARNING: VK has sent you a CAPTCHA."
		" Please, follow %s and enter the text shown on the image to the chat."
		" Example: !captcha my_captcha_key. Tnx") % url
	msg = xmpp.Message(user.source, body, "chat", frm=TransportID)
	x = msg.setTag("x", namespace=xmpp.NS_OOB)
	x.setTagData("url", url)
	captcha = msg.setTag("captcha", namespace=xmpp.NS_CAPTCHA)
	image = utils.getLinkData(url, False)
	if image:
		hash = sha1(image).hexdigest()
		encoded = image.encode("base64")
		form = utils.buildDataForm(type="form", fields = [
			{"var": "FORM_TYPE", "value": xmpp.NS_CAPTCHA, "type": "hidden"},
			{"var": "from", "value": TransportID, "type": "hidden"},
			{"var": "ocr", "label": _("Enter shown text"),
			"payload": [xmpp.Node("required"), 
				xmpp.Node("media", {"xmlns": xmpp.NS_MEDIA}, 
					[xmpp.Node("uri", {"type": "image/jpg"}, 
						["cid:sha1+%s@bob.xmpp.org" % hash]
						)
					])
				]}
			])
		captcha.addChild(node=form)
		oob = msg.setTag("data", {"cid": "sha1+%s@bob.xmpp.org" % hash, "type": "image/jpg", "max-age": "0"}, xmpp.NS_URN_OOB)
		oob.setData(encoded)
	sender(Component, msg)
	sendPresence(user.source, TransportID, show="xa", reason=body)

TransportFeatures.update({xmpp.NS_OOB,
	xmpp.NS_MEDIA,
	xmpp.NS_CAPTCHA,
	xmpp.NS_URN_OOB})

registerHandler("evt04", sendCaptcha)