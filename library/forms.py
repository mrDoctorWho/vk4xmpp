# coding: utf-8

from __main__ import URL_ACCEPT_APP, VK_ACCESS, _

URL_ACCEPT_APP = URL_ACCEPT_APP % VK_ACCESS

class Forms:

	@classmethod
	def getSimpleForm(cls):
		form = []
		form.append({"var": "link", "type": "text-single",
			"label": _("Autorization page"), "value": URL_ACCEPT_APP})
		form.append({"var": "password", "type": "text-private",
			"label": _("Access-token"),
			"desc": _("Enter the access token")})
		return form

	@classmethod
	def getComlicatedForm(cls):
		form = cls.getSimpleForm()
		# This is why we have a fixed order
		form[1]["label"] = _("Password/Access-token")
		form[1]["desc"] = _("Enter the token or password")

		form.insert(1, {"var": "phone", "type": "text-single",
			"label": _("Phone number"), "value": "+",
			"desc": _("Enter phone number in format +71234567890")})
		form.insert(2, {"var": "use_password", "type": "boolean", 
			"label": _("Get access-token automatically"), 
			"desc": _("Tries to get access-token automatically. (It's recommended to use a token)")})
		return form

 
