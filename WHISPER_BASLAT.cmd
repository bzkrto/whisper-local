@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Mevcut whisper astra klasorunde .venv bulunamadi.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "whisper_bootstrap.py" --text
if errorlevel 1 pause
