@echo off
set "WHISPER_TS=tailscale"
where tailscale >nul 2>nul
if errorlevel 1 (
  set "WHISPER_TS=%ProgramFiles%\Tailscale\tailscale.exe"
)
"%WHISPER_TS%" status
if errorlevel 1 (
  echo Tailscale kurulu ve oturum acik olmali. V19 notlarindaki mobil kurulumu uygulayin.
  pause
  exit /b 1
)
"%WHISPER_TS%" serve --bg http://127.0.0.1:8765
"%WHISPER_TS%" serve status
pause
