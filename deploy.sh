#!/bin/bash
# ========================================================
# Hostile Object Estimation System - Linux Launcher
# ========================================================
# This script provides one-click installation and startup:
# 
# FRESH INSTALLATION:
#   1. Checks for required system dependencies (Python, git, etc.)
#   2. If dependencies missing, provides command to install them
#   3. Creates .env from .env.example
#   4. Runs interactive, validated Telegram setup (optional)
#   5. Creates Python virtual environment (.venv)
#   6. Installs all Python dependencies
#   7. Starts the system
# 
# NORMAL STARTUP:
#   1. Validates system dependencies
#   2. Uses existing .env and .venv
#   3. Skips dependency installation if unchanged (marker file check)
#   4. Starts the system immediately
# 
# To force dependency reinstall: Delete .venv/.deps-installed
# To start fresh: rm -rf .venv && ./deploy.sh
# ========================================================

# Change to script directory to handle execution from any location
cd "$(dirname "$0")" || { echo "Error: Failed to change to script directory"; exit 1; }

# --- Optional: re-run interactive Telegram setup only, then exit ---
if [ "$1" = "--setup" ] || [ "$1" = "--reconfigure" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required for setup. Install it with: sudo apt install -y python3"
        exit 1
    fi
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp ".env.example" ".env"
    fi
    python3 src/setup.py
    exit $?
fi

echo "Starting Hostile Object Estimation System..."

# --- System Dependencies Check ---
echo "Checking system dependencies..."
echo

MISSING_PACKAGES=()
INSTALL_CMD=""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    MISSING_PACKAGES+=("python3" "python3-pip" "python3-venv")
else
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ Python $PYTHON_VERSION found"
    
    # Check venv module
    if ! python3 -m venv --help &> /dev/null; then
        echo "❌ python3-venv module is missing"
        MISSING_PACKAGES+=("python3-venv")
    fi
fi

# Check git
if ! command -v git &> /dev/null; then
    echo "⚠️  Git is not installed (optional but recommended)"
    MISSING_PACKAGES+=("git")
fi

# If packages are missing, provide installation command
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo
    echo "=========================================="
    echo "Missing Required Dependencies"
    echo "=========================================="
    echo
    echo "Please run the following command to install missing packages:"
    echo
    echo "  sudo apt update && sudo apt install -y ${MISSING_PACKAGES[*]}"
    echo
    echo "After installation, run this script again: ./deploy.sh"
    echo "=========================================="
    echo
    exit 1
fi

echo
echo "✅ All system dependencies are installed"
echo

# --- Configuration Check ---
ENV_FILE=".env"
EXAMPLE_FILE=".env.example"
ENV_IS_NEW=0

if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$EXAMPLE_FILE" ]; then
        echo "Error: $EXAMPLE_FILE not found. Cannot create configuration."
        exit 1
    fi
    echo "Config file (.env) not found. Creating from example..."
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create $ENV_FILE from $EXAMPLE_FILE."
        echo "Please check file permissions, available disk space, and that the directory is writable."
        exit 1
    fi
    ENV_IS_NEW=1
fi

# Only run interactive Telegram setup on first run (when .env was just created)
if [ $ENV_IS_NEW -eq 1 ]; then
    echo
    echo "Launching interactive Telegram setup (optional)..."
    if ! python3 src/setup.py; then
        echo "⚠️  Telegram setup was skipped or failed."
        echo "    Run it later with: ./deploy.sh --setup   (or edit .env manually)"
    fi
else
    echo "✅ Using existing .env configuration. (Edit .env, or re-run ./deploy.sh --setup)"
fi

# --- Python Environment Check ---
echo
echo "Checking Python installation..."

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed."
    echo
    echo "Please install Python 3 with the following command:"
    echo "  sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
    echo
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"

# Check if venv module is available
if ! python3 -m venv --help &> /dev/null; then
    echo "❌ Error: Python venv module is not available."
    echo
    echo "Please install it with:"
    echo "  sudo apt install -y python3-venv"
    echo
    exit 1
fi

# --- Virtual Environment Setup ---
FIRST_RUN=0
VENV_VALID=0

# Check if venv directory exists
if [ -d ".venv" ]; then
    # Verify it's a valid venv by checking for activate script
    if [ -f ".venv/bin/activate" ]; then
        echo "✅ Virtual environment found."
        VENV_VALID=1
    else
        echo "⚠️  Virtual environment directory exists but appears to be incomplete or corrupted."
        echo "Removing and recreating virtual environment..."
        rm -rf .venv
        VENV_VALID=0
    fi
fi

# Create venv if it doesn't exist or was invalid
if [ $VENV_VALID -eq 0 ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv || {
        echo "❌ Error: Failed to create virtual environment."
        echo
        echo "Troubleshooting steps:"
        echo "  1. Ensure Python 3.7+ is installed: python3 --version"
        echo "  2. Ensure venv module is installed: sudo apt install python3-venv"
        echo "  3. Check disk space: df -h"
        echo "  4. Check write permissions: ls -la"
        echo
        exit 1
    }
    
    # Verify the venv was created successfully
    if [ ! -f ".venv/bin/activate" ]; then
        echo "❌ Error: Virtual environment was created but activation script is missing."
        echo "This may indicate a corrupted installation. Cleaning up..."
        rm -rf .venv
        exit 1
    fi
    
    echo "✅ Virtual environment created successfully."
    FIRST_RUN=1
    echo
fi

# Activate venv
echo "Activating virtual environment..."
source .venv/bin/activate || {
    echo "❌ Error: Failed to activate virtual environment."
    echo
    echo "The virtual environment may be corrupted. Try:"
    echo "  rm -rf .venv"
    echo "  ./deploy.sh"
    echo
    exit 1
}

# --- Install/Update Dependencies ---
# Install on first run, if marker doesn't exist, or if requirements.txt is newer
NEEDS_INSTALL=0

if [ $FIRST_RUN -eq 1 ]; then
    NEEDS_INSTALL=1
    echo "Installing dependencies (this may take a few minutes)..."
elif [ ! -f ".venv/.deps-installed" ]; then
    NEEDS_INSTALL=1
    echo "Dependencies marker not found. Installing dependencies..."
else
    # Check if requirements.txt is newer than marker file
    if [ "requirements.txt" -nt ".venv/.deps-installed" ]; then
        NEEDS_INSTALL=1
        echo "Requirements have changed, updating dependencies..."
    fi
fi

if [ $NEEDS_INSTALL -eq 1 ]; then
    # Ensure pip is up to date
    echo "Upgrading pip..."
    pip install --upgrade pip || {
        echo "⚠️  Warning: Failed to upgrade pip, continuing with existing version..."
    }
    
    # Install dependencies
    pip install -r requirements.txt || {
        echo "❌ Error: Failed to install dependencies."
        echo
        echo "Troubleshooting steps:"
        echo "  1. Check internet connectivity: ping -c 3 pypi.org"
        echo "  2. Try updating pip: pip install --upgrade pip"
        echo "  3. Try installing without cache: pip install --no-cache-dir -r requirements.txt"
        echo "  4. Install system dependencies:"
        echo "     sudo apt install -y python3-dev build-essential"
        echo
        echo "To retry installation, run: ./deploy.sh"
        echo "To force clean install, run: rm -rf .venv && ./deploy.sh"
        echo
        exit 1
    }
    
    # Mark dependencies as installed
    touch .venv/.deps-installed
    echo "✅ Dependencies installed successfully."
    echo
else
    echo "✅ Dependencies already installed and up to date."
fi

# --- Run the System ---
echo
echo "=========================================="
echo "Starting the system..."
echo "=========================================="
echo
# Using python3 explicitly
python3 src/main.py

# Capture exit code
EXIT_CODE=$?

echo
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ System exited normally."
else
    echo "⚠️  System exited with code $EXIT_CODE"
    echo
    echo "If you encountered errors, check:"
    echo "  - Camera permissions: sudo usermod -a -G video \$USER"
    echo "  - Display issues on headless server: install xvfb"
    echo "  - Configuration in .env file"
fi
echo "=========================================="

exit $EXIT_CODE
