[![Code Climate](https://codeclimate.com/github/mrDoctorWho/vk4xmpp/badges/gpa.svg)](https://codeclimate.com/github/mrDoctorWho/vk4xmpp)

[![VK4XMPP on Ohloh](https://www.openhub.net/p/vk4xmpp/widgets/project_partner_badge.gif)](https://www.openhub.net/p/vk4xmpp)

**[Fork Me](https://github.com/mrDoctorWho/vk4xmpp/fork) Now! Spread the project for great good!**


VK4XMPP Transport
======

VK4XMPP представляет собой легковесный транспорт[¹](https://github.com/mrDoctorWho/vk4xmpp#wtf). Из VK в XMPP [²](https://github.com/mrDoctorWho/vk4xmpp#wtf) и обратно. Написан на языке программирования Python (совместим только со второй веткой).


**<a name="features"></a>Возможности**:
* **Аватары у пользователей** (во vCard и при входе в сеть, по стандарту XEP-0153)
* **Long Poll (обо всех событиях пользователь уведомляется незамедлительно)**
* **Поддержка групп (меток для друзей ВКонтакте) в ростере**
* **Поддержка конференций** (групповых чатов)
* **Отправка изображений в сторону транспорта** (XEP-0071: XHTML-IM)
* Вложения в сообщениях (только приём)
* Пересланные сообщения (и вложения в них)
* Прием и отправка сообщений
* Авторизация по паролю или ключу «access-token», выдаваемому ВКонтакте
* Список друзей в ростере
* Поддержка vCard для контактов
* Добавление в ростер новых, недавно добавленных друзей автоматически (в случае, если пользователь транспорта в это время был в сети, иначе следует вручную запросить подписку id@transport)
* Статистические данные о работе транспорта
* Проверка времени последней активности пользователя
* Настройка транспорта пользователем «под себя» посредством AdHoc-команд [³](https://github.com/mrDoctorWho/vk4xmpp#wtf)
* Отправка изображения капчи по стандарту XEP-0158 (поддерживается в Tkabber)
* Администрирование посредством AdHoc-команд
* Поддержка плагинов

**Отличия от pyvk-t**:
* Транспорт не хранит паролей
* Транспорт не парсит страницы, а использует API ВКонтакте

**<a name="xep"></a>Список поддерживаемых XEP**:

* XEP-0012 (Last Activity)
* XEP-0030 (Service Discovery)
* XEP-0039 (Statistics Gathering)
* XEP-0045 (Multi-User Chat)
* XEP-0050 (Ad-Hoc Commands)
* XEP-0054 (vcard-temp)
* XEP-0066 (Out of Band Data)
* XEP-0071 (XHTML-IM)
* XEP-0077 (In-Band Registration)
* XEP-0153 (vCard-Based Avatars)
* XEP-0085 (Chat State Notifications)
* XEP-0091 (Legacy Delayed Delivery)
* XEP-0092 (Software Version)
* XEP-0100 (Gateway Interaction)
* XEP-0158 (CAPTCHA Forms)
* XEP-0184 (Message Delivery Receipts)
* XEP-0199 (XMPP Ping)
* XEP-0333 (Chat Markers)

**Почему VK4XMPP**:

В конце 2013 года администрация «ВКонтакте» приняла решение отказаться от официальной поддержки протокола XMPP.
Это событие было воспринято разными пользователями по-разному. Тем, кто уже был знаком с XMPP, его возможностями и удобством некоторых клиентов, это не понравилось.

«**VK4XMPP**», подоспевший прямо к остановке XMPP-сервера «ВКонтакте», выполнявшего роль пересылки сообщений из/в социальную сеть, был тепло принят бывшими пользователями официального сервиса. С самого момента первого релиза транспорт предоставлял намного больше возможностей, чем бывший официальный вариант.

Причины попробовать VK4XMPP:

* Удобство: чтобы использовать VK4XMPP вам нужен XMPP-клиент и jabber-аккаунт. Клиентов очень много и все разные. Любой найдёт что-то, что ему понравится.
* Скорость работы: VK4XMPP использует прямые HTTP-запросы к API «ВКонтакте», которые, в основном, не превышают и килобайта.
* Экономия трафика: Несмотря на большой расход трафика на присутствия в XMPP, ваш XMPP-клиент передаст в десятки раз меньше данных, нежели браузер.
* Экономия оперативной памяти устройства: Вы когда-нибудь задумывались, сколько памяти «съедает» браузер? Посмотрите. А теперь посмотрите на XMPP-клиент. Браузер — гораздо более сложная программа, чем XMPP-клиент. Оставьте чаты специализированному софту.
* Вы параноик: Вы видите опасность раскрытия личных данных везде и всюду, но всё же пользуетесь социальной сетью (вероятно, под другим именем, ведь вы параноик). Что, по-вашему, безопаснее? Простой XMPP-клиент или же браузер? Помимо этого вы можете пропускать **зашифрованные сообщения** через jabber и сервера ВКонтакте с использованием **OTR**. Поддержка OTR не требуется от транспорта. Для этого вам и вашему собеседнику нужен клиент с поддержкой OTR, например, [Psi+](http://psi-plus.com) или [Gajim](http://gajim.org).

Причины сбежать в ужасе:

* Сложная форма регистрации: Как ни крути, а регистрация (при условии наличия Jabber-ID) на транспорте состоит аж из 3-х пунктов! Вы потратите **целую** минуту на регистрацию, а может даже две!
* Отсутствие некоторых возможностей: К сожалению, не всё можно реализовать в текущем варианте XMPP и состоянии XMPP-клиентов. Так например, вы не сможете переслать сообщения другу от другого пользователя. И это не всё.
* *Вы параноик: Бегите и не возвращайтесь. Никогда.*

**Как вы можете помочь**:

1. Вы — программист. Каждая функция vk4xmpp содержит строки документации. Также есть [пример](https://github.com/mrDoctorWho/vk4xmpp/blob/master/extensions/.example.py) написания плагина, описывающий все возможности системы плагинов. При желании, написать что-то не составит труда. Pull-request'ы приветствуются.

2. Вы — активный пользователь социальной сети «ВКонтакте» или Jabber, которому просто нравится транспорт. Приглашайте своих друзей попробовать VK4XMPP!

3. Вы — пользователь, которому просто нравится проект и/или определённый запущенный сервис. Транспорты, впрочем как и сервера (в основном), запущены энтузиастами на некоммерческой основе, люди оплачивают их из своего кармана. Сделайте пожертвование своему серверу! *(администраторам: в файле конфигурации для этого есть поле AdditionalAbout)*


<a name="servers"></a>**Список серверов, где установлен VK4XMPP**:

* vk.jabberik.ru
* vkontakte.jabberon.ru
* vk.beerseller.org
* vk.kap.sh
* vk.jabbik.ru
* vk.opiums.eu
* vk.stv-fian.ru

Полный список можно посмотреть [здесь](http://anon.stv-fian.ru).


<a name="thanks"></a>**Благодарности**:

* Алексей «Snake» Нежданов (библиотека xmpppy)
* Alexey-cv (donate, продвижение посредством создания тем на 4pda, содание FAQ, написание большинства инструкций, тестирование)
* alkorgun (предложения по лучшей реализации некоторых алгоритмов, код)
* Armageddon (сервера, тестирование, идеи, donate)
* boriz (donate)
* diSabler (мелкие исправления, форма капчи, логотип, donate)
* Manazius (инструкции, общение со смертными)
* nsof (donate, идеи, тестирование)
* Santiago26 (тестирование ранних релизов, статья на Хабре)
* aawray ([xmpp-monitor](https://github.com/aawray/xmpp-monitor))

А также всем, кто как-либо участвовал в жизни транспорта. Без вас не было бы транспорта таким, какой он есть.

Полный список разработчиков можно посмотреть [здесь](https://github.com/mrDoctorWho/vk4xmpp/graphs/contributors).

<a name="installation"></a>Установка (для серверов):

* [Arch Linux](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-на-ArchLinux-с-Prosody)
* [Gentoo](http://blog.stv-fian.ru/?p=375)
* [Ubuntu/Debian/etc](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-(для-серверов))


<a name="configure"></a>Настройка jabber-серверов:

* Ejabberd: [раз](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-(только-для-серверов)), [два](http://nixman.info/?p=2315)
* [Openfire](http://ky0uraku.livejournal.com/79921.html)
* [Prosody](https://github.com/mrDoctorWho/vk4xmpp/wiki/Установка-VK4XMPP-на-Prosody)
* [Generic](http://dsy.name/?q=vk4xmpp)


<a name="register"></a>Регистрация:

* [Gajim](http://j-cool.ru/vk4xmpp/gajim.html)
* ~~[JasmineIM](http://xmppserv.ru/jasmine/)~~
* ~~[Jimm](http://xmppserv.ru/jimm/)~~
* [jTalk](http://jabberon.ru/articles/2014/12/12/транспорт-вконтакте-подключение-через-jtalk/)
* ~~[Kopete](http://xmppserv.ru/kopete/)~~
* [Miranda](http://is.gd/5dAduL)
* [Pidgin](http://xubuntu-ru.net/how-to/129-podklyuchenie-k-transportu-vk4xmpp-s-pomoschyu-klienta-pidgin.html)
* [Psi+](http://is.gd/VwlK5R)
* [QIP](http://is.gd/xrjvfF)
* [Talkonaut](http://is.gd/OxJdMK)
* [Tkabber](http://dsy.name/?q=vk4xmpp)
* ~~[VacuumIM](http://xmppserv.ru/vacuum/)~~


<a name="talk"></a>Обсуждения:

* ~~[На 4pda](http://is.gd/t10ZIc)~~
* [На форуме Debian](http://debianforum.ru/index.php?topic=6037)
* [На форуме Ubuntu](http://forum.ubuntu.ru/index.php?topic=230041)


<a name="other"></a>Другое:
* [FAQ](http://is.gd/qqCI81)
* [Группа во ВКонтакте](https://vk.com/vk4xmpp)
* [Страница на JaWiki](http://jawiki.ru/Vk4xmpp)

Также рекомендуется заглянуть в [Wiki](https://github.com/mrDoctorWho/vk4xmpp/wiki/).

Запуск:
python ./gateway.py

Обратиться к разработчику в сети jabber можно в конференции simpleapps@conference.helldev.net.

**<a name="wtf"></a>WTF**:

1. Транспорт — Программное Обеспечение, обеспечивающее связь между различными протоколами мгновенного обмена сообщениями. Распространены в XMPP (Jabber).

2. XMPP (Jabber) — Расширяемый протокол мгновенного обмена сообщениями ([Wikipedia/XMPP](https://wikipedia.org/wiki/XMPP)).

3. К сожалению, нет нормальной инструкции; см. [JabberON/AdHoc](http://jabberon.ru/articles/2015/03/18/транспорт-вконтакте-дополнительные-команды/) и [JaWiki/AdHoc](http://jawiki.ru/Adhoc).

© simpleApps, 2013 — 2017.
