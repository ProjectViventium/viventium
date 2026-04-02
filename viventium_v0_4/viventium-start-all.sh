#!/bin/bash
# === VIVENTIUM START - Unified LibreChat + LiveKit Voice Call Stack ===
#
# Legacy helper for voice-call testing.
# The canonical product entrypoint is now:
#   ../bin/viventium start
#
# Current isolated defaults:
#   1. MongoDB (native, port 27117)
#   2. LiveKit Server (native, port 7888)
#   3. LibreChat Backend (port 3180)
#   4. LibreChat Frontend Dev (port 3190)
#   5. Viventium Modern Playground (port 3300)
#
# Usage: ./viventium-start-all.sh [options]
#
# Options:
#   --build           Force rebuild LibreChat packages
#   --clean           Clean build and rebuild
#   --install-deps    Install npm dependencies (livekit-server-sdk)
#   --no-playground   Skip starting the playground
#   --help            Show this help message
#
# === VIVENTIUM END ===

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIVENTIUM_ROOT="$(dirname "$SCRIPT_DIR")"
LIBRECHAT_DIR="$SCRIPT_DIR/LibreChat"
PLAYGROUND_DIR="$SCRIPT_DIR/agent-starter-react"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Options
BUILD_PACKAGES=false
CLEAN_BUILD=false
INSTALL_DEPS=false
NO_PLAYGROUND=false

# LiveKit Configuration (shared env)
LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:7888}"
LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-viventium-local}"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-$(openssl rand -hex 16 2>/dev/null || echo viventium-local-secret)}"
LIVEKIT_PORT=7888

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_PACKAGES=true
            shift
            ;;
        --clean)
            CLEAN_BUILD=true
            BUILD_PACKAGES=true
            shift
            ;;
        --install-deps)
            INSTALL_DEPS=true
            shift
            ;;
        --no-playground)
            NO_PLAYGROUND=true
            shift
            ;;
        --help)
            head -25 "$0" | tail -22
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Verify directories exist
if [ ! -d "$LIBRECHAT_DIR" ]; then
    echo -e "${RED}Error: LibreChat directory not found at $LIBRECHAT_DIR${NC}"
    exit 1
fi

if [ ! -d "$PLAYGROUND_DIR" ]; then
    echo -e "${RED}Error: Playground directory not found at $PLAYGROUND_DIR${NC}"
    exit 1
fi

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Viventium Voice Call Stack${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Load environment from parent viventium_core/.env.local
if [ -f "$VIVENTIUM_ROOT/.env.local" ]; then
    echo -e "${YELLOW}Loading credentials from viventium_core/.env.local...${NC}"
    set -a
    source "$VIVENTIUM_ROOT/.env.local" 2>/dev/null || true
    set +a
    echo -e "${GREEN}Credentials loaded${NC}"
fi

# Ensure LibreChat .env has LiveKit configuration
setup_librechat_env() {
    local env_file="$LIBRECHAT_DIR/.env"

    echo -e "${YELLOW}Configuring LibreChat environment...${NC}"

    # Check if LiveKit vars already exist
    if grep -q "LIVEKIT_API_KEY" "$env_file" 2>/dev/null; then
        echo -e "${GREEN}LiveKit configuration already present in .env${NC}"
    else
        echo -e "${YELLOW}Adding LiveKit configuration to LibreChat/.env...${NC}"
        cat >> "$env_file" << EOF

# === VIVENTIUM START - LiveKit Configuration ===
LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
LIVEKIT_URL=${LIVEKIT_URL}
        VIVENTIUM_PLAYGROUND_URL=http://localhost:3300
# === VIVENTIUM END ===
EOF
        echo -e "${GREEN}LiveKit configuration added${NC}"
    fi
}

# Store PIDs for cleanup
PIDS=()
LIVEKIT_CONTAINER_ID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down all services...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Kill related processes
    pkill -f "node api/server/index.js" 2>/dev/null || true
    pkill -f "vite.*client" 2>/dev/null || true
    pkill -f "next.*agents-playground" 2>/dev/null || true
    # Stop LiveKit container
    if [ -n "$LIVEKIT_CONTAINER_ID" ]; then
        docker stop "$LIVEKIT_CONTAINER_ID" 2>/dev/null || true
    fi
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check MongoDB
check_mongodb() {
    echo -e "${YELLOW}Checking MongoDB...${NC}"
    if ! mongosh --eval "db.runCommand({ping:1})" --quiet > /dev/null 2>&1; then
        echo -e "${RED}MongoDB is not running!${NC}"
        echo -e "${YELLOW}Please start MongoDB first:${NC}"
        echo -e "  brew services start mongodb-community"
        exit 1
    fi
    echo -e "${GREEN}MongoDB OK${NC}"
}

# Start LiveKit Server
start_livekit() {
    echo -e "${BLUE}Starting LiveKit Server...${NC}"

    # Check if already running
    if lsof -Pi :$LIVEKIT_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        EXISTING=$(docker ps -q --filter ancestor=livekit/livekit-server 2>/dev/null | head -1)
        if [ -n "$EXISTING" ]; then
            echo -e "${GREEN}LiveKit already running (container: ${EXISTING:0:12})${NC}"
            LIVEKIT_CONTAINER_ID="$EXISTING"
            return 0
        fi
    fi

    # Start LiveKit
    LIVEKIT_CONTAINER_ID=$(docker run -d \
        -p 7888:7888 \
        -p 7889:7889 \
        -p 7890:7890/udp \
        livekit/livekit-server \
        --dev --bind 0.0.0.0 --node-ip 127.0.0.1)

    echo -e "${GREEN}LiveKit started (container: ${LIVEKIT_CONTAINER_ID:0:12})${NC}"

    # Wait for ready
    echo -e "${YELLOW}Waiting for LiveKit...${NC}"
    for i in {1..30}; do
        if curl -s "http://localhost:$LIVEKIT_PORT" >/dev/null 2>&1; then
            echo -e "${GREEN}LiveKit ready${NC}"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}LiveKit failed to start${NC}"
    return 1
}

