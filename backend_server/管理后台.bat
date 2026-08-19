@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   ClassTrack.com 管理后台 (PyQt6)
echo ============================================
cd /d "%~dp0"
python admin_app.py
pause
