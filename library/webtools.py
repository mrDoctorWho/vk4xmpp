# coding: utf-8
# parts of code © alkogrun

import re
import htmlentitydefs

edefs = dict()

for Name, Numb in htmlentitydefs.name2codepoint.iteritems():
	edefs[Name] = unichr(Numb)

del Name, Numb, htmlentitydefs

compile_ehtmls = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")
compile_eol = re.compile(r"</?br */?>")

def uhtml(data):
	"""
	Unescapes escaped html characters
	"""
	if "&" in data:

		def e_sb(co):
			co = co.group(1)
			if co.startswith("#"):
				if chr(120) == co[1].lower():
					Char, c06 = co[2:], 16
				else:
					Char, c06 = co[1:], 10
				try:
					Numb = int(Char, c06)
					assert (-1 < Numb < 65535)
					Char = unichr(Numb)
				except Exception:
					Char = edefs.get(Char, "&%s;" % co)
			else:
				Char = edefs.get(co, "&%s;" % co)
			return Char

		data = compile_ehtmls.sub(e_sb, data)
	data = compile_eol.sub("\n", data)
	return data

def getTagArg(tag, argv, data, close_tag=""):
	close_tag = close_tag or tag
	pattern = re.compile(r"<%(tag)s.? %(argv)s=[\"']?(.*?)[\"']?\">(.*?)</%(close_tag)s>" % vars(), flags=re.DOTALL | re.IGNORECASE)
	tagData = pattern.search(data)
	if tagData:
		tagData = tagData.group(1)
	return tagData or " "

