@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo BASE API Product Fetcher
echo ========================================
python base_products_fetcher.py
echo.
echo Complete: products_base.csv
pause
