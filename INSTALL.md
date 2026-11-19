# Установка CLIP AI на Windows

## 1. Подготовка
- Windows 10/11.
- Python 3.11 x64 и Python Launcher (`py`).
- Достаточно свободного места на диске для зависимостей, записей и клипов.
- Интернет.

Проверить Python:

```bat
py -3.11 --version
```

Ожидается Python 3.11.x.

## 2. Распаковка
Распакуйте репозиторий, например, в `D:\CLIP_AI`. Не распаковывайте поверх другой рабочей установки без резервной копии.

## 3. Twitch credentials
Скопируйте `.env.example` в `.env` и заполните:

```dotenv
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
```

Не добавляйте `.env` в Git.

## 4. Базовые зависимости
Запустите `setup.bat`. Он вызывает `py -3 -m pip install -r requirements.txt`.

Проверка:

```bat
py -3.11 -m pip show streamlink yt-dlp psutil
```

## 5. FFmpeg
Проверьте:

```bat
ffmpeg -version
ffprobe -version
```

Если команды не найдены, установите FFmpeg Essentials из надёжного источника или используйте уже установленную копию. Укажите папку `bin` в PATH или задайте переменную `CLIP_AI_FFMPEG_BIN` в `.env`.

## 6. Запуск
Запустите `start.bat`, затем откройте `http://127.0.0.1:8766`.

Проверьте:
- `http://127.0.0.1:8766/api/health`
- `http://127.0.0.1:8766/api/twitch/status`

## 7. YAMNet (необязательно)
Запустите `install_yamnet.bat`, затем `test_yamnet.bat`. Пакеты TensorFlow CPU и модель YAMNet могут занимать значительное место. Не устанавливайте их, если нужен только базовый Twitch Connector/Hunter.
