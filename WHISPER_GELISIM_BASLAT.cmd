@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Normal Whisper penceresini kapatin. Bu mod ses yerine arastirma ve kod gelistirme icindir.
echo Docker Desktop acik olmali. Eksik test imaji ilk calistirmada otomatik hazirlanir.
if not exist ".venv\Scripts\python.exe" (
    echo Mevcut whisper astra klasorunde .venv bulunamadi.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "whisper_bootstrap.py" --development
echo.
pause
