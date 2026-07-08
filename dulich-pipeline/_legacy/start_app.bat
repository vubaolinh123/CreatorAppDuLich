@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Tao video du lich theo Framework
echo   Dang khoi dong server...
echo ============================================

REM Khoi dong server trong cua so rieng
start "DuLich Server" ".venv\Scripts\python.exe" server.py

REM Cho server len roi mo trinh duyet
timeout /t 3 >nul
start "" http://localhost:7788

echo.
echo App da mo trong trinh duyet: http://localhost:7788
echo (Giu cua so "DuLich Server" mo trong khi dung app.)
echo Dong cua so "DuLich Server" la tat server.
