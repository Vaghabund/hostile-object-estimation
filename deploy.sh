#!/bin/bash
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
fi

# Function to check and prompt for variables
setup_variable() {
    local var_name=$1
    local prompt_msg=$2
    local placeholder=$3
    
    # Get current value from .env
    current_val=$(grep "^$var_name=" "$ENV_FILE" | cut -d'=' -f2-)
    
    # If value is empty or still the placeholder, ask the user
    if [ -z "$current_val" ] || [ "$current_val" = "$placeholder" ]; then
        echo -n "$prompt_msg: "
        read -r user_input
        if [ -n "$user_input" ]; then
            # Create a temporary file for safe atomic update
            temp_file=$(mktemp)
            # Replace the line while preserving all characters
            while IFS= read -r line; do
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
            mv "$temp_file" "$ENV_FILE"
            echo "✅ $var_name updated."
        fi
    fi
}

setup_variable "TELEGRAM_BOT_TOKEN" "Enter your Telegram Bot Token" "your_bot_token_here"
setup_variable "AUTHORIZED_USER_ID" "Enter your Telegram User ID" "your_telegram_user_id_here"

# --- Standard Deployment ---
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
