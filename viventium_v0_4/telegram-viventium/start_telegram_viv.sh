#!/bin/bash
set -e

# ============================================================================
# Telegram-Viventium Bot Startup Script
# ============================================================================
# 
# RESOURCE OPTIMIZATION: To reduce CPU and memory usage, configure these
# settings in your config.env file:
#   - CONNECTION_POOL_SIZE (default: 8)
#   - GET_UPDATES_CONNECTION_POOL_SIZE (default: 8)
#   - TIMEOUT (default: 30 seconds)
#   - CONCURRENT_UPDATES (default: false)
#   - POLLING_TIMEOUT (default: 30 seconds)
#
# See config.env.example for detailed documentation on each setting.
# Defaults are optimized for small deployments (1-10 users).
#
# ============================================================================

# Load environment variables
# Use a safer method to load .env that ignores invalid lines
load_env() {
  local env_file="$1"
  echo "Loading .env from $env_file"
  while IFS= read -r line; do
    # Skip comments and empty lines
    if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
      continue
    fi
    
    # Remove inline comments (everything after #)
    line="${line%%#*}"
    # Trim whitespace
    line=$(echo "$line" | xargs)
    
    # Skip if empty after comment removal
    if [[ -z "$line" ]]; then
            continue
        fi
    
    # Split on first = sign
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      # Trim whitespace from key and value
      key=$(echo "$key" | xargs)
      value=$(echo "$value" | xargs)
    
    # Export valid keys
    if [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
       export "$key=$value"
      fi
    fi
  done < "$env_file"
}

if [ -f config.env ]; then
  load_env config.env
elif [ -f .env ]; then
  load_env .env
elif [ -f ../../.env ]; then
  load_env ../../.env
else
  echo "Warning: No .env file found."
fi

TELEGRAM_BACKEND="${VIVENTIUM_TELEGRAM_BACKEND:-librechat}"
if [ "$TELEGRAM_BACKEND" = "livekit" ]; then
  # Check for LiveKit credentials
  if [ -z "$LIVEKIT_URL" ] || [ -z "$LIVEKIT_API_KEY" ] || [ -z "$LIVEKIT_API_SECRET" ]; then
    echo "Error: LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in .env or environment."
    echo "These are required for the Telegram Bot to bridge to the Viventium Agent."
    exit 1
  fi
else
  if [ -z "$VIVENTIUM_TELEGRAM_USER_ID" ]; then
    echo "Warning: VIVENTIUM_TELEGRAM_USER_ID is not set. LibreChat auth will fail."
  fi
  if [ -z "$VIVENTIUM_TELEGRAM_SECRET" ] && [ -z "$VIVENTIUM_CALL_SESSION_SECRET" ]; then
    echo "Warning: VIVENTIUM_TELEGRAM_SECRET is not set. LibreChat auth will fail."
  fi
fi

# Check for Telegram Bot Token
if [ -z "$BOT_TOKEN" ]; then
  echo "Error: BOT_TOKEN (Telegram) must be set."
  exit 1
fi

echo "Starting Telegram-Viventium Bridge..."
echo "Mode: $TELEGRAM_BACKEND"
if [ "$TELEGRAM_BACKEND" = "livekit" ]; then
  echo "LiveKit URL: $LIVEKIT_URL"
else
  echo "LibreChat Origin: ${VIVENTIUM_LIBRECHAT_ORIGIN:-http://localhost:3180}"
fi

# Ensure dependencies are installed (optional check)
# uv pip install -r requirements.txt # If you have one

# Run the bot
cd TelegramVivBot
# Use uv to run the bot, ensuring dependencies (like python-telegram-bot, livekit) are installed
echo "Installing/Syncing dependencies..."
if command -v uv >/dev/null 2>&1; then
    uv run python bot.py
else
    echo "Error: 'uv' not found. Please install uv or run 'pip install -r requirements.txt' manually."
    python bot.py
fi
