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

REM Check Python installation
echo Checking Python installation...
echo.

py --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [X] Error: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.7+ from: https://www.python.org/downloads/
    echo.
    echo IMPORTANT: When installing, CHECK the box "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Display Python version
for /f "tokens=*" %%i in ('py --version') do set PYTHON_VERSION=%%i
echo [OK] Found !PYTHON_VERSION!
echo.

REM Check if virtual environment exists and is valid
set VENV_VALID=0
set FIRST_RUN=0

if exist ".venv" (
    REM Check if activate script exists (indicates valid venv)
    if exist ".venv\Scripts\activate.bat" (
        echo [OK] Virtual environment found.
        set VENV_VALID=1
        goto :install_deps
    ) else (
        echo [!] Virtual environment directory exists but appears corrupted.
        echo [!] Removing and recreating virtual environment...
        echo.
        rd /s /q ".venv" 2>nul
        set VENV_VALID=0
    )
) else (
    echo Virtual environment not found.
    set VENV_VALID=0
)

REM Create venv if invalid or missing
if !VENV_VALID! equ 0 (
    echo Creating virtual environment...
    echo.
    
    REM Try Python 3.11 first
    py -3.11 -m venv .venv >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Created venv with Python 3.11
        set FIRST_RUN=1
        goto :verify_venv
    )
    
    REM Try Python 3.12
    py -3.12 -m venv .venv >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Created venv with Python 3.12
        set FIRST_RUN=1
        goto :verify_venv
    )
    
    REM Try Python 3.10
    py -3.10 -m venv .venv >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Created venv with Python 3.10
        set FIRST_RUN=1
        goto :verify_venv
    )
    
    REM Try default Python
    py -m venv .venv >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Created venv with default Python
        set FIRST_RUN=1
        goto :verify_venv
    )
    
    REM All attempts failed
    echo [X] Error: Failed to create virtual environment.
    echo.
    echo Troubleshooting steps:
    echo   1. Ensure Python 3.7+ is installed: py --version
    echo   2. Reinstall Python with "Add to PATH" option checked
    echo   3. Check disk space and write permissions
    echo   4. Try running as Administrator
    echo.
    pause
    exit /b 1
)

:verify_venv
REM Verify the venv was created successfully
if not exist ".venv\Scripts\activate.bat" (
    echo [X] Error: Virtual environment creation failed - activation script missing.
    echo [!] Cleaning up corrupted installation...
    rd /s /q ".venv" 2>nul
    echo.
    echo Please try running the script again. If the problem persists:
    echo   - Check available disk space
    echo   - Run as Administrator
    echo   - Temporarily disable antivirus
    echo.
    pause
    exit /b 1
)
echo.
goto :install_deps

:install_deps
REM Check if dependencies need to be installed
set NEEDS_INSTALL=0

if !FIRST_RUN! equ 1 (
    echo Installing dependencies ^(this may take a few minutes^)...
    set NEEDS_INSTALL=1
) else if not exist ".venv\.deps-installed" (
    echo Dependencies marker not found. Installing dependencies...
    set NEEDS_INSTALL=1
) else (
    REM Check if requirements.txt is newer than marker file
    for %%A in (requirements.txt) do set REQ_TIME=%%~tA
    for %%A in (.venv\.deps-installed) do set MARKER_TIME=%%~tA
    
    if "!REQ_TIME!" gtr "!MARKER_TIME!" (
        echo Requirements have changed, updating dependencies...
        set NEEDS_INSTALL=1
    )
)

if !NEEDS_INSTALL! equ 1 (
    echo.
    echo Upgrading pip...
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    if !errorlevel! neq 0 (
        echo [!] Warning: Failed to upgrade pip, continuing with existing version...
    )
    
    echo Installing dependencies from requirements.txt...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo [X] Error: Failed to install dependencies.
        echo.
        echo Troubleshooting steps:
        echo   1. Check internet connectivity: ping pypi.org
        echo   2. Try running as Administrator
        echo   3. Check firewall/antivirus settings
        echo   4. Try: .venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
        echo.
        echo To retry: Run this script again
        echo To force clean install: Delete .venv folder and run again
        echo.
        pause
        exit /b 1
    )
    
    REM Create marker file
    echo. > .venv\.deps-installed
    echo [OK] Dependencies installed successfully.
    echo.
) else (
    echo [OK] Dependencies already installed and up to date.
    echo.
)

goto :activate_venv

:activate_venv
call .venv\Scripts\activate.bat >nul 2>&1
if !errorlevel! neq 0 (
    echo [X] Error: Failed to activate virtual environment.
    echo.
    echo The virtual environment may be corrupted. Try:
    echo   1. Delete the .venv folder
    echo   2. Run this script again
    echo.
    pause
    exit /b 1
)

REM Run the application
echo.
echo ==========================================
echo Starting application...
echo ==========================================
echo.
.venv\Scripts\python.exe src/main.py

REM Capture exit code
set EXIT_CODE=!errorlevel!

echo.
echo ==========================================
if !EXIT_CODE! equ 0 (
    echo [OK] Application exited normally.
) else (
    echo [!] Application exited with code !EXIT_CODE!
    echo.
    echo If you encountered errors, check:
    echo   - Camera permissions and availability
    echo   - Configuration in .env file
    echo   - Requirements: webcam or video source needed
    echo.
    echo For more help, check the README.md file
)
echo ==========================================
echo.
pause
exit /b !EXIT_CODE!
