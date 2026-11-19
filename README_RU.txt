CLIP AI — Twitch Connector (локальный тест)

1. Установи Python 3.10 или новее с https://www.python.org/downloads/windows/
   Во время установки отметь галочку Add Python to PATH.
2. Скопируй файл .env.example и назови копию .env (именно .env, без .txt).
3. Открой .env Блокнотом.
4. Вставь Client ID и Client Secret из Twitch Developer Console:
   TWITCH_CLIENT_ID=твой_client_id
   TWITCH_CLIENT_SECRET=твой_client_secret
   Не добавляй кавычки. Не присылай .env никому и не загружай в GitHub.
5. Сохрани файл.
6. Дважды щёлкни start.bat. Оставь чёрное окно открытым.
7. Открой в браузере http://127.0.0.1:8765/api/twitch/status
   При успехе увидишь JSON с "connected": true.
8. Для проверки живых трансляций открой http://127.0.0.1:8765/api/twitch/streams?first=10

Важно:
- Это локальный сервер-посредник для безопасного хранения Client Secret. Он слушает только 127.0.0.1.
- На этом этапе подключается Twitch App Access Token и проверяется чтение публичных LIVE-стримов.
- Это ещё не скачивание VOD, не создание клипов и не авторизация от имени пользователя.
- Не публикуй файл .env и не отправляй его в чат.
