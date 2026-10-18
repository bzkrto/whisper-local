@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Ses uretimi ve arka plan ogrenmesi acilmadan mikrofon deneniyor.
".venv\Scripts\python.exe" "whisper_ses_v12.py" --test-stt --tts none
pause
