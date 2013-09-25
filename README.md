VK4XMPP Transport
======

VK4XMPP представляет собой легковесный транспорт. Из VK в XMPP и обратно.

Написан на языке программирования Python, все используемые библиотеки содержит в себе. 
Находится в состоянии тестирования. Требует Python 2.7.

Установка стандартна как и для любого другого транспорта. Только вот переименуйте Config_example.txt в Config.txt и заполните его.
На время тестирования рекомендуется заглядывать в папку транспорта и сообщать разработчику об ошибках (тела ошибок хранятся в папке crash).

**Возможности**:
* Прием и отправка сообщений;
* Авторизация по паролю или ключу «access-token», выдаваемому ВКонтакте;
* Пересланные сообщения;
* Вложения в сообщениях (только приём);
* Список друзей в ростере;
* Поддержка vCard для контактов;
* Поддержка конференций (групповых чатов, тестовая, не рекомендуется к использованию);
* Добавление в ростер новых, недавно добавленных друзей автоматически (в случае, если пользователь транспорта в это время был в сети, иначе следует вручную запросить подписку id@transport);
* Статистические данные о работе транспорта.

**Отличия от pyvk-t**:
* Транспорт не хранит паролей;
* Транспорт не парсит страницы, а использует API ВКонтакте;

**Список серверов, где уже установлен транспорт VK4XMPP**:
* vk.jabberik.ru
* vk.isida-bot.com
* vk.virtualtalk.org
* vkontakte.jabberon.ru
* vk.jabber-moscow.ru
* vk.beerseller.org
* vk.jabberid.org
* vk4xmpp.kap.sh
* vk.xmppserv.ru
* vk.jabbik.ru

Установка (для серверов): [Раз](http://is.gd/u0No4y) | [Два](http://is.gd/A22Qxz)

Регистрация: [Psi+](http://is.gd/ujPeZ8) | [Tkabber](http://dsy.name/?q=vk4xmpp) | [Gajim](http://xmppserv.ru/gajim/) | [Miranda](http://is.gd/q8ZfFP) | [QIP](http://is.gd/eLAt27) | [jTalk](http://is.gd/XkkdIl) | [Jimm](http://xmppserv.ru/jimm/) | [JasmineIM](http://xmppserv.ru/jasmine/)

Другое: [FAQ](http://is.gd/zgOMp9) | [Отзывы и предложения](http://vk4xmpp.userecho.com) | [Обсуждение на 4pda](http://is.gd/t10ZIc) | [Страница на JaWiki](http://jawiki.ru/Vk4xmpp)

Запуск:
python ./gateway.py

Обратиться к разработчику в сети xmpp можно в конференции [simpleapps@conference.jabber.ru](xmpp:simpleapps@conference.jabber.ru?join).

© simpleApps, 2013.