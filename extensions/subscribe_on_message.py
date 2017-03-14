# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2017.


known_sources = [] # TODO: database

def subscribe_msg03(msg, destination, source):
	if source not in known_sources and destination in Users:
		user = Users[destination]
		id = vk2xmpp(source)
		data = user.vk.getUserData(id, notoken=True)
		dict = {id: {"name":data.get("name", "Anonymous User")}}
		user.sendSubPresence(dict)
		known_sources.append(source)

registerHandler("msg03", subscribe_msg03)