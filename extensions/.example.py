# coding: utf-8
# This file is a part of VK4XMPP Transport
# © simpleApps, 2014.
# This plugin contain all vk4xmpp plugin's API features
# Rename it to "example.py" if you wanna test it
# Please notice that plugins are working in globals() so names must be unique

## Events (not finished yet so not sorted):
# 01 - transport's start (threaded), no args
# 02 - transport's shutdown (linear)
# 03 - user deletion (linear), args: User object
# 04 - captcha (linear), args: VK object
# 05 - user became online (threaded), args: User object
# 06 - user became offline (linear), args: VK object (don't ask me why, i have no idea)
# 07 - user is logging in (linear, before the friends list wes received), args: User object
# 08 - new user registered, args: user's jid
# 09 - user unregistered, args: user's jid
## Messages: 01 outgoing (vk->xmpp), 02 incoming (xmpp), 03 is used to modify message (xmpp)
## Presences: 01 incoming presence, 02 - is used to modify outgoing presence (xmpp)

def evt01_handler():
	"""
	Threaded handler.
	Called when the transport's loaded and users initialized
	But before the modules are being loaded
	"""
	print "WOW! That's my awesome plugin event!"

registerHandler("evt01", evt01_handler)

def evt02_handler():
	"""
	Linear handler.
	Called when transport's shutting down
	"""
	print "NOOOOOOOOO! Transport is so awesome, why are you stopping it?"

registerHandler("evt02", evt02_handler)

def evt03_handler(user):
	"""
	Linear handler.
	Called when user has removed his registration ("unsubscribe" presence or "delete" in disco)
	Parameters:
		user: User class object
	Look at the User class for advanced information
	"""
	print "Print user %s is going to remove us" % (user.source)

registerHandler("evt03", evt03_handler)

def evt04_handler(vk):
	"""
	Linear handler.
	Called when user received a captcha
	Parameters:
		vk: VK class object
	"""
	print "Look at this man, he've got a captcha: %s. This image: %s is not for robots" % (vk.source, vk.engine.captcha["img"])

registerHandler("evt04", evt04_handler)

def evt05_handler(user):
	"""
	Threaded handler.
	Called when user became online (our xmpp user, so we received available/probe presence)
	Exactly at end of the user.initialize() function
	Parameters:
		user: User class object
	"""
	print "Hey, look who come to see us: %s" % user.source

registerHandler("evt05", evt05_handler)

def evt06_handler(vk):
	"""
	Threaded handler.
	Called when user is disconnected (vk)
	Exactly when user.vk.disconnect() is called
	Parameters:
		vk: VK class object
	"""
	print "We've lost this guy: %s" % vk.source ## yes VK class object too have source attribute

registerHandler("evt06", evt06_handler)


def evt08_handler(source):
	"""
	Linear handler
	Called when a new user registered
	"""

registerHandler("evt08", watch_registered)


def evt09_handler(source):
	"""
	Linear handler
	Called when a user has unregistered
	"""

registerHandler("evt09", watch_unregistered)


def evt07_handler(user):
	"""
	Linear handler
	Called when user is connecting (if authenticated)
	Parameters:
		user: User class object
	"""
	print "User", user.source, "is authenticated!"

def msg01_handler(user, message):
	"""
	Linear handler.
	Called for each message has been received from VK
	Parameters:
		user: User class object
		message: single message json object
	Return values:
		None: the function itself should send a message
		str type: transport's core will add returned string to existing body
	"""
	return "\nmsg01_handler is awesome"

registerHandler("msg01", msg01_handler)

def msg02_handler(msg):
	"""
	Linear handler.
	Called for each message has been received from xmpp
	Parameters:
		msg: xmpp.Message object
	"""
	print "Look who's trying to send us a message: %s" % msg.getFrom().getStripped()

registerHandler("msg02", msg02_handler)

def msg03_handler(msg, destination, source):
	"""
	Linear handler.
	Called when transport sending a message to XMPP
	Could be used for modifying message before it being sent
	Parameters:
		msg: xmpp.Message object
		destination: message destination
		source: message source
	Look at sendMessage() in transport's core for advanced information
	"""
	msg.setTag("awesome", namespace="urn:xmpp:awesome")

registerHandler("msg03", msg03_handler)

def prs01_handler(source, prs):
	"""
	Trheaded handler. I have no idea why.
	Called when presence received (no matter which one, when user in Transport)
	Also called when user is just initialized (only after "probe" presence)
	Parameters:
		source: presence source
		prs: xmpp.Presence object
	"""
	print "Hey, user %s is became %s in xmpp!" % (source, prs.getType())

registerHandler("prs01", prs01_handler)

def prs02_handler(prs, destination, source):
	"""
	Linear handler.
	Same as msg02_handler, but this one is for presence
	Parameters:
		prs: xmpp.Presence object
		destination: message destination
		source: message source
	Look at sendPresence() in transport's core for advanced information
	"""
	prs.setTag("c", {"node": "http://psi-dev.googlecode.com/caps", "ver": "0.16"}, xmpp.NS_CAPS)

registerHandler("prs02", prs02_handler)

## AdHoc. To add adhoc option (now only for user settings and only boolean values supported)
## You need to add form field to GLOBAL_USER_SETTINGS
## Example: GLOBAL_USER_SETTINGS["setting_name"] = {"label": "field label", "value": "default-value", "type": "field-type"}
## For field types look http://xmpp.org/extensions/xep-0004.html section 3.3 "Field Types"
## Ok now, look here.
GLOBAL_USER_SETTINGS["awesome_setting"] = {"label": "My new setting", "value": 0} ## If not type added, then boolean will be used
## Settings are being automatically saved as soon as they changed.
## To check if the value is equal to something, do:
## print user.settings.awesome_setting == 0
## where "user" is the User class object