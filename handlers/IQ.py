# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

def iqHandler(cl, iq):
	jidFrom = iq.getFrom()
	source = jidFrom.getStripped()
	if WhiteList:
		if jidFrom and jidFrom.getDomain() not in WhiteList:
			Sender(cl, iqBuildError(iq, xmpp.ERR_BAD_REQUEST, "You're not in the white-list"))
			raise xmpp.NodeProcessed()

	if iq.getType() == "set" and iq.getTagAttr("captcha", "xmlns") == xmpp.NS_CAPTCHA:
		if source in Transport:
			jidTo = iq.getTo()
			if jidTo == TransportID:
				cTag = iq.getTag("captcha")
				cxTag = cTag.getTag("x", {}, xmpp.NS_DATA)
				fcxTag = cxTag.getTag("field", {"var": "ocr"})
				cValue = fcxTag.getTagData("value")
				captchaAccept(cl, cValue, jidTo, source)

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
		iqLastHandler(cl, iq)
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


def iqBuildError(stanza, error=None, text=None):
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
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if USER_LIMIT:
		count = calcStats()[0]
		if count >= USER_LIMIT and not source in Transport:
			cl.send(iqBuildError(iq, xmpp.ERR_NOT_ALLOWED, _("Transport's admins limited registrations, sorry.")))
			raise xmpp.NodeProcessed()

	if iType == "get" and destination == TransportID and not IQChildren:
		form = xmpp.DataForm()
		logger.debug("Sending register form to %s" % source)
		form.addChild(node=xmpp.Node("instructions")).setData(_("Type data in fields")) ## TODO: Complete this by forms
		link = form.setField("link", URL_ACCEPT_APP, "text-single")
		link.setLabel(_("Autorization page"))
		link.setDesc(_("If you won't get access-token automatically, please, follow authorization link and authorize app,\n"\
					   "and then paste url to password field."))
		phone = form.setField("phone", "+", "text-single")
		phone.setLabel(_("Phone number"))
		phone.setDesc(_("Enter phone number in format +71234567890"))
		use_password = form.setField("use_password", "0", "boolean")
		use_password.setLabel(_("Get access-token automatically"))
		use_password.setDesc(_("Try to get access-token automatically. (NOT recommented, password required!)"))
		password = form.setField("password", None, "text-private")
		password.setLabel(_("Password/Access-token"))
		password.setDesc(_("Type password, access-token or url (recommented)"))
		result.setQueryPayload((form,))

	elif iType == "set" and destination == TransportID and IQChildren:
		phone, password, usePassword, token = False, False, False, False
		Query = iq.getTag("query")
		if Query.getTag("x"):
			for node in iq.getTags("query", namespace=xmpp.NS_REGISTER):
				for node in node.getTags("x", namespace=xmpp.NS_DATA):
					phone = node.getTag("field", {"var": "phone"})
					phone = phone and phone.getTagData("value")
					password = node.getTag("field", {"var": "password"})
					password = password and password.getTagData("value")
					usePassword = node.getTag("field", {"var": "use_password"})
					usePassword = usePassword and usePassword.getTagData("value")

			if not password:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Empty password"))
			if not isNumber(usePassword):
				if usePassword and usePassword.lower() == "true":
					usePassword = 1
				else:
					usePassword = 0
			usePassword = int(usePassword)
			if not usePassword:
				logger.debug("user %s won't use password" % source)
				token = password
				password = None
			else:
				logger.debug("user %s wants use password" % source)
				if not phone:
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Phone incorrect."))
			if source in Transport:
				user = Transport[source]
				deleteUser(user, semph=False)
			else:
				user = User((phone, password), source)
			if not usePassword:
				try:
					token = token.split("#access_token=")[1].split("&")[0].strip()
				except (IndexError, AttributeError):
					pass
				user.token = token
			if not user.connect():
				logger.error("user %s connection failed (from iq)" % source)
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Incorrect password or access token!"))
			else:
				try:
					user.init()
				except api.CaptchaNeeded:
					user.vk.captchaChallenge()
				except Exception:
					crashLog("iq.user.init")
					result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Initialization failed."))
				else:
					Transport[source] = user
					Poll.add(Transport[source])
					watcherMsg(_("New user registered: %s") % source)

		elif Query.getTag("remove"): # Maybe exits a better way for it
			logger.debug("user %s wants remove me..." % source)
			if source in Transport:
				user = Transport[source]
				deleteUser(user, True, False)
				result.setPayload([], add = 0)
				watcherMsg(_("User removed registration: %s") % source)
			else:
				logger.debug("... but he do not know he already removed!")

		else:
			result = iqBuildError(iq, 0, _("Feature not implemented."))
	Sender(cl, result)

def calcStats():
	countTotal = 0
	countOnline = len(Transport)
	with Database(DatabaseFile, Semaphore) as db:
		db("select count(*) from users")
		countTotal = db.fetchone()[0]
	return [countTotal, countOnline]

