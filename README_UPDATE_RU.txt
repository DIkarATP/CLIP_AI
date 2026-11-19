CLIP AI — Twitch Connector (same-origin dashboard)

УСТАНОВКА ОБНОВЛЕНИЯ
1. Закрой старое окно start.bat сочетанием Ctrl+C.
2. Распакуй содержимое этого архива в существующую папку clipai_twitch_connector.
3. Согласись заменить server.py и start.bat, если Windows спросит.
4. Важно: существующий файл .env НЕ удаляй и НЕ заменяй — в нём твои Twitch credentials.
5. Убедись, что рядом с server.py лежит index.html.
6. Запусти start.bat.
7. Открой в браузере http://127.0.0.1:8765/ (не открывай HTML двойным щелчком).

Проверка API: http://127.0.0.1:8765/api/twitch/status
Проверка LIVE: http://127.0.0.1:8765/api/twitch/streams?first=10

Эта версия отдаёт сайт и API с одного локального адреса, поэтому устраняет типичную проблему браузерного Failed to fetch при открытии HTML как file://.
Не публикуй .env и не отправляй Client Secret никому.
