# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

import base64
from tempfile import mktemp
from cStringIO import StringIO

sticker_url = re.compile(r"^Sticker\:\s(http\:\/\/[a-zA-Z0-9\._\/]+)$")

try:
	from PIL import Image
except ImportError:
	logger.warning("sticker: not enabling RGB conversion because PIL is not installed")
	ENABLE_RGB_CONVERSION = False

if not isdef("STICKER_SIZE"):
	STICKER_SIZE = "128"

GLOBAL_USER_SETTINGS["send_stickers"] = {"label": "Send stickers with XHTML-IM", 
		"desc": "If set, transport would send images for stickers instead of URLs (requires client-side support)", "value": 0}


def convertImage(data):
	outfile = mktemp()
	io = StringIO(data)
	image = Image.open(io)
	image.convert("RGB").save(outfile, "JPEG", quality=RGB_CONVERSION_QUALITY)
	data = rFile(outfile)
	try:
		os.remove(outfile)
	except Exception:
		crashLog("convertImage")
	return data


def sendSticker(msg, destination, source):
	body = msg.getBody()
	if body:
		if msg.getType() == "groupchat":
			user = Chat.getUserObject(destination)
		else:
			user = Transport[destination]
		if user.settings.send_stickers:
			url = sticker_url.search(body)
			if url:
				url = url.group(1).replace("256b", STICKER_SIZE)
				data = urllib.urlopen(url).read()
				if data:
					mime = "png"
					if isdef("ENABLE_RGB_CONVERSION") and ENABLE_RGB_CONVERSION:
						data = convertImage(data)
						mime = "jpeg"
					data = base64.b64encode(data)
					xhtml = msg.setTag("html", namespace=xmpp.NS_XHTML_IM)
					xbody = xhtml.setTag("body", namespace="http://www.w3.org/1999/xhtml")
					xbody.setTag("br")
					xbody.setTag("img", {"src": "data:image/%s;base64,%s" % (mime, data), "alt": "img"})


def initStickerSender():
	if xmpp.NS_GROUPCHAT in TransportFeatures:
		registerHandler("msg03g", sendSticker)


registerHandler("evt01", initStickerSender)
registerHandler("msg03", sendSticker)