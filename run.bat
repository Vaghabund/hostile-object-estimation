@echo off
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
    echo Created .env file. Please edit it with your Telegram bot token and user ID.
    echo You can skip Telegram configuration if you don't need bot functionality.
    echo.
)

REM --- Virtual Environment Setup ---
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
echo Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Warning: Some dependencies may not have installed correctly.
    echo The system will attempt to start anyway.
    echo.
)

REM --- Run the System ---
echo.
echo Starting the system...
echo.
python src/main.py

REM --- Pause on Exit ---
pause
