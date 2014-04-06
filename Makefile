#
# Makefile
#
# this makefile is currently only used to make snapshots


VERSION=2.152
PACKAGE_VERSION=2
PROG=dpkg-deb
SOURCE=/tmp/vk4xmpp_build
FLAGS=--build
DEBTARGET=vk4xmpp_$(VERSION)-$(PACKAGE_VERSION)_all.deb
TARGET=vk4xmpp-$(VERSION)

default:
	@echo "options are 'snapshot', 'clean'"


debian_package:
	rm -rf $(SOURCE)
	mkdir -p $(SOURCE)
	mkdir -p $(SOURCE)/usr/share/vk4xmpp
	cp -r . $(SOURCE)/usr/share/vk4xmpp
	rm -rf $(SOURCE)/usr/share/vk4xmpp/.git
	mkdir -p $(SOURCE)/etc
	mv $(SOURCE)/usr/share/vk4xmpp/DEBIAN $(SOURCE)
	mv $(SOURCE)/usr/share/vk4xmpp/init.d $(SOURCE)/etc/init.d
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

clean:
	rm -Rf tmp/*
