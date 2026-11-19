@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Установка компонентов записи Twitch...
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Не удалось установить зависимости. Проверь интернет и версию Python.
  pause
  exit /b 1
)
echo.
echo Готово. Streamlink и yt-dlp установлены.
echo FFmpeg будет установлен отдельным шагом для обработки клипов.
pause
