# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013 — 2014.

import urllib

GoogleMapLink = "https://maps.google.com/maps?q=%s"

def TimeAndRelativeDimensionInSpace(self, machine):
	body = ""
	result = (MSG_APPEND, "")
	if machine.has_key("geo"):
		t_machine = machine["geo"]
		place = t_machine.get("place")
		coordinates = t_machine["coordinates"].split()
		coordinates = "Lat.: {0}°, long: {1}°".format(*coordinates)
		body = _("Point on the map: \n")
		if place:
			body += _("Country: %s") % place["country"]
			body += _("\nCity: %s\n") % place["city"]
		body += _("Coordinates: %s") % coordinates
		body += "\n%s — Google Maps" % GoogleMapLink % urllib.quote(t_machine["coordinates"])
		result = (MSG_APPEND, body)
	return result

registerHandler("msg01", TimeAndRelativeDimensionInSpace)
