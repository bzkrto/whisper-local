@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Whisper .venv ortami bulunamadi. Bu dosyayi Whisper klasorunden calistirin.
  pause
  exit /b 1
)
echo Whisper kapali olmali. Secilen Chatterbox sesi ve ayri ses ortami kontrol edilecek.
".venv\Scripts\python.exe" -m whisper.voice.chatterbox_setup --setup --repair
if errorlevel 1 (
  echo Ses onarimi tamamlanamadi. Yukaridaki hata aciklamasini kontrol edin.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "whisper_bootstrap.py" --test-voice
echo Test tamamlandi. Ses geldiyse WHISPER_BASLAT.cmd ile acin.
pause
