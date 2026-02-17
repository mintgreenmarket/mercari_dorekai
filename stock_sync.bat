@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo Stock Sync - Manual Execution
echo ========================================
python stock_sync.py
pause
