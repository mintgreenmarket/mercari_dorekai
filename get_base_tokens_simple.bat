@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo BASE API Token Acquisition (Simple)
echo ========================================
echo.
python get_base_tokens_simple.py
pause
