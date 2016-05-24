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

default:
	@echo "options are 'snapshot', 'clean', 'debian_package_initd', 'debian_package_systemd'"


debian_package_initd:
	rm -rf $(SOURCE)
	mkdir -p $(SOURCE)/usr/share/vk4xmpp
	cp -r . $(SOURCE)/usr/share/vk4xmpp
	rm -rf $(SOURCE)/usr/share/vk4xmpp/.git
	mkdir -p $(SOURCE)/etc
	mv $(SOURCE)/usr/share/vk4xmpp/DEBIAN_INITD $(SOURCE)/DEBIAN
	mv $(SOURCE)/usr/share/vk4xmpp/init.d $(SOURCE)/etc/init.d
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

debian_package_systemd:
	rm -rf $(SOURCE)
	mkdir -p $(SOURCE)/usr/share/vk4xmpp
	cp -r . $(SOURCE)/usr/share/vk4xmpp
	rm -rf $(SOURCE)/usr/share/vk4xmpp/.git
	mv $(SOURCE)/usr/share/vk4xmpp/DEBIAN_SYSTEMD $(SOURCE)/DEBIAN
	mkdir -p $(SOURCE)/etc/systemd/system
	mv $(SOURCE)/usr/share/vk4xmpp/systemd/vk4xmpp.service.debian $(SOURCE)/etc/systemd/system/vk4xmpp.service
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

clean:
	rm -Rf $(SOURCE)
