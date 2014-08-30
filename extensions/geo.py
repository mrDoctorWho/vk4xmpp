# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2013.

import urllib

GoogleMapLink = "https://maps.google.com/maps?q=%s"

def TimeAndRelativeDimensionInSpace(self, machine):
	body = ""
	if machine.has_key("geo"):
		WhereAreYou = machine["geo"]
		Place = WhereAreYou.get("place")
		Coordinates = WhereAreYou["coordinates"].split()
		Coordinates = "Lat.: {0}°, long: {1}°".format(*Coordinates)
		body = _("Point on the map: \n")
		if Place:
			body += _("Country: %s") % Place["country"]
			body += _("\nCity: %s\n") % Place["city"]
		body += _("Coordinates: %s") % Coordinates
		body += "\n%s — Google Maps" % GoogleMapLink % urllib.quote(WhereAreYou["coordinates"])
	return body

registerHandler("msg01", TimeAndRelativeDimensionInSpace)