# Install livekit-server-sdk if needed (called from within LIBRECHAT_DIR)
install_livekit_sdk() {
    # Already in LIBRECHAT_DIR when called
    if ! grep -q "livekit-server-sdk" api/package.json 2>/dev/null; then
        echo -e "${YELLOW}livekit-server-sdk not found in package.json${NC}"
        echo -e "${YELLOW}It should already be added. Running npm install...${NC}"
    fi

    # Check if node_modules has livekit
    if [ ! -d "node_modules/livekit-server-sdk" ]; then
        echo -e "${YELLOW}Installing livekit-server-sdk...${NC}"
        npm install livekit-server-sdk@^2.11.1 --save
        echo -e "${GREEN}livekit-server-sdk installed${NC}"
    else
        echo -e "${GREEN}livekit-server-sdk already installed${NC}"
    fi
    # Stay in LIBRECHAT_DIR - don't change directory
}

# Start LibreChat
start_librechat() {
    echo -e "${BLUE}Starting LibreChat...${NC}"
    cd "$LIBRECHAT_DIR"

    # Check Node version
    NODE_VERSION=$(node -v | cut -d'.' -f1 | tr -d 'v')
    if [ "$NODE_VERSION" -lt 20 ]; then
        echo -e "${RED}Node.js 20+ required. Current: $(node -v)${NC}"
        exit 1
    fi

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing LibreChat dependencies...${NC}"
        npm ci
        BUILD_PACKAGES=true
    fi

    # Install livekit SDK
    if [ "$INSTALL_DEPS" = true ] || [ ! -d "node_modules/livekit-server-sdk" ]; then
        install_livekit_sdk
    fi

    # Clean if requested
    if [ "$CLEAN_BUILD" = true ]; then
        echo -e "${YELLOW}Cleaning build artifacts...${NC}"
        rm -rf packages/data-provider/dist packages/data-schemas/dist packages/api/dist packages/client/dist client/dist
    fi

    # Build if needed
    if [ "$BUILD_PACKAGES" = true ] || [ ! -d "packages/data-provider/dist" ]; then
        echo -e "${YELLOW}Building packages...${NC}"
        npm run build:data-provider
        npm run build:data-schemas
        npm run build:api
        npm run build:client-package
    fi

    # Build client if needed
    if [ ! -f "client/dist/index.html" ]; then
        echo -e "${YELLOW}Building client...${NC}"
        cd client && npm run build && cd ..
    fi

    # Setup environment
    setup_librechat_env

    # Export LiveKit vars for the backend
    export LIVEKIT_API_KEY
    export LIVEKIT_API_SECRET
    export LIVEKIT_URL
    export VIVENTIUM_PLAYGROUND_URL="http://localhost:3300"

    # Start backend
    echo -e "${BLUE}Starting LibreChat backend (port 3180)...${NC}"
    npm run backend:dev &
    PIDS+=($!)

    # Wait for backend
    echo -e "${YELLOW}Waiting for backend...${NC}"
    sleep 5

    # Start frontend
    echo -e "${BLUE}Starting LibreChat frontend (port 3190)...${NC}"
    PORT=3190 npm run frontend:dev &
    PIDS+=($!)

    cd "$SCRIPT_DIR"
}

# Start Playground
start_playground() {
    echo -e "${BLUE}Starting LiveKit Agents Playground...${NC}"
    cd "$PLAYGROUND_DIR"

    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing playground dependencies...${NC}"
        npm install
    fi

    # Set playground environment
    export NEXT_PUBLIC_LIVEKIT_URL="${LIVEKIT_URL}"

    echo -e "${BLUE}Starting playground (port 3300)...${NC}"
    npm run dev -- -p 3300 &
    PIDS+=($!)

    cd "$SCRIPT_DIR"
}

# Main execution
echo -e "${BOLD}Configuration:${NC}"
echo -e "  LiveKit URL:      ${GREEN}${LIVEKIT_URL}${NC}"
echo -e "  LiveKit API Key:  ${GREEN}${LIVEKIT_API_KEY:0:8}...${NC}"
echo -e "  Playground URL:   ${GREEN}http://localhost:3300${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}Running pre-flight checks...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker required${NC}"; exit 1; }
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js required${NC}"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo -e "${RED}npm required${NC}"; exit 1; }

if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}Docker is not running${NC}"
    exit 1
fi
echo -e "${GREEN}Pre-flight checks passed${NC}"
echo ""

# Start services
check_mongodb
echo ""

start_livekit
echo ""

start_librechat
echo ""

if [ "$NO_PLAYGROUND" != true ]; then
    start_playground
    echo ""
fi

# Wait for services
sleep 3

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All Services Running${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${BLUE}LibreChat Frontend:${NC}  http://localhost:3190"
echo -e "  ${BLUE}LibreChat API:${NC}       http://localhost:3180/api"
echo -e "  ${BLUE}LiveKit Server:${NC}      ws://localhost:7880"
if [ "$NO_PLAYGROUND" != true ]; then
echo -e "  ${BLUE}Voice Playground:${NC}    http://localhost:3300"
fi
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Testing Voice Call Button${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "1. Open ${GREEN}http://localhost:3190${NC} in browser"
echo -e "2. Log in and select an ${GREEN}Agent${NC} conversation"
echo -e "3. Look for the ${GREEN}phone icon${NC} in the chat header"
echo -e "4. Click it to open the voice playground"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for processes
wait "${PIDS[@]}"
