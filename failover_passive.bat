@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo Failover Guard (Passive)
echo ========================================
python failover_guard.py --role passive
pause
