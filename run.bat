@echo off
REM ========================================================
REM Hostile Object Estimation System - Windows Launcher
REM ========================================================
REM This script provides one-click installation and startup:
REM 
REM FRESH INSTALLATION:
REM   1. Creates .env from .env.example
REM   2. Creates Python virtual environment (.venv)
REM   3. Installs all dependencies
REM   4. Starts the system
REM 
REM NORMAL STARTUP:
REM   1. Uses existing .env and .venv
REM   2. Skips dependency installation if unchanged (marker file check)
REM   3. Starts the system immediately
REM 
REM To force dependency reinstall: Delete .venv\.deps-installed
REM ========================================================

REM Change to script directory to handle execution from any location
cd /d "%~dp0"

echo Starting Hostile Object Estimation System...

REM --- Configuration Check ---
set ENV_FILE=.env
set EXAMPLE_FILE=.env.example

if not exist "%ENV_FILE%" (
    if not exist "%EXAMPLE_FILE%" (
        echo Error: %EXAMPLE_FILE% not found. Cannot create configuration.
        pause
        exit /b 1
    )
    echo Config file (.env) not found. Creating from example...
    copy "%EXAMPLE_FILE%" "%ENV_FILE%" >nul
    if errorlevel 1 (
        echo Error: Failed to create "%ENV_FILE%" from "%EXAMPLE_FILE%".
        echo Please check file permissions, available disk space, and that the directory is writable.
        pause
        exit /b 1
    )
    echo Created .env file. Please edit it with your Telegram bot token and user ID.
    echo You can skip Telegram configuration if you don't need bot functionality.
    echo.
)

REM --- Virtual Environment Setup ---
set FIRST_RUN=0
if not exist ".venv" (
    echo Virtual environment not found. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        echo Please ensure Python 3.7+ is installed and available in PATH.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
    set FIRST_RUN=1
    echo.
)

REM --- Activate Virtual Environment ---
echo Activating virtual environment...
call .venv\Scripts\activate
if errorlevel 1 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM --- Install/Update Dependencies ---
REM Install on first run, if marker doesn't exist, or if requirements.txt is newer
set NEEDS_INSTALL=0

if %FIRST_RUN%==1 (
    set NEEDS_INSTALL=1
    echo Installing dependencies...
) else if not exist ".venv\.deps-installed" (
    set NEEDS_INSTALL=1
    echo Installing dependencies...
) else (
    REM Check if requirements.txt is newer than marker file using xcopy date comparison
    echo n | xcopy /d /l /y requirements.txt .venv\.deps-installed >nul 2>&1
    if not errorlevel 1 (
        set NEEDS_INSTALL=1
        echo Requirements have changed, updating dependencies...
    )
)

if %NEEDS_INSTALL%==1 (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies.
        echo Please check the error messages above and ensure:
        echo   - You have internet connectivity
        echo   - pip is working correctly
        echo   - All package versions in requirements.txt are available
        pause
        exit /b 1
    )
    type nul > .venv\.deps-installed
    echo Dependencies installed successfully.
    echo.
) else (
    echo Dependencies already installed and up to date.
)

REM --- Run the System ---
echo.
echo Starting the system...
echo.
python src/main.py

REM --- Pause on Exit ---
pause
