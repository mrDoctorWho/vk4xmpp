##   auth.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

# $Id: auth.py, v1.42 2013/10/21 alkorgun Exp $

"""
Provides library with all Non-SASL and SASL authentication mechanisms.
Can be used both for client and transport authentication.
"""

import hashlib
from . import dispatcher

from base64 import encodestring, decodestring
from .plugin import PlugIn
from .protocol import *
from random import random as _random
from re import findall as re_findall

def HH(some):
	return hashlib.md5(some).hexdigest()

def H(some):
	return hashlib.md5(some).digest()

def C(some):
	return ":".join(some)

class NonSASL(PlugIn):
	"""
	Implements old Non-SASL (JEP-0078) authentication used in jabberd1.4 and transport authentication.
	"""
	def __init__(self, user, password, resource):
		"""
		Caches username, password and resource for auth.
		"""
		PlugIn.__init__(self)
		self.DBG_LINE = "gen_auth"
		self.user = user
		self.password = password
		self.resource = resource

	def plugin(self, owner):
		"""
		Determine the best auth method (digest/0k/plain) and use it for auth.
		Returns used method name on success. Used internally.
		"""
		if not self.resource:
			return self.authComponent(owner)
		self.DEBUG("Querying server about possible auth methods", "start")
		resp = owner.Dispatcher.SendAndWaitForResponse(Iq("get", NS_AUTH, payload=[Node("username", payload=[self.user])]))
		if not isResultNode(resp):
			self.DEBUG("No result node arrived! Aborting...", "error")
			return None
		iq = Iq(typ="set", node=resp)
		query = iq.getTag("query")
		query.setTagData("username", self.user)
		query.setTagData("resource", self.resource)
		if query.getTag("digest"):
			self.DEBUG("Performing digest authentication", "ok")
			hash = hashlib.sha1(owner.Dispatcher.Stream._document_attrs["id"] + self.password).hexdigest()
			query.setTagData("digest", hash)
			if query.getTag("password"):
				query.delChild("password")
			method = "digest"
		elif query.getTag("token"):
			token = query.getTagData("token")
			seq = query.getTagData("sequence")
			self.DEBUG("Performing zero-k authentication", "ok")
			hash = hashlib.sha1(hashlib.sha1(self.password).hexdigest() + token).hexdigest()
			for i in xrange(int(seq)):
				hash = hashlib.sha1(hash).hexdigest()
			query.setTagData("hash", hash)
			method = "0k"
		else:
			self.DEBUG("Sequre methods unsupported, performing plain text authentication", "warn")
			query.setTagData("password", self.password)
			method = "plain"
		resp = owner.Dispatcher.SendAndWaitForResponse(iq)
		if isResultNode(resp):
			self.DEBUG("Sucessfully authenticated with remove host.", "ok")
			owner.User = self.user
			owner.Resource = self.resource
			owner._registered_name = owner.User + "@" + owner.Server + "/" + owner.Resource
			return method
		self.DEBUG("Authentication failed!", "error")

	def authComponent(self, owner):
		"""
		Authenticate component. Send handshake stanza and wait for result. Returns "ok" on success.
		"""
		self.handshake = 0
		hash = hashlib.sha1(owner.Dispatcher.Stream._document_attrs["id"] + self.password).hexdigest()
		owner.send(Node(NS_COMPONENT_ACCEPT + " handshake", payload=[hash]))
		owner.RegisterHandler("handshake", self.handshakeHandler, xmlns=NS_COMPONENT_ACCEPT)
		while not self.handshake:
			self.DEBUG("waiting on handshake", "notify")
			owner.Process(1)
		owner._registered_name = self.user
		if self.handshake + 1:
			return "ok"

	def handshakeHandler(self, disp, stanza):
		"""
		Handler for registering in dispatcher for accepting transport authentication.
		"""
		if stanza.getName() == "handshake":
			self.handshake = 1
		else:
			self.handshake = -1