def iqLastHandler(cl, iq):
	jidFrom = iq.getFrom()
	jidTo = iq.getTo()
	iType = iq.getType()
	source = jidFrom.getStripped()
	destination = jidTo.getStripped() ## By following standard we should use destination with resource, If we don't client must think user is offline. So, let it be.
	id = vk2xmpp(destination)
	if iType == "get":
		if id == TransportID:
			last = int(time.time() - startTime)
			name = IDentifier["name"]
		elif source in Transport and id in Transport[source].friends:
			last = int(time.time() - Transport[source].vk.method("messages.getLastActivity", {"user_id": id}).get("time", -1))
			name = Transport[source].getUserData(id)
		else:
			raise xmpp.NodeProcessed()
		result = xmpp.Iq("result", to=jidFrom, frm=destination)
		result.setID(iq.getID())
		result.setTag("query", {"seconds": str(last)}, xmpp.NS_LAST)
		result.setTagData("query", name)
		Sender(cl, result)

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

sDict = {
		"users/total": "users",
		"users/online": "users",
		"memory/virtual": "KB",
		"memory/real": "KB",
		"cpu/percent": "percent",
		"cpu/time": "seconds",
		"thread/active": "threads",
		"msg/in": "messages",
		"msg/out": "messages"
		}

def iqStatsHandler(cl, iq):
	destination = iq.getTo()
	iType = iq.getType()
	IQChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if iType == "get" and destination == TransportID:
		QueryPayload = list()
		if not IQChildren:
			keys = sorted(sDict.keys(), reverse=True)
			for key in keys:
				Node = xmpp.Node("stat", {"name": key})
				QueryPayload.append(Node)
		else:
			users = calcStats()
			shell = os.popen("ps -o vsz,rss,%%cpu,time -p %s" % os.getpid()).readlines()
			memVirt, memReal, cpuPercent, cpuTime = shell[1].split()
			stats = {"users": users, "KB": [memVirt, memReal],
					 "percent": [cpuPercent], "seconds": [cpuTime], "threads": [threading.activeCount()],
					 "messages": [Stats["msgout"], Stats["msgin"]]}
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
	source = iq.getFrom().getStripped()
	destination = iq.getTo().getStripped()
	iType = iq.getType()
	ns = iq.getQueryNS()
	Node = iq.getTagAttr("query", "node")
	if iType == "get":
		if not Node:
			QueryPayload = []
			if destination == TransportID:
				features = TransportFeatures
			else:
				features = UserFeatures

			result = iq.buildReply("result")
			QueryPayload.append(xmpp.Node("identity", IDentifier))
			if ns == xmpp.NS_DISCO_INFO:
				for key in features:
					xNode = xmpp.Node("feature", {"var": key})
					QueryPayload.append(xNode)
				result.setQueryPayload(QueryPayload)
			
			elif ns == xmpp.NS_DISCO_ITEMS:
				result.setQueryPayload(QueryPayload)

			Sender(cl, result)

def iqGatewayHandler(cl, iq):
	jidTo = iq.getTo()
	iType = iq.getType()
	destination = jidTo.getStripped()
	IQChildren = iq.getQueryChildren()
	if destination == TransportID:
		result = iq.buildReply("result")
		if iType == "get" and not IQChildren:
			query = xmpp.Node("query", {"xmlns": xmpp.NS_GATEWAY})
			query.setTagData("desc", "Enter api token")
			query.setTag("prompt")
			result.setPayload([query])

		elif IQChildren and iType == "set":
			token = ""
			for node in IQChildren:
				if node.getName() == "prompt":
					token = node.getData()
					break
			if token:
				xNode = xmpp.simplexml.Node("prompt")
				xNode.setData(token[0])
				result.setQueryPayload([xNode])
		else:
			raise xmpp.NodeProcessed()
		Sender(cl, result)

def vCardGetPhoto(url, encode=True):
	try:
		opener = urllib.urlopen(url)
		data = opener.read()
		if data and encode:
			data = data.encode("base64")
		return data
	except IOError:
		pass
	except Exception:
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
	source = jidFrom.getStripped()
	destination = jidTo.getStripped()
	iType = iq.getType()
	result = iq.buildReply("result")
	if iType == "get":
		_DESC = '\n'.join((DESC, "_" * 16, AdditionalAbout)) if AdditionalAbout else DESC
		if destination == TransportID:
			vcard = iqVcardBuild({"NICKNAME": "VK4XMPP Transport",
								"DESC": _DESC,
								"PHOTO": "https://raw.github.com/mrDoctorWho/vk4xmpp/master/vk4xmpp.png",
								"URL": "http://simpleapps.ru"
								})
			result.setPayload([vcard])

		elif source in Transport:
			user = Transport[source]
			if user.friends:
				id = vk2xmpp(destination)
				json = user.getUserData(id, ["screen_name", PhotoSize])
				values = {"NICKNAME": json.get("name", str(json)),
						"URL": "http://vk.com/id%s" % id,
						"DESC": _("Contact uses VK4XMPP Transport\n%s") % _DESC
						}
				if id in user.friends.keys():
					values["PHOTO"] = json.get(PhotoSize) or URL_VCARD_NO_IMAGE
				vCard = iqVcardBuild(values)
				result.setPayload([vCard])
			else:
				result = iqBuildError(iq, xmpp.ERR_BAD_REQUEST, _("Your friend-list is empty."))
		else:
			result = iqBuildError(iq, xmpp.ERR_REGISTRATION_REQUIRED, _("You're not registered for this action."))
	else:
		raise xmpp.NodeProcessed()
	Sender(cl, result)
