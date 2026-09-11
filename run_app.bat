@echo off
title AI Video Director
echo Menjalankan AI Video Director...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan kode error %errorlevel%.
    pause
)
