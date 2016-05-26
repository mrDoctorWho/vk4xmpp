# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

"""
Contain all default variables used by VK4XMPP
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

IDENTIFIER = {"type": "vk", "category": "gateway", "name": "VK4XMPP Transport"}
URL_ACCEPT_APP = "http://jabberon.ru/vk4xmpp.html#%d"
VK4XMPP_MONITOR_SERVER = "anon.xmppserv.ru"
VK4XMPP_MONITOR_URL = "http://xmppserv.ru/xmpp-monitor/hosts.php"
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
evalJID = ""
AdditionalAbout = ""
allowBePublic = True

# The features transport will advertise
TransportFeatures = {xmpp.NS_DELAY}

# The features transport's users will advertise
UserFeatures = {xmpp.NS_CHATSTATES, xmpp.NS_LAST}