@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo Stock Sync Scheduler (Auto-sync every 30 min)
echo ========================================
echo.
echo Press Ctrl+C to stop
echo ========================================
python stock_sync_scheduler.py
pause
