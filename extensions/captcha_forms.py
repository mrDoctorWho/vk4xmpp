# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 — 2015.

from hashlib import sha1
import xmpp

"""
Implements XEP-0158: CAPTCHA Forms
"""


def sendCaptcha(user, captcha):
	"""
	Send a captcha to the user
	Args:
		user: the user's jid
		captcha: captcha dictionary ({"url": "https://vk.com/...", "sid": "10"})
	"""
	url = captcha.get("img")
	sid = captcha.get("sid")
	logger.debug("VK: sending message with captchaXMPP (jid: %s)", user)
	body = _("WARNING: VK has sent you a CAPTCHA."
		" Please, follow the link: %s and enter the text shown on the image to the chat."
		" Example: !captchaXMPP my_captcha_key."
		"\nWarning: don't use Firefox to open the link.") % url
	msg = xmpp.Message(user, body, "chat", frm=TransportID)
	x = msg.setTag("x", namespace=xmpp.NS_OOB)
	x.setTagData("url", url)
	captchaNode = msg.setTag("captchaXMPP", namespace=xmpp.NS_CAPTCHA)
	image = utils.getLinkData(url, False)
	if image:
		hash = sha1(image).hexdigest()
		encoded = image.encode("base64")
		payload = [xmpp.Node("required"),
					xmpp.Node("media", {"xmlns": xmpp.NS_MEDIA},
					[xmpp.Node("uri", {"type": "image/jpg"},
						["cid:sha1+%s@bob.xmpp.org" % hash])])]  # feel yourself like a erlang programmer
		fields = [{"var": "FORM_TYPE", "value": xmpp.NS_CAPTCHA, "type": "hidden"}]
		fields.append({"var": "from", "value": TransportID, "type": "hidden"})
		fields.append({"var": "challenge", "value": msg.getID(), "type": "hidden"})
		fields.append({"var": "ocr", "label": _("Enter shown text"), "payload": payload})
		form = utils.buildDataForm(type="form", fields=fields)
		captchaNode.addChild(node=form)
		oob = msg.setTag("data", {"cid": "sha1+%s@bob.xmpp.org" % hash, "type": "image/jpg", "max-age": "0"}, xmpp.NS_URN_OOB)
		oob.setData(encoded)
	else:
		logger.warning("unable to get the image from %s (jid: %s)", url, user)
	msg.setID(sid)
	sender(Component, msg)
	sendPresence(user, TransportID, show="xa", reason=body, hash=USER_CAPS_HASH)

TransportFeatures.update({xmpp.NS_OOB,
	xmpp.NS_MEDIA,
	xmpp.NS_CAPTCHA,
	xmpp.NS_URN_OOB})

registerHandler("evt04", sendCaptcha)
