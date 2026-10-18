@echo off
chcp 65001 >nul
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 (
    echo Docker komutu bulunamadi. Test imaji olusturulmadi.
    pause
    exit /b 1
)
echo Yalniz docker-test klasorunden test ortami hazirlanacak. Ilk kurulum internet gerektirir.
docker build -t whisper-test:local "docker-test"
if errorlevel 1 echo Test ortami hazirlanamadi.
pause
