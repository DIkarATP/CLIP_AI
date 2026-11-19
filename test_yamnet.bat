@echo off
setlocal
cd /d "%~dp0"
py -3.11 -c "import numpy, soundfile, tensorflow as tf, tensorflow_hub as hub; print('NumPy:', numpy.__version__); print('TensorFlow:', tf.__version__); print('TF Hub:', hub.__version__); print('YAMNet dependencies: OK')"
if errorlevel 1 echo Dependencies are missing. Run install_yamnet.bat first.
pause
