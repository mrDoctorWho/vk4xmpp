# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2014 (15.12.14 06:09AM GMT)


def statstracker_callMethod(user):
	user.vk.method("stats.trackVisitor")

registerHandler("evt05", statstracker_callMethod)

