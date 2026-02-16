@echo off
echo Starting Hostile Object Estimation System...
if not exist ".venv" (
    echo Virtual environment not found. Please create it first.
    exit /b 1
)
call .venv\Scripts\activate
python src/main.py
pause
