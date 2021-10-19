Installation
====

The extension “groupchats” requires up to 3 fields in the main config:

1. ConferenceServer — the address of your (or not your?) conference server

Bear in mind that there can be limits on the jabber server for conference per jid. Read the wiki for more details.

2. CHAT_USERS_LIMIT — the limit of users per chat. 30 is the default.

3. CHAT_LIFETIME_LIMIT — the limit of the time after that chat considered inactive and will be removed. Time must be formatted as text and contain the time measurement variables after the digits.


For example:

```python
CHAT_LIFETIME_LIMIT = "28y09M21d"
```

Will make chats that were used 28 years 9 Months 21 ago deleted.

You can wheter ignore or use any of these chars: *smdMy*. Those are the time measurement variables.

Supported measurements: s for seconds, m for minutes, d for days, M for months, y for years.

The number MUST contain 2 digits as well.

Note: if you won't set the field, plugin won't remove any chat, but still will be gathering statistics and groupchats would work fine anyways.
