#!/bin/bash
echo "Starting Hostile Object Estimation System..."

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
pip install -r requirements.txt

# Run the system
# Using python3 explicitly
python3 src/main.py
