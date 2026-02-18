@echo off
cd /d "%~dp0.."
.\.venv\Scripts\python.exe generate_template_data.py
pause