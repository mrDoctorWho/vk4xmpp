Installation
====

Add a field named ENABLE_PHOTO_HASHES in the main config file and set it's value to True in order to enable sending photo hashes. It will make the clients show the users photos (in case if user has the option enabled in their config). There are also two other options: PHOTO_REQUEST_LIMIT is a limit for one-time request (a number of users we can get avatars for per one request) and PHOTO_LIFE_DURATION is a duration of the time while photo hash will be considered as a fresh one.

Example:

```python
ENABLE_PHOTO_HASHES = True
PHOTO_REQUEST_LIMIT = 280
PHOTO_LIFE_DURATION = 604800
```