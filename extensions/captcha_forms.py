# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014.
## TODO: Add check if mod_iq_captcha exists.

from hashlib import sha1

def captchaSend(self):
	logger.debug("VKLogin: sending message with captcha to %s" % self.source)
	body = _("WARNING: VK sent captcha to you."
			 " Please, go to %s and enter text from image to chat."
			 " Example: !captcha my_captcha_key. Tnx") % self.engine.captcha["img"]
	msg = xmpp.Message(self.source, body, "chat", frm = TransportID)
	x = msg.setTag("x", namespace=xmpp.NS_OOB)
	x.setTagData("url", self.engine.captcha["img"])
	captcha = msg.setTag("captcha", namespace=xmpp.NS_CAPTCHA)
	image = utils.getLinkData(self.engine.captcha["img"], False)
	if image:
		hash = sha1(image).hexdigest()
		encoded = image.encode("base64")
		form = utils.buildDataForm(type="form", fields = [{"var": "FORM_TYPE", "value": xmpp.NS_CAPTCHA, "type": "hidden"},
													{"var": "from", "value": TransportID, "type": "hidden"},
													{"var": "ocr", "label": _("Enter shown text"),
														"payload": [xmpp.Node("required"), xmpp.Node("media", {"xmlns": xmpp.NS_MEDIA},
															[xmpp.Node("uri", {"type": "image/jpg"},
																["cid:sha1+%s@bob.xmpp.org" % hash])])]}])
		captcha.addChild(node=form)
		oob = msg.setTag("data", {"cid": "sha1+%s@bob.xmpp.org" % hash, "type": "image/jpg", "max-age": "0"}, xmpp.NS_URN_OOB)
		oob.setData(encoded)
	sender(Component, msg)
	Presence = xmpp.protocol.Presence(self.source, show="xa", status=body, frm=TransportID)
	sender(Component, Presence)


registerHandler("evt04", captchaSend)