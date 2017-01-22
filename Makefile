GLOBAL_VERSION=3.0
PACKAGE_VERSION:=$(shell git describe --tags)
VERSION=$(GLOBAL_VERSION)+$(PACKAGE_VERSION)
PROG=dpkg-deb
SOURCE:=$(shell mktemp -d)
FLAGS=--build
DEBTARGET=vk4xmpp_$(VERSION)_all.deb
TARGET=vk4xmpp-$(VERSION)

DOCS=LICENSE README.md extensions.README.md

.PHONY: help hierarchy

help:
	@echo "VK4XMPP build script"
	@echo "===================="
	@echo "help - display this help and exit"
	@echo "init-package - build package with SysV flavour"
	@echo "systemd-package - build package with SystemD flavour"

hierarchy:
	mkdir -p $(SOURCE)/usr/share/doc/vk4xmpp
	mkdir -p $(SOURCE)/usr/bin
	mkdir -p $(SOURCE)/var/lib/vk4xmpp
	mkdir -p $(SOURCE)/etc/vk4xmpp/conf.d
	mkdir -p $(SOURCE)/var/log/vk4xmpp
	mkdir -p $(SOURCE)/usr/lib/vk4xmpp
	mkdir -p $(SOURCE)/run/vk4xmpp
	mkdir -p $(SOURCE)/DEBIAN
	cp DEBIAN/pre* $(SOURCE)/DEBIAN
	cat DEBIAN/control.template | sed s/VERSION/$(VERSION)/ > $(SOURCE)/DEBIAN/control
	cp gateway.py $(SOURCE)/usr/bin/vk4xmpp
	cp $(DOCS) $(SOURCE)/usr/share/doc/vk4xmpp
	cp Config_example.txt $(SOURCE)/etc/vk4xmpp/config.example
	cp -R library modules js extensions locales $(SOURCE)/usr/lib/vk4xmpp
	find $(SOURCE) -type f -name "*.py" -print0 | xargs -0 python -m compileall

init-package: hierarchy
	cp DEBIAN/postinst.initd $(SOURCE)/DEBIAN/postinst
	cp -R init.d $(SOURCE)/etc/init.d
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)

systemd-package: hierarchy
	cp $(SOURCE)/DEBIAN/postinst.systemd $(SOURCE)/DEBIAN/postinst
	mkdir -p $(SOURCE)/etc/systemd/system
	cp -R systemd/vk4xmpp.service.debian $(SOURCE)/etc/systemd/system/vk4xmpp.service
	fakeroot $(PROG) $(FLAGS) $(SOURCE) $(DEBTARGET)