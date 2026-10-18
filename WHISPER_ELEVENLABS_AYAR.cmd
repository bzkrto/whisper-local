@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Whisper Python ortami bulunamadi.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m whisper.voice.elevenlabs_tts
if errorlevel 1 pause
