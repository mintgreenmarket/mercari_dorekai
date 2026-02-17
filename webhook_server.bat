@echo off
chcp 65001
cd /d %~dp0
echo ========================================
echo Webhookサーバー起動中...
echo ========================================
echo.
echo メルカリWebhook: http://localhost:5000/webhook/mercari
echo BASEWebhook: http://localhost:5000/webhook/base
echo.
echo 停止するにはCtrl+Cを押してください
echo ========================================
python webhook_server.py
pause
