# coding: utf-8
# This file is a part of VK4XMPP transport
# © simpleApps, 2015.

## Installation:
# The plugin requires a field USER_LIFETIME_LIMIT in the main config file. Time must be formatted as text contains the time variable measurement.
# For example: USER_LIFETIME_LIMIT = "28y09M21d" means user will be removed after 28 years 9 Months 21 days from now
# You can wheter ignore or use any of these chars: smdMy.
# Used chars: s for seconds, m for minutes, d for days, M for months, y for years. The number MUST contain 2 digits as well.
# Note: if you won't set the field, plugin won't remove any user, but still will be gathering statistics.

"""
Watches for inactive users and removes them
"""


def user_activity_evt01():
	runDatabaseQuery("create table if not exists last_activity (jid text, date integer)", set=True)
	if isdef("USER_LIFETIME_LIMIT"):
		user_activity_remove()
	else:
		logger.warning("not starting inactive users remover because USER_LIFETIME_LIMIT is not set")
	import mod_iq_stats
	mod_iq_stats.STAT_FIELDS["users/seen"] = "users"
	mod_iq_stats.calcStats = calcStats


def user_activity_evt05(user):
	jid = user.source
	exists = runDatabaseQuery("select jid from last_activity where jid=?", (jid,), many=False)
	if not exists:
		runDatabaseQuery("insert into last_activity values (?, ?)", (jid, time.time()), set=True)
	else:
		runDatabaseQuery("update last_activity set date=? where jid=?", (time.time(), jid), set=True)


def user_activity_remove():
	users = runDatabaseQuery("select * from last_activity", many=True)
	LA = utils.TimeMachine(USER_LIFETIME_LIMIT)
	for (jid, date) in users:
		if (time.time() - date) >= LA:
			if jid not in Transport:
				runDatabaseQuery("delete from users where jid=?", (jid,), set=True)
				runDatabaseQuery("delete from last_activity where jid=?", (jid,))
				settings = "%s/%s" % (settingsDir, jid)
				if os.path.exists(settings):
					import shutil
					shutil.rmtree(settings)
				logger.info("user_activity: user has been removed from " \
				"the database because of inactivity more than %s (jid: %s)" % (LA, jid))
			else:
				sendMessage(Component, jid, TransportID, 
					_("Your last activity was more than %s seconds ago."
						" Relogin or you'll be exterminated.") % LA, LA)
	utils.runThread(user_activity_remove, delay=(60*60*24))

# A dirty hack to add seen users in stats
def calcStats():
	"""
	Returns count(*) from users database
	"""
	countOnline = len(Transport)
	countTotal = runDatabaseQuery("select count(*) from users", many=False)[0]
	countSeen = runDatabaseQuery("select count(*) from last_activity where date >=?", (startTime,), many=False)[0]
	return [countTotal, countSeen, countOnline]


registerHandler("evt01", user_activity_evt01)
registerHandler("evt05", user_activity_evt05)
