# coding: utf
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

def iqHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidFromStr = jidFrom.getStripped()
	if WhiteList:
		if jidFrom and jidFrom.getDomain() not in WhiteList:
			Sender(cl, iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "You're not in the white-list"))
			raise xmpp.NodeProcessed()

	if iq.getType() == "set" and iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		if jidFromStr in Transport:
			jidTo = iq.getTo()
			if jidTo == TransportID:
				cTag = iq.getTag("captcha")
				cxTag = cTag.getTag("x", {}, xmpp.NS_DATA)
				fcxTag = cxTag.getTag("field", {"var": "ocr"})
				cValue = fcxTag.getTagData("value")
				captchaAccept(cl, cValue, jidTo, jidFromStr)

	ns = iq.getQueryNS()
	if ns == xmpp.NS_REGISTER:
		iqRegisterHandler(cl, iq)
	elif ns == xmpp.NS_GATEWAY:
		iqGatewayHandler(cl, iq)
	elif ns == xmpp.NS_STATS: 
		iqStatsHandler(cl, iq)
	elif ns == xmpp.NS_VERSION:
		iqVersionHandler(cl, iq)
	elif ns == xmpp.NS_LAST:
		iqUptimeHandler(cl, iq)
	elif ns in (xmpp.NS_DISCO_INFO, xmpp.NS_DISCO_ITEMS):
		iqDiscoHandler(cl, iq)
	else:
		Tag = iq.getTag("vCard") or iq.getTag("ping")
		if Tag and Tag.getNamespace() == xmpp.NS_VCARD:
			iqVcardHandler(cl, iq)
		elif Tag and Tag.getNamespace() == xmpp.NS_PING:
			jidTo = iq.getTo()
			if jidTo == TransportID:
				Sender(cl, iq.buildReply("result"))

	raise xmpp.NodeProcessed()

def iqBuildError(stanza, error = None, text = None):
	if not error:
		error = xmpp.ERR_FEATURE_NOT_IMPLEMENTED
	error = xmpp.Error(stanza, error, True)
	if text:
		eTag = error.getTag("error")
		eTag.setTagData("text", text)
	return error

URL_ACCEPT_APP = "http://simpleapps.ru/vk4xmpp.html"

def iqRegisterHandler(cl, iq):
	jidTo = iq.getTo()
	jidFrom = iq.getFrom()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")

	if iType == "get" and jidToStr == TransportID and not IQChildren:
		data = xmpp.Node("x")
		logger.debug("Sending register form to %s" % jidFromStr)
		data.setNamespace(xmpp.NS_DATA)
		instr= data.addChild(node=xmpp.Node("instructions"))
		instr.setData(_("Type data in fields"))
		link = data.addChild(node=xmpp.DataField("link"))
		link.setLabel(_("Autorization page"))
		link.setType("text-single")
		link.setValue(URL_ACCEPT_APP)
		link.setDesc(_("If you won't get access-token automatically, please, follow authorization link and authorize app,\n"\
					  "and then paste url to password field."))
		phone = data.addChild(node=xmpp.DataField("phone"))
		phone.setLabel(_("Phone number"))
		phone.setType("text-single")
		phone.setValue("+")
		phone.setDesc(_("Enter phone number in format +71234567890"))
		use_password = data.addChild(node=xmpp.DataField("use_password"))
		use_password.setLabel(_("Get access-token automatically"))
		use_password.setType("boolean")
		use_password.setValue("0")
		use_password.setDesc(_("Try to get access-token automatically. (NOT recommented, password required!)"))
		password = data.addChild(node=xmpp.DataField("password"))
		password.setLabel(_("Password/Access-token"))
		password.setType("text-private")
		password.setDesc(_("Type password, access-token or url (recommented)"))
		result.setQueryPayload((data,))

	elif iType == "set" and jidToStr == TransportID and IQChildren:
		phone, password, usePassword, token = False, False, False, False
		Query = iq.getTag("query")
		if Query.getTag("x"):
			for node in iq.getTags("query", namespace = xmpp.NS_REGISTER):
				for node in node.getTags("x", namespace = xmpp.NS_DATA):
					phone = node.getTag("field", {"var": "phone"})
					phone = phone and phone.getTagData("value")
					password = node.getTag("field", {"var": "password"})
					password = password and password.getTagData("value")
					usePassword = node.getTag("field", {"var": "use_password"})
					usePassword = usePassword and usePassword.getTagData("value")

			if not password:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Null password"))
			if not isNumber(usePassword):
				if usePassword and usePassword.lower() == "true":
					usePassword = 1
				else:
					usePassword = 0
			usePassword = int(usePassword)
			if not usePassword:
				logger.debug("user %s won't to use password" % jidFromStr)
				token = password
				password = None
			else:
				logger.debug("user %s want to use password" % jidFromStr)
				if not phone:
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Phone incorrect."))
			if jidFromStr in Transport:
				user = Transport[jidFromStr]
				user.deleteUser()
			else:
				user = tUser((phone, password), jidFromStr)
			if not usePassword:
				try:
					token = token.split("#access_token=")[1].split("&")[0].strip()
				except (IndexError, AttributeError):
					pass
				user.token = token
			if not user.connect():
				logger.error("user %s connection failed (from iq)" % jidFromStr)
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
			else:
				try: 
					user.init()
				except api.CaptchaNeeded:
					user.vk.captchaChallenge()
				except:
					crashLog("iq.user.init")
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
				else:
					Transport[jidFromStr] = user
					updateTransportsList(Transport[jidFromStr]) #$
					WatcherMsg(_("New user registered: %s") % jidFromStr)

		elif Query.getTag("remove"): # Maybe exits a better way for it
			logger.debug("user %s want to remove me :(" % jidFromStr)
			if jidFromStr in Transport:
				Class = Transport[jidFromStr]
				Class.deleteUser(True)
				result.setPayload([], add = 0)
				WatcherMsg(_("User remove registration: %s") % jidFromStr)
		else:
			result = iqBuildError(iq, 0, _("Feature not implemented."))
	Sender(cl, result)

def calcStats():
	countTotal = 0
	countOnline = 0
	with Database(DatabaseFile, Semaphore) as db:
		db("select count(*) from users")
		countTotal = db.fetchone()[0]
	for key in TransportsList:
		if hasattr(key, "vk") and key.vk.Online:
			countOnline += 1
	return [countTotal, countOnline]

def iqUptimeHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	iType = iq.getType()
	if iType == "get" and jidTo == TransportID:
		uptime = int(time.time() - startTime)
		result = xmpp.Iq("result", to = jidFrom)
		result.setID(iq.getID())
		result.setTag("query", {"seconds": str(uptime)}, xmpp.NS_LAST)
		result.setTagData("query", IDentifier["name"])
		Sender(cl, result)
	raise xmpp.NodeProcessed()

def iqVersionHandler(cl, iq):
	iType = iq.getType()
	jidTo = iq.getTo()
	if iType == "get" and jidTo == TransportID:
		result = iq.buildReply("result")
		Query = result.getTag("query")
		Query.setTagData("name", IDentifier["name"])
		Query.setTagData("version", Revision)
		Query.setTagData("os", "%s / %s" % (OS, Python))
		Sender(cl, result)
	raise xmpp.NodeProcessed()

sDict = {
		  "users/total": "users",
		  "users/online": "users",
		  "memory/virtual": "KB",
		  "memory/real": "KB",
		  "cpu/percent": "percent",
		  "cpu/time": "seconds"
		  }

def iqStatsHandler(cl, iq):
	jidToStr = iq.getTo()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if iType == "get" and jidToStr == TransportID:
		QueryPayload = list()
		if not IQChildren:
			keys = sorted(sDict.keys(), reverse = True)
			for key in keys:
				Node = xmpp.Node("stat", {"name": key})
				QueryPayload.append(Node)
		else:
			users = calcStats()
			shell = os.popen("ps -o vsz,rss,%%cpu,time -p %s" % os.getpid()).readlines()
			memVirt, memReal, cpuPercent, cpuTime = shell[1].split()
			stats = {"users": users, "KB": [memVirt, memReal], 
					 "percent": [cpuPercent], "seconds": [cpuTime]}
			for Child in IQChildren:
				if Child.getName() != "stat":
					continue
				name = Child.getAttr("name")
				if name in sDict:
					attr = sDict[name]
					value = stats[attr].pop(0)
					Node = xmpp.Node("stat", {"units": attr})
					Node.setAttr("name", name)
					Node.setAttr("value", value)
					QueryPayload.append(Node)
		if QueryPayload:
			result.setQueryPayload(QueryPayload)
			Sender(cl, result)

def iqDiscoHandler(cl, iq):
	jidFromStr = iq.getFrom().getStripped()
	jidToStr = iq.getTo().getStripped()
	iType = iq.getType()
	ns = iq.getQueryNS()
	Node = iq.getTagAttr("query", "node")
	if iType == "get":
		if not Node and jidToStr == TransportID:
			QueryPayload = []
			result = iq.buildReply("result")
			QueryPayload.append(xmpp.Node("identity", IDentifier))
			if ns == xmpp.NS_DISCO_INFO:
				for key in TransportFeatures:
					xNode = xmpp.Node("feature", {"var": key})
					QueryPayload.append(xNode)
				result.setQueryPayload(QueryPayload)
			elif ns == xmpp.NS_DISCO_ITEMS:
				result.setQueryPayload(QueryPayload)
			Sender(cl, result)
	raise xmpp.NodeProcessed()

def iqGatewayHandler(cl, iq):
	jidTo = iq.getTo()
	iType = iq.getType()
	jidToStr = jidTo.getStripped()
	IQChildren = iq.getQueryChildren()
	if jidToStr == TransportID:
		result = iq.buildReply("result")
		if iType == "get" and not IQChildren:
			query = xmpp.Node("query", {"xmlns": xmpp.NS_GATEWAY})
			query.setTagData("desc", "Enter phone number")
			query.setTag("prompt")
			result.setPayload([query])

		elif IQChildren and iType == "set":
			phone = ""
			for node in IQChildren:
				if node.getName() == "prompt":
					phone = node.getData()
					break
			if phone:
				xNode = xmpp.simplexml.Node("prompt")
				xNode.setData(phone[0])
				result.setQueryPayload([xNode])
		else:
			raise xmpp.NodeProcessed()
		Sender(cl, result)

def vCardGetPhoto(url, encode = True):
	try:
		opener = urllib.urlopen(url)
		data = opener.read()
		if data and encode:
			data = data.encode("base64")
		return data
	except IOError:
		pass
	except:
		crashLog("vcard.getPhoto")

def iqVcardBuild(tags):
	vCard = xmpp.Node("vCard", {"xmlns": xmpp.NS_VCARD})
	for key in tags.keys():
		if key == "PHOTO":
			binVal = vCard.setTag("PHOTO")
			binVal.setTagData("BINVAL", vCardGetPhoto(tags[key]))
		else:
			vCard.setTagData(key, tags[key])
	return vCard

def iqVcardHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	jidFromStr = jidFrom.getStripped()
	jidToStr = jidTo.getStripped()
	iType = iq.getType()
	result = iq.buildReply("result")
	if iType == "get":
		if jidToStr == TransportID:
			vcard = iqVcardBuild({"NICKNAME": "VK4XMPP Transport",
								  "DESC": DESC,
								  "PHOTO": "http://simpleApps.ru/vk4xmpp.png",
								  "URL": "http://simpleapps.ru"})
			result.setPayload([vcard])

		elif jidFromStr in Transport:
			Class = Transport[jidFromStr]
			Friends = Class.vk.getFriends(["screen_name", PhotoSize])
			if Friends:
				id = vk2xmpp(jidToStr)
				if id in Friends.keys():
					name = Friends[id]["name"]
					photo = Friends[id].get("photo_100") or URL_VCARD_NO_IMAGE
					vCard = iqVcardBuild({"NICKNAME": name, "PHOTO": photo, "URL": "http://vk.com/id%s" % id,
										  "DESC": _("Contact uses VK4XMPP Transport\n%s") % DESC})
					result.setPayload([vCard])
				else:
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("User is not your friend."))
			else:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is null."))
		else:
			result = iqBuildError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
	else:
		raise xmpp.NodeProcessed()
	Sender(cl, result)
