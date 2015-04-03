# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2015.

from __main__ import *


STAT_FIELDS = {
			"users/total": "users",
			"users/online": "users",
			"memory/virtual": "MB",
			"memory/real": "MB",
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
				node = xmpp.Node("stat", {"name": key})
				queryPayload.append(node)
		else:
			users = calcStats()
			try:
				shell = os.popen("ps -o vsz,rss,%%cpu,time -p %s" % os.getpid()).readlines()
				virt, real, percent, time = shell[1].split()
			except IndexError:
				logger.error("IndexError during trying to execute `ps`")
				raise xmpp.NodeProcessed()

			virt, real = "%0.2f" % (int(virt)/1024.0), "%0.2f" % (int(real)/1024.0)
			stats = {"users": users,
					"MB": [virt, real],
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
	TransportFeatures.add(xmpp.NS_STATS)
	Component.RegisterHandler("iq", stats_handler, "get", xmpp.NS_STATS)


def unload():
	TransportFeatures.remove(xmpp.NS_STATS)
	Component.UnregisterHandler("iq", stats_handler, "get", xmpp.NS_STATS)