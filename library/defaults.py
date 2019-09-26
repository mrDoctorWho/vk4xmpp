# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

"""
Contains all default variables used by VK4XMPP
"""

__author__ = "mrDoctorWho <mrdoctorwho@gmail.com>"

import logging
import xmpp

ALIVE = True

# config vairables
DEBUG_XMPPPY = False
DEBUG_POLL = None
DEBUG_API = []
STANZA_SEND_INTERVAL = 0.03125
THREAD_STACK_SIZE = 0
VK_ACCESS = 69638
USER_LIMIT = 0
RUN_AS = None
ALLOW_REGISTRATION = True

IDENTIFIER = {"type": "vk", "category": "gateway", "name": "VK4XMPP Transport", "short": "VK4XMPP"}
URL_ACCEPT_APP = "http://opiums.eu/vk4xmpp.html#%d"
VK4XMPP_MONITOR_SERVER = "opiums.eu"
VK4XMPP_MONITOR_URL = "http://torrent.opiums.eu/hosts_xmpp.php"
CAPS_NODE = "https://simpleapps.ru/caps/vk4xmpp"

USER_CAPS_HASH = None
TRANSPORT_CAPS_HASH = None

LOG_LEVEL = logging.DEBUG
ADMIN_JIDS = []

# files & folders transport uses
pidFile = "vk4xmpp.pid"
logFile = "vk4xmpp.log"
crashDir = "crash"
settingsDir = "settings"


# extension/module specific
PhotoSize = "photo_100"
DefLang = "ru"
AdditionalAbout = ""
allowBePublic = True

# The features transport will advertise
TransportFeatures = {xmpp.NS_DELAY, xmpp.NS_CHATSTATES, xmpp.NS_LAST, xmpp.NS_CHAT_MARKERS, xmpp.NS_OOB}

# The features transport's users will advertise
UserFeatures = TransportFeatures # we don't use them all, but it seems some clients don't query transports' users (?)
