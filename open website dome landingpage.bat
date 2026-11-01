@echo off
title Arch-Dome Landing Server
cd /d "%~dp0"

echo ========================================================
echo   Starting Arch-Dome Landing Page Local Server...
echo ========================================================

:: 1. تشغيل بايثون مباشرة من بيئة Anaconda الموجودة على جهازك
if exist "C:\Users\Liza\anaconda3\envs\dome_v1_env\python.exe" (
echo [OK] Using Anaconda dome_v1_env Python...
"C:\Users\Liza\anaconda3\envs\dome_v1_env\python.exe" server.py
goto done
)

:: 2. محاولة بايثون الأساسي في Anaconda
if exist "C:\Users\Liza\anaconda3\python.exe" (
echo [OK] Using Anaconda Base Python...
"C:\Users\Liza\anaconda3\python.exe" server.py
goto done
)

:: 3. محاولة مشغل ويندوز py
py server.py
if %errorlevel% equ 0 goto done

:: 4. محاولة عامة
python server.py

:done
pause