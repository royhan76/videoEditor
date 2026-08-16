@echo off
title AI Video Director
echo Menjalankan AI Video Director menggunakan Python global...
"C:\Users\royha\AppData\Local\Programs\Python\Python312\python.exe" app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan kode error %errorlevel%.
    pause
)
