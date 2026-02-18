@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo.
echo ========================================================
echo Hostile Object Estimation System - Windows Launcher
echo ========================================================
echo.

REM Create .env from .env.example if needed
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy ".env.example" ".env" >nul
        if !errorlevel! equ 0 (
            echo Created .env file. Please edit it with your Telegram bot token if needed.
            echo.
        ) else (
            echo Error: Failed to create .env
            pause
            exit /b 1
        )
    )
)

REM Check if .venv exists
if exist ".venv" (
    echo Virtual environment found. Continuing...
    goto :activate_venv
)

REM Create .venv with Python 3.11 or 3.12
echo Virtual environment not found. Creating with Python 3.11/3.12...
echo.

py -3.11 -m venv .venv >nul 2>&1
if !errorlevel! equ 0 (
    echo Created venv with Python 3.11
    goto :install_deps
)

py -3.12 -m venv .venv >nul 2>&1
if !errorlevel! equ 0 (
    echo Created venv with Python 3.12
    goto :install_deps
)

echo Error: Failed to create virtual environment.
echo.
echo This project requires Python 3.11 or 3.12 installed.
echo Please download from: https://www.python.org/downloads/
echo.
echo When installing, MAKE SURE TO CHECK: "Add Python to PATH"
pause
exit /b 1

:install_deps
echo.
.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
echo Installing dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo Error: Failed to install dependencies.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

:activate_venv
call .venv\Scripts\activate.bat >nul 2>&1

REM Run the application
echo Starting application...
echo.
.venv\Scripts\python.exe src/main.py
pause
