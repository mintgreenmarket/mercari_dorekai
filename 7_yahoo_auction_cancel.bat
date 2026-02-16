@echo off
chcp 65001
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python 7_yahoo_auction_cancel.py
pause