class SASL(PlugIn):
	"""
	Implements SASL authentication.
	"""
	def __init__(self, username, password):
		PlugIn.__init__(self)
		self.username = username
		self.password = password

	def plugin(self, owner):
		if "version" not in self._owner.Dispatcher.Stream._document_attrs:
			self.startsasl = "not-supported"
		elif self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self.startsasl = None

	def auth(self):
		"""
		Start authentication. Result can be obtained via "SASL.startsasl" attribute
		and will beeither "success" or "failure". Note that successfull
		auth will take at least two Dispatcher.Process() calls.
		"""
		if self.startsasl:
			pass
		elif self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self._owner.RegisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)

	def plugout(self):
		"""
		Remove SASL handlers from owner's dispatcher. Used internally.
		"""
		if hasattr(self._owner, "features"):
			self._owner.UnregisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)
		if hasattr(self._owner, "challenge"):
			self._owner.UnregisterHandler("challenge", self.SASLHandler, xmlns=NS_SASL)
		if hasattr(self._owner, "failure"):
			self._owner.UnregisterHandler("failure", self.SASLHandler, xmlns=NS_SASL)
		if hasattr(self._owner, "success"):
			self._owner.UnregisterHandler("success", self.SASLHandler, xmlns=NS_SASL)

	def FeaturesHandler(self, conn, feats):
		"""
		Used to determine if server supports SASL auth. Used internally.
		"""
		if not feats.getTag("mechanisms", namespace=NS_SASL):
			self.startsasl = "not-supported"
			self.DEBUG("SASL not supported by server", "error")
			return None
		mecs = []
		for mec in feats.getTag("mechanisms", namespace=NS_SASL).getTags("mechanism"):
			mecs.append(mec.getData())
		self._owner.RegisterHandler("challenge", self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler("failure", self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler("success", self.SASLHandler, xmlns=NS_SASL)
		if "ANONYMOUS" in mecs and self.username == None:
			node = Node("auth", attrs={"xmlns": NS_SASL, "mechanism": "ANONYMOUS"})
		elif "DIGEST-MD5" in mecs:
			node = Node("auth", attrs={"xmlns": NS_SASL, "mechanism": "DIGEST-MD5"})
		elif "PLAIN" in mecs:
			sasl_data = "%s\x00%s\x00%s" % ("@".join((self.username, self._owner.Server)), self.username, self.password)
			node = Node("auth", attrs={"xmlns": NS_SASL, "mechanism": "PLAIN"}, payload=[encodestring(sasl_data).replace("\r", "").replace("\n", "")])
		else:
			self.startsasl = "failure"
			self.DEBUG("I can only use DIGEST-MD5 and PLAIN mecanisms.", "error")
			return
		self.startsasl = "in-process"
		self._owner.send(node.__str__())
		raise NodeProcessed()

	def SASLHandler(self, conn, challenge):
		"""
		Perform next SASL auth step. Used internally.
		"""
		if challenge.getNamespace() != NS_SASL:
			return None
		if challenge.getName() == "failure":
			self.startsasl = "failure"
			try:
				reason = challenge.getChildren()[0]
			except Exception:
				reason = challenge
			self.DEBUG("Failed SASL authentification: %s" % reason, "error")
			raise NodeProcessed()
		elif challenge.getName() == "success":
			self.startsasl = "success"
			self.DEBUG("Successfully authenticated with remote server.", "ok")
			handlers = self._owner.Dispatcher.dumpHandlers()
			self._owner.Dispatcher.PlugOut()
			dispatcher.Dispatcher().PlugIn(self._owner)
			self._owner.Dispatcher.restoreHandlers(handlers)
			self._owner.User = self.username
			raise NodeProcessed()
		incoming_data = challenge.getData()
		chal = {}
		data = decodestring(incoming_data)
		self.DEBUG("Got challenge:" + data, "ok")
		for pair in re_findall('(\w+\s*=\s*(?:(?:"[^"]+")|(?:[^,]+)))', data):
			key, value = [x.strip() for x in pair.split("=", 1)]
			if value[:1] == '"' and value[-1:] == '"':
				value = value[1:-1]
			chal[key] = value
		if "qop" in chal and "auth" in [x.strip() for x in chal["qop"].split(",")]:
			resp = {}
			resp["username"] = self.username
			resp["realm"] = self._owner.Server
			resp["nonce"] = chal["nonce"]
			cnonce = ""
			for i in xrange(7):
				cnonce += hex(int(_random() * 65536 * 4096))[2:]
			resp["cnonce"] = cnonce
			resp["nc"] = ("00000001")
			resp["qop"] = "auth"
			resp["digest-uri"] = "xmpp/" + self._owner.Server
			A1 = C([H(C([resp["username"], resp["realm"], self.password])), resp["nonce"], resp["cnonce"]])
			A2 = C(["AUTHENTICATE", resp["digest-uri"]])
			response = HH(C([HH(A1), resp["nonce"], resp["nc"], resp["cnonce"], resp["qop"], HH(A2)]))
			resp["response"] = response
			resp["charset"] = "utf-8"
			sasl_data = ""
			for key in ("charset", "username", "realm", "nonce", "nc", "cnonce", "digest-uri", "response", "qop"):
				if key in ("nc", "qop", "response", "charset"):
					sasl_data += "%s=%s," % (key, resp[key])
				else:
					sasl_data += "%s=\"%s\"," % (key, resp[key])
			node = Node("response", attrs={"xmlns": NS_SASL}, payload=[encodestring(sasl_data[:-1]).replace("\r", "").replace("\n", "")])
			self._owner.send(node.__str__())
		elif "rspauth" in chal:
			self._owner.send(Node("response", attrs={"xmlns": NS_SASL}).__str__())
		else:
			self.startsasl = "failure"
			self.DEBUG("Failed SASL authentification: unknown challenge", "error")
		raise NodeProcessed()

class Bind(PlugIn):
	"""
	Bind some JID to the current connection to allow router know of our location.
	"""
	def __init__(self):
		PlugIn.__init__(self)
		self.DBG_LINE = "bind"
		self.bound = None

	def plugin(self, owner):
		"""
		Start resource binding, if allowed at this time. Used internally.
		"""
		if self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self._owner.RegisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)

	def plugout(self):
		"""
		Remove Bind handler from owner's dispatcher. Used internally.
		"""
		self._owner.UnregisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)

	def FeaturesHandler(self, conn, feats):
		"""
		Determine if server supports resource binding and set some internal attributes accordingly.
		"""
		if not feats.getTag("bind", namespace=NS_BIND):
			self.bound = "failure"
			self.DEBUG("Server does not requested binding.", "error")
			return None
		if feats.getTag("session", namespace=NS_SESSION):
			self.session = 1
		else:
			self.session = -1
		self.bound = []

	def Bind(self, resource=None):
		"""
		Perform binding. Use provided resource name or random (if not provided).
		"""
		while self.bound is None and self._owner.Process(1):
			pass
		if resource:
			resource = [Node("resource", payload=[resource])]
		else:
			resource = []
		resp = self._owner.SendAndWaitForResponse(Protocol("iq", typ="set", payload=[Node("bind", attrs={"xmlns": NS_BIND}, payload=resource)]))
		if isResultNode(resp):
			self.bound.append(resp.getTag("bind").getTagData("jid"))
			self.DEBUG("Successfully bound %s." % self.bound[-1], "ok")
			jid = JID(resp.getTag("bind").getTagData("jid"))
			self._owner.User = jid.getNode()
			self._owner.Resource = jid.getResource()
			resp = self._owner.SendAndWaitForResponse(Protocol("iq", typ="set", payload=[Node("session", attrs={"xmlns": NS_SESSION})]))
			if isResultNode(resp):
				self.DEBUG("Successfully opened session.", "ok")
				self.session = 1
				return "ok"
			else:
				self.DEBUG("Session open failed.", "error")
				self.session = 0
		elif resp:
			self.DEBUG("Binding failed: %s." % resp.getTag("error"), "error")
		else:
			self.DEBUG("Binding failed: timeout expired.", "error")
			return ""

class ComponentBind(PlugIn):
	"""
	ComponentBind some JID to the current connection to allow router know of our location.
	"""
	def __init__(self, sasl):
		PlugIn.__init__(self)
		self.DBG_LINE = "bind"
		self.bound = None
		self.needsUnregister = None
		self.sasl = sasl

	def plugin(self, owner):
		"""
		Start resource binding, if allowed at this time. Used internally.
		"""
		if not self.sasl:
			self.bound = []
			return None
		if self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self._owner.RegisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)
			self.needsUnregister = 1

	def plugout(self):
		"""
		Remove ComponentBind handler from owner's dispatcher. Used internally.
		"""
		if self.needsUnregister:
			self._owner.UnregisterHandler("features", self.FeaturesHandler, xmlns=NS_STREAMS)

	def FeaturesHandler(self, conn, feats):
		"""
		Determine if server supports resource binding and set some internal attributes accordingly.
		"""
		if not feats.getTag("bind", namespace=NS_BIND):
			self.bound = "failure"
			self.DEBUG("Server does not requested binding.", "error")
			return None
		if feats.getTag("session", namespace=NS_SESSION):
			self.session = 1
		else:
			self.session = -1
		self.bound = []

	def Bind(self, domain=None):
		"""
		Perform binding. Use provided domain name (if not provided).
		"""
		while self.bound is None and self._owner.Process(1):
			pass
		if self.sasl:
			xmlns = NS_COMPONENT_1
		else:
			xmlns = None
		self.bindresponse = None
		ttl = dispatcher.DefaultTimeout
		self._owner.RegisterHandler("bind", self.BindHandler, xmlns=xmlns)
		self._owner.send(Protocol("bind", attrs={"name": domain}, xmlns=NS_COMPONENT_1))
		while self.bindresponse is None and self._owner.Process(1) and ttl > 0:
			ttl -= 1
		self._owner.UnregisterHandler("bind", self.BindHandler, xmlns=xmlns)
		resp = self.bindresponse
		if resp and resp.getAttr("error"):
			self.DEBUG("Binding failed: %s." % resp.getAttr("error"), "error")
		elif resp:
			self.DEBUG("Successfully bound.", "ok")
			return "ok"
		else:
			self.DEBUG("Binding failed: timeout expired.", "error")
			return ""

	def BindHandler(self, conn, bind):
		self.bindresponse = bind
		pass
