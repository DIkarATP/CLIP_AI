# Диагностика CLIP AI

## `py` не найден
Установите Python 3.11 x64 с Python Launcher. Проверьте `py -3.11 --version`.

## `python` открывает Microsoft Store
В Windows может быть включён alias Microsoft Store. Проверяйте Python Launcher командой `py -3.11`, а не полагайтесь на `python`.

## `yt-dlp` не является командой
Проверьте пакет и запускайте модулем:

```bat
py -3.11 -m pip show yt-dlp
py -3.11 -m yt_dlp --version
```

## FFmpeg не найден
Проверьте наличие `ffmpeg.exe` и `ffprobe.exe`. Добавьте папку `bin` в PATH или задайте `CLIP_AI_FFMPEG_BIN`. Не скачивайте FFmpeg повторно, если он уже есть на диске.

## Twitch API не подключается
Проверьте наличие `.env` рядом с `server.py` и корректность переменных `TWITCH_CLIENT_ID` и `TWITCH_CLIENT_SECRET`. Не отправляйте содержимое `.env` помощнику. Проверьте `http://127.0.0.1:8766/api/twitch/status`.

## Worker не начинает запись
Проверьте `/api/worker/status`, источник, права, флаги `authorized`, `enabled`, `rights_confirmed`, доступность LIVE и наличие Streamlink. Worker не должен запускаться автоматически без намерения пользователя.

## MP4 не виден в селекторе записей
Обновите список файлов и проверьте, какие расширения реально перечисляет текущий `index.html`. Не переименовывайте MP4 в TS. Если интерфейс фильтрует только `.ts`, требуется отдельное исправление UI/API.

## Не удаляйте пользовательские данные
Не удаляйте `data/`, `recordings/`, `clips/`, `preview_cache/` и `.env` в качестве универсального способа исправления.
