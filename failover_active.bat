@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo Failover Guard (Active)
echo ========================================
python failover_guard.py --role active
pause
