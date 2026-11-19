@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo CLIP AI - YAMNet dependency installer
echo Python 3.11 x64 and internet connection required.
echo ==========================================
where py >nul 2>nul
if errorlevel 1 goto no_python
py -3.11 --version
if errorlevel 1 goto no_py311
py -3.11 -m pip install --upgrade pip
if errorlevel 1 goto failed
py -3.11 -m pip install numpy==1.26.4 soundfile==0.12.1 tensorflow-cpu==2.15.1 tensorflow-hub==0.16.1
if errorlevel 1 goto failed
echo.
echo Installation completed successfully.
echo Run test_yamnet.bat next.
pause
exit /b 0
:no_python
echo Python launcher "py" was not found.
goto failed
:no_py311
echo Python 3.11 was not found. Install Python 3.11 x64 with the Python Launcher.
goto failed
:failed
echo.
echo Installation failed. Read the error above.
pause
exit /b 1
