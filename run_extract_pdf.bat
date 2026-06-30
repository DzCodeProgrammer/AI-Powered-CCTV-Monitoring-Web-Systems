@echo off
cd /d "%~dp0"
venv\Scripts\python.exe scripts\extract_dahua_pdf.py
pause
