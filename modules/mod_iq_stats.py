# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

from __main__ import *


STAT_FIELDS = {
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


def stats_handler(cl, iq):
	destination = iq.getTo()
	iqChildren = iq.getQueryChildren()
	result = iq.buildReply("result")
	if destination == TransportID:
		queryPayload = list()
		if not iqChildren:
			keys = sorted(STAT_FIELDS.keys(), reverse=True)
			for key in keys:
				Node = xmpp.Node("stat", {"name": key})
				queryPayload.append(Node)
		else:
			users = calcStats()
			shell = os.popen("ps -o vsz,rss,%%cpu,time -p %s" % os.getpid()).readlines()
			virt, real, percent, time = shell[1].split()
			stats = {"users": users,
					"KB": [virt, real],
					"percent": [percent],
					"seconds": [time],
					"threads": [threading.activeCount()],
					"messages": [Stats["msgout"], Stats["msgin"]]}
			for child in iqChildren:
				if child.getName() == "stat":
					name = child.getAttr("name")
					if name in STAT_FIELDS:
						attr = STAT_FIELDS[name]
						value = stats[attr].pop(0)
						node = xmpp.Node("stat", {"units": attr})
						node.setAttr("name", name)
						node.setAttr("value", value)
						queryPayload.append(node)
		if queryPayload:
			result.setQueryPayload(queryPayload)
			sender(cl, result)


def load():
	Component.RegisterHandler("iq", stats_handler, "get", xmpp.NS_STATS)