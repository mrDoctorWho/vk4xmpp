#
# Makefile
#
# this makefile is currently only used to make snapshots


VERSION=2.`git log --pretty=format:''|wc -l`
PACKAGE_VERSION=2
PROG=dpkg-deb
SOURCE=/tmp/vk4xmpp_build
FLAGS=--build
DEBTARGET=vk4xmpp_$(VERSION)-$(PACKAGE_VERSION)_all.deb
TARGET=vk4xmpp-$(VERSION)

DOCS=LICENSE README.md extensions.README.md

.PHONy: default
default:
	@echo "options are 'snapshot', 'clean', 'vk4xmpp-systemd-deb', 'vk4xmpp-initd-deb'"

.PHONY: hierarchy
hierarchy:
	rm -rf $(SOURCE)
	mkdir -p $(SOURCE)/usr/share/doc/vk4xmpp
	mkdir -p $(SOURCE)/usr/bin
	mkdir -p $(SOURCE)/var/lib/vk4xmpp
	mkdir -p $(SOURCE)/etc/vk4xmpp/conf.d
	mkdir -p $(SOURCE)/var/log/vk4xmpp
	mkdir -p $(SOURCE)/usr/lib/vk4xmpp
	mkdir -p $(SOURCE)/run/vk4xmpp
	cp gateway.py $(SOURCE)/usr/bin/vk4xmpp
	cp $(DOCS) $(SOURCE)/usr/share/doc/vk4xmpp
	cp Config_example.txt $(SOURCE)/etc/vk4xmpp/config
	cp -R library modules js extensions locales $(SOURCE)/usr/lib/vk4xmpp

vk4xmpp-systemd-deb: hierarchy
	cp -R DEBIAN $(SOURCE)/DEBIAN
	rm $(SOURCE)/DEBIAN/postinst.systemd
	mv $(SOURCE)/DEBIAN/postinst.initd $(SOURCE)/DEBIAN/postinst
	cp -R init.d $(SOURCE)/etc/init.d
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

debian_package_systemd: hierarchy
	cp -R DEBIAN $(SOURCE)/DEBIAN
	cp -R DEBIAN $(SOURCE)/DEBIAN
	rm $(SOURCE)/DEBIAN/postinst.initd
	mv $(SOURCE)/DEBIAN/postinst.systemd $(SOURCE)/DEBIAN/postinst
	mkdir -p $(SOURCE)/etc/systemd/system
	cp -R systemd/vk4xmpp.service.debian $(SOURCE)/etc/systemd/system/vk4xmpp.service
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

clean:
	rm -Rf $(SOURCE)
