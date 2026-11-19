@echo off
setlocal
cd /d "%~dp0"
py -3.11 test_yamnet_recording.py
pause
