# coding: utf-8

# BlackSmith-bot module.
# © simpleApps, 21.05.2012.
# This module contains main web\
# functions for site parsing.

import urllib, urllib2, re

UserAgents = {"OperaMini": "Opera/9.60 (J2ME/MIDP; Opera Mini/4.2.13337/724; U; ru)"} # Opera Mini 4.2 User-Agent

## HTML Unescape and <br> tag replace.
import htmlentitydefs

edefs = dict()

for Name, Numb in htmlentitydefs.name2codepoint.iteritems():
	edefs[Name] = unichr(Numb)

del Name, Numb

compile_ehtmls = re.compile("&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")

def uHTML(data):
	if data.count("&"):

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
				except:
					Char = edefs.get(Char, "&%s;" % co)
			else:
				Char = edefs.get(co, "&%s;" % co)
			return Char

		data = compile_ehtmls.sub(e_sb, data)
	data = re.sub("</?br */?>", "\n", data)
	return data
	
## Opening urls.
read_link = lambda link: urllib.urlopen(link).read()

def read_url(link, Browser = None):
	req = urllib2.Request(link)
	if Browser:
		req.add_header("User-agent", Browser)
	site = urllib2.urlopen(req)
	data = site.read()
	return data

## Parsing.
def re_search(body, s0, s2, s1 = "(?:.|\s)+"):
	comp = re.compile("%s(%s?)%s" % (s0, s1, s2), 16)
	body = comp.search(body)
	if body:
		body = (body.group(1)).strip()
	return body

## Get HTML tag.
def getTagData(tag, data, close_tag = 0):
	if not close_tag:
		close_tag = tag
	pattern = re.compile("<%(tag)s.*?>(.*?)</%(close_tag)s>" % vars(), flags=re.S+re.IGNORECASE)
	tagData = pattern.search(data)
	if tagData:
		tagData = tagData.group(1)
	return tagData or " "
	
def getTagArg(tag, argv, data, close_tag = 0):
	if not close_tag:
		close_tag = tag
	pattern = re.compile("<%(tag)s.? %(argv)s=[\"']?(.*?)[\"']?\">(.*?)</%(close_tag)s>" % vars(), flags=re.DOTALL|re.IGNORECASE)
	tagData = pattern.search(data)
	if tagData:
		tagData = tagData.group(1)
	return tagData or " "

def stripTags(data, subBy = str(), pattern = "<[^<>]+>"):
	pattern = re.compile(pattern)
	return pattern.sub(subBy, data)

## IDNA tool.
def IDNA(text, encode = True):
	if "://" in text:
		text = text.split("://")[1]
	if encode:
		text = unicode(text).encode("idna")
	else:
		text = unicode(text).decode("idna")
	return text
	
## Format size.
def byteFormat(size):
	if size < 1024: return '%sb' % int(size)
	for t in ('kB','MB','GB'):
		size = size / 1024.0
		if size < 1024: break
	return '%.2f%s' % (size,t)