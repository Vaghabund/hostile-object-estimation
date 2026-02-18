#!/bin/bash
# ========================================================
# Hostile Object Estimation System - Linux Launcher
# ========================================================
# This script provides one-click installation and startup:
# 
# FRESH INSTALLATION:
#   1. Creates .env from .env.example
#   2. Prompts for Telegram bot credentials (optional)
#   3. Creates Python virtual environment (.venv)
#   4. Installs all dependencies
#   5. Starts the system
# 
# NORMAL STARTUP:
#   1. Uses existing .env and .venv
#   2. Skips dependency installation if unchanged (marker file check)
#   3. Starts the system immediately
# 
# To force dependency reinstall: Delete .venv/.deps-installed
# ========================================================

# Change to script directory to handle execution from any location
cd "$(dirname "$0")" || { echo "Error: Failed to change to script directory"; exit 1; }

echo "Starting Hostile Object Estimation System..."

# --- Configuration Check ---
ENV_FILE=".env"
EXAMPLE_FILE=".env.example"

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
fi

# Function to check and prompt for variables
setup_variable() {
    local var_name=$1
    local prompt_msg=$2
    local placeholder=$3
    local is_secret=$4  # Optional: if "secret", hide input
    
    # Get current value from .env (using -F for literal string matching, -m1 to take the first match only)
    current_val=$(grep -m1 -F "$var_name=" "$ENV_FILE" | cut -d'=' -f2-)
    
    # If value is empty or still the placeholder, ask the user
    if [ -z "$current_val" ] || [ "$current_val" = "$placeholder" ]; then
        echo -n "$prompt_msg: "
        if [ "$is_secret" = "secret" ]; then
            # For sensitive data, don't echo input
            read -rs user_input
            echo  # Print newline after hidden input
        else
            read -r user_input
        fi
        if [ -n "$user_input" ]; then
            # Create a temporary file for safe atomic update
            temp_file=$(mktemp) || { echo "Error: Failed to create temporary file"; return 1; }
            # Replace the line while preserving all characters
            while IFS= read -r line || [ -n "$line" ]; do
                case "$line" in
                    "$var_name="*)
                        printf '%s=%s\n' "$var_name" "$user_input"
                        ;;
                    *)
                        printf '%s\n' "$line"
                        ;;
                esac
            done < "$ENV_FILE" > "$temp_file"
            # Atomic replacement
            mv "$temp_file" "$ENV_FILE" || { echo "Error: Failed to update .env file"; rm -f "$temp_file"; return 1; }
            echo "✅ $var_name updated."
        else
            # User skipped input - check if it's still a placeholder
            if [ "$current_val" = "$placeholder" ]; then
                if [ "$var_name" = "TELEGRAM_BOT_TOKEN" ] || [ "$var_name" = "AUTHORIZED_USER_ID" ]; then
                    echo "ℹ️  Telegram bot will be disabled. You can configure it later by editing .env"
                else
                    echo "⚠️  $var_name is still set to placeholder. Application may not work correctly."
                fi
            else
                echo "⚠️  Skipping $var_name (keeping current value)."
            fi
        fi
    fi
}

setup_variable "TELEGRAM_BOT_TOKEN" "Enter your Telegram Bot Token" "your_bot_token_here" "secret" || exit 1
setup_variable "AUTHORIZED_USER_ID" "Enter your Telegram User ID" "your_telegram_user_id_here" || exit 1

# --- Standard Deployment ---
# Check if venv exists
FIRST_RUN=0
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating .venv..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        echo "Please ensure Python 3.7+ is installed and available in PATH."
        exit 1
    fi
    echo "Virtual environment created successfully."
    FIRST_RUN=1
    echo
fi

# Activate venv
echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment."
    exit 1
fi

# --- Install/Update Dependencies ---
# Install on first run, if marker doesn't exist, or if requirements.txt is newer
NEEDS_INSTALL=0

if [ $FIRST_RUN -eq 1 ]; then
    NEEDS_INSTALL=1
    echo "Installing dependencies..."
elif [ ! -f ".venv/.deps-installed" ]; then
    NEEDS_INSTALL=1
    echo "Installing dependencies..."
else
    # Check if requirements.txt is newer than marker file
    if [ "requirements.txt" -nt ".venv/.deps-installed" ]; then
        NEEDS_INSTALL=1
        echo "Requirements have changed, updating dependencies..."
    fi
fi

if [ $NEEDS_INSTALL -eq 1 ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies."
        echo "Please check the error messages above and ensure:"
        echo "  - You have internet connectivity"
        echo "  - pip is working correctly"
        echo "  - All package versions in requirements.txt are available"
        exit 1
    fi
    touch .venv/.deps-installed
    echo "Dependencies installed successfully."
    echo
else
    echo "Dependencies already installed and up to date."
fi

# --- Run the System ---
echo
echo "Starting the system..."
echo
# Using python3 explicitly
python3 src/main.py
