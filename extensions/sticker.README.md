Installation
====

This plugin can work itself. Though, it has some useful settings.

The following are supported variables used to configure the plugin:

ENABLE_RGB_CONVERSION (boolean) can be True or False (removes Alpha channel, requires PIL)
RGB_CONVERSION_QUALITY (integer) from 0 to 100, where 0 is the worst quality you could have ever seen
STICKER_SIZE (string) can be 64, 128, 256. Where the number is the size of a sticker.

Note that these variables should be set in the config file.

Example:

```python
ENABLE_RGB_CONVERSION = True
RGB_CONVERSION_QUALITY = 100
STICKER_SIZE = "128"
```