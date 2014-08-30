VK4XMPP Transport
======

VK4XMPP представляет собой легковесный транспорт. Из VK в XMPP и обратно.

Написан на языке программирования Python, все используемые библиотеки содержит в себе.

**Транспорт требует Python 2.7+**.


**Возможности**:
* Прием и отправка сообщений
* Авторизация по паролю или ключу «access-token», выдаваемому ВКонтакте
* Пересланные сообщения
* Вложения в сообщениях (только приём)
* Список друзей в ростере
* Поддержка vCard для контактов
* Поддержка конференций (групповых чатов, тестовая, не рекомендуется к использованию)
* Добавление в ростер новых, недавно добавленных друзей автоматически (в случае, если пользователь транспорта в это время был в сети, иначе следует вручную запросить подписку id@transport)
* Статистические данные о работе транспорта
* Отправка изображений по стандарту XHTML-IM в сторону транспорта
* Проверка времени последней активности пользователя

**Отличия от pyvk-t**:
* Транспорт не хранит паролей
* Транспорт не парсит страницы, а использует API ВКонтакте

**Список поддерживаемых XEP**:
* XEP-0012 (Last Activity)
* XEP-0030 (Service Discovery)
* XEP-0039 (Statistics Gathering)
* XEP-0050 (Ad-Hoc Commands)
* XEP-0054 (vcard-temp)
* XEP-0071 (XHTML-IM)
* XEP-0077 (In-Band Registration)
* XEP-0085 (Chat State Notifications)
* XEP-0091 (Legacy Delayed Delivery)
* XEP-0092 (Software Version)
* XEP-0100 (Gateway Interaction)
* XEP-0158 (CAPTCHA Forms)
* XEP-0184 (Message Delivery Receipts)
* XEP-0199 (XMPP Ping)

**Список серверов, где уже установлен транспорт VK4XMPP**:
* vk.jabberik.ru
* vk.virtualtalk.org
* vkontakte.jabberon.ru
* vk.beerseller.org
* vk4xmpp.kap.sh
* vk.xmppserv.ru
* vk.jabbik.ru
* vk.matrixteam.org (English version)
* vk.helldev.net

Полный список можно посмотреть [здесь](http://xmppserv.ru/xmpp-monitor).


**Отдельное «спасибо»**:
* Alexey-cv (donate, продвижение посредством создания тем на 4pda, содание FAQ, написание большинства инструкций, тесты)
* alkorgun (предложения по лучшей реализации некоторых алгоритмов, код)
* Armageddon (сервера, тестирование, идеи, donate)
* boriz (donate)
* diSabler (мелкие исправления, форма капчи, логотип, donate)
* Manazius (инструкции, общение со смертными)
* nsof (donate, идеи)
* Santiago26 (тестирование ранних релизов, статья на Хабре)

Без этих людей не было бы транспорта таким, какой он есть.


Установка (для серверов): [Arch](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-на-ArchLinux-с-Prosody) | [Ubuntu/Debian/etc](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-(только-для-серверов)) | [Gentoo](http://blog.stv-fian.ru/?p=375)


Настройка jabber-серверов: [Ejabberd](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-(только-для-серверов)) | [Ejabberd (2)](http://nixman.info/?p=2315) | [Prosody](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-VK4XMPP-на-Prosody) | [Openfire](http://ky0uraku.livejournal.com/79921.html) | [Generic](http://dsy.name/?q=vk4xmpp)

Регистрация: [Psi+](http://is.gd/ujPeZ8) | [Tkabber](http://dsy.name/?q=vk4xmpp) | [Gajim](http://xmppserv.ru/gajim/) | [Miranda](http://is.gd/q8ZfFP) | [QIP](http://is.gd/eLAt27) | [jTalk](http://is.gd/XkkdIl) | [Jimm](http://xmppserv.ru/jimm/) | [JasmineIM](http://xmppserv.ru/jasmine/) | [Pidgin](http://xmppserv.ru/pidgin/) | [VacuumIM](http://xmppserv.ru/vacuum/) | [Kopete](http://xmppserv.ru/kopete/)

Обсуждения: [На 4pda](http://is.gd/t10ZIc) | [На форуме Ubuntu](http://forum.ubuntu.ru/index.php?topic=230041) | [На форуме Debian](http://debianforum.ru/index.php?topic=6037)

Другое: [FAQ](http://is.gd/zgOMp9) | [Отзывы и предложения](http://vk4xmpp.userecho.com) | [Страница на JaWiki](http://jawiki.ru/Vk4xmpp) | [Группа во ВКонтакте](https://vk.com/vk4xmpp)

Также рекомендуется заглянуть в [Wiki](https://github.com/mrDoctorWho/vk4xmpp/wiki/).

Запуск:
python ./gateway.py

Обратиться к разработчику в сети jabber можно в конференции [simpleapps@conference.jabber.ru](xmpp:simpleapps@conference.jabber.ru?join).



© simpleApps, 2013 — 2014.
