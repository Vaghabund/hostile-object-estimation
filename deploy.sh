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
