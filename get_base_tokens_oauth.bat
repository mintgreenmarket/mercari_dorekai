@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo BASE API Token Acquisition
echo ========================================
echo.
echo Starting OAuth authentication...
echo.
python get_base_tokens_oauth.py
pause
