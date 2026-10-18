@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m whisper.voice.chatterbox_setup --setup --choose
if errorlevel 1 pause
