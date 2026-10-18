@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Mevcut proje ortaminda .venv bulunamadi.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "whisper_bootstrap.py" --check-only
pause
