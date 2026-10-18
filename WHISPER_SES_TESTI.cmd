@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Mikrofon ve arka plan ogrenmesi acilmadan ucretsiz yerel ses deneniyor.
".venv\Scripts\python.exe" "whisper_bootstrap.py" --test-voice
echo.
pause
