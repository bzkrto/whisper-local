@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" whisper_bootstrap.py --mobile
pause
