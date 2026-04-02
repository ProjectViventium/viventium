#!/usr/bin/env bash
#
# === VIVENTIUM START ===
# OpenClaw Bridge: MCP bridge to OpenClaw Gateway capabilities
# Added: 2026-02-12
#
# Documentation: docs/requirements_and_learnings/28_OpenClaw_Integration.md
#
# Purpose:
# - Start the OpenClaw Bridge MCP server for LibreChat integration
# - Manages per-user OpenClaw Gateway instances
# - Provides tools: exec, browser, message, cron, nodes, canvas, agent
#
# Usage:
#   ./viventium-openclaw-bridge-start.sh [command]
#
# Commands:
#   start            Start OpenClaw Bridge MCP server (default)
#   stop             Stop the MCP server
#   restart          Stop then start
#   status           Show status
#   logs             Tail MCP server logs
#   build            Force rebuild Docker image
#   native           Run MCP server natively (no Docker, for dev)
#   help             Show this help
#
# Environment Variables (set in .env.local):
#   ANTHROPIC_API_KEY              - API key for OpenClaw agent
#   OPENCLAW_BRIDGE_PORT           - MCP server port (default: 8086)
#   OPENCLAW_BRIDGE_AUTH_TOKEN     - Auth token for gateway communication
#   OPENCLAW_RUNTIME               - direct | e2b (default: e2b for VM POC)
#   OPENCLAW_ISOLATION_TIER        - deprecated alias for OPENCLAW_RUNTIME
#   OPENCLAW_MODEL                 - Default model for OpenClaw agent
#
# === VIVENTIUM END ===
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIVENTIUM_CORE_DIR="$(dirname "$ROOT_DIR")"
OPENCLAW_BRIDGE_DIR="$ROOT_DIR/MCPs/openclaw-bridge"
LOG_ROOT="$VIVENTIUM_CORE_DIR/.viventium"
LOG_DIR="$LOG_ROOT/logs"

mkdir -p "$LOG_DIR"

# ----------------------------
# Helper functions
# ----------------------------
log_info() {
  echo -e "${CYAN}[openclaw-bridge]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[openclaw-bridge]${NC} $1"
}

log_error() {
  echo -e "${RED}[openclaw-bridge]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[openclaw-bridge]${NC} $1"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found. Please install Docker."
    exit 1
  fi
  if ! docker ps >/dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker Desktop."
    exit 1
  fi
}

# ----------------------------
# Load environment
# ----------------------------
load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 1
  fi

  log_info "Loading credentials from $env_file"

  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    line="${line%%#*}"
    line=$(echo "$line" | xargs 2>/dev/null || echo "$line")
    [[ -z "$line" ]] && continue
    if [[ "$line" =~ ^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local value="${BASH_REMATCH[2]}"
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      export "$key"="$value"
    fi
  done < "$env_file"
  return 0
}

if [[ -f "$VIVENTIUM_CORE_DIR/.env" ]]; then
  load_env_file "$VIVENTIUM_CORE_DIR/.env"
fi
if [[ -f "$VIVENTIUM_CORE_DIR/.env.local" ]]; then
  load_env_file "$VIVENTIUM_CORE_DIR/.env.local"
fi

# ----------------------------
# Defaults
# ----------------------------
export OPENCLAW_BRIDGE_PORT="${OPENCLAW_BRIDGE_PORT:-8086}"
export OPENCLAW_BRIDGE_AUTH_TOKEN="${OPENCLAW_BRIDGE_AUTH_TOKEN:-viventium-bridge-local}"
export OPENCLAW_DATA_DIR="${OPENCLAW_DATA_DIR:-$HOME/.viventium/openclaw/users}"
export OPENCLAW_PORT_START="${OPENCLAW_PORT_START:-18789}"
export OPENCLAW_PORT_END="${OPENCLAW_PORT_END:-18999}"
export OPENCLAW_IDLE_TIMEOUT_HOURS="${OPENCLAW_IDLE_TIMEOUT_HOURS:-2}"
export OPENCLAW_RUNTIME="${OPENCLAW_RUNTIME:-${OPENCLAW_ISOLATION_TIER:-e2b}}"
export OPENCLAW_ISOLATION_TIER="${OPENCLAW_ISOLATION_TIER:-$OPENCLAW_RUNTIME}"
export OPENCLAW_MODEL="${OPENCLAW_MODEL:-anthropic/claude-sonnet-4-20250514}"

# ----------------------------
# Show help
# ----------------------------
show_help() {
  echo ""
  echo -e "${CYAN}OpenClaw Bridge${NC}"
  echo ""
  echo "Usage: $0 [command]"
  echo ""
  echo "Commands:"
  echo "  start     Start OpenClaw Bridge MCP server (default)"
  echo "  stop      Stop the MCP server"
  echo "  restart   Stop then start"
  echo "  status    Show status"
  echo "  logs      Tail MCP server logs"
  echo "  build     Force rebuild Docker image"
  echo "  native    Run natively without Docker (for dev)"
  echo "  help      Show this help"
  echo ""
  echo "Available MCP tools:"
  echo "  - openclaw_vm_start/resume/stop/terminate/list/status/takeover"
  echo "  - openclaw_exec/openclaw_browser/openclaw_agent (all accept vm_id)"
  echo ""
  echo "Runtime mode:"
  echo "  OPENCLAW_RUNTIME=$OPENCLAW_RUNTIME (direct|e2b)"
  echo ""
}

# ----------------------------
# Status
# ----------------------------
show_status() {
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  OpenClaw Bridge Status${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  # Check native process
  local native_pid
  native_pid=$(pgrep -f "mcp_server.py.*--port.*${OPENCLAW_BRIDGE_PORT}" 2>/dev/null || true)
  if [[ -n "$native_pid" ]]; then
    log_success "MCP Server (native): running (PID $native_pid) on port $OPENCLAW_BRIDGE_PORT"
  fi

  # Check Docker container
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-openclaw-bridge-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    log_success "MCP Server (Docker): running on port $OPENCLAW_BRIDGE_PORT"
  fi

  if [[ -z "$native_pid" ]] && [[ -z "$mcp_container" ]]; then
    log_warn "MCP Server: not running"
  fi

  # Check health
  local health
  health=$(curl -s "http://localhost:$OPENCLAW_BRIDGE_PORT/health" 2>/dev/null || echo "")
  if [[ -n "$health" ]]; then
    echo "  Health: $health"
  fi

  # Check OpenClaw binary
  if command -v openclaw >/dev/null 2>&1; then
    local oc_version
    oc_version=$(openclaw --version 2>/dev/null || echo "unknown")
    log_success "OpenClaw binary: $oc_version"
  else
    log_warn "OpenClaw binary: not installed (run: npm install -g openclaw@latest)"
  fi

  echo ""
  echo "Configuration:"
  echo "  Port:            $OPENCLAW_BRIDGE_PORT"
  echo "  Data Directory:  $OPENCLAW_DATA_DIR"
  echo "  Runtime Mode:    $OPENCLAW_RUNTIME"
  echo "  Compat Alias:    OPENCLAW_ISOLATION_TIER=$OPENCLAW_ISOLATION_TIER"
  if [[ "$OPENCLAW_RUNTIME" == "e2b" ]]; then
    if [[ -n "${E2B_API_KEY:-}" ]]; then
      echo "  E2B API Key:     set"
    else
      echo "  E2B API Key:     missing"
    fi
  fi
  echo "  Idle Timeout:    ${OPENCLAW_IDLE_TIMEOUT_HOURS}h"
  echo "  Model:           $OPENCLAW_MODEL"
  echo ""
}

# ----------------------------
# Stop services
# ----------------------------
stop_services() {
  log_warn "Stopping OpenClaw Bridge services..."

  # Stop Docker container
  cd "$OPENCLAW_BRIDGE_DIR"
  docker compose down 2>/dev/null || true

  # Stop native process
  local native_pid
  native_pid=$(pgrep -f "mcp_server.py.*--port.*${OPENCLAW_BRIDGE_PORT}" 2>/dev/null || true)
  if [[ -n "$native_pid" ]]; then
    kill "$native_pid" 2>/dev/null || true
    log_info "Stopped native MCP server (PID $native_pid)"
  fi

  log_success "OpenClaw Bridge services stopped"
}

# ----------------------------
# Build images
# ----------------------------
build_images() {
  require_docker

  cd "$OPENCLAW_BRIDGE_DIR"

  log_info "Building OpenClaw Bridge MCP server image..."
  docker compose build --no-cache 2>&1 | tee "$LOG_DIR/openclaw-bridge-build.log"
  log_success "OpenClaw Bridge MCP server image built"
}

# ----------------------------
# Start via Docker
# ----------------------------
start_services() {
  require_docker

  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  OpenClaw Bridge${NC}"
  echo -e "${CYAN}  MCP Bridge to OpenClaw Gateway${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  # Check API keys
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    log_warn "ANTHROPIC_API_KEY not set — OpenClaw agent tools may not work"
  fi

  # Show configuration
  echo -e "Configuration:"
  echo -e "  MCP Port:         ${GREEN}$OPENCLAW_BRIDGE_PORT${NC}"
  echo -e "  Data Directory:   ${GREEN}$OPENCLAW_DATA_DIR${NC}"
  echo -e "  Runtime Mode:     ${GREEN}$OPENCLAW_RUNTIME${NC}"
  echo -e "  Idle Timeout:     ${GREEN}${OPENCLAW_IDLE_TIMEOUT_HOURS}h${NC}"
  echo -e "  Model:            ${GREEN}$OPENCLAW_MODEL${NC}"
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "  Anthropic Key:    ${GREEN}${ANTHROPIC_API_KEY:0:8}...${NC}"
  fi
  echo ""

  mkdir -p "$OPENCLAW_DATA_DIR"

  cd "$OPENCLAW_BRIDGE_DIR"

  # Check if already running
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-openclaw-bridge-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    log_success "MCP server already running on port $OPENCLAW_BRIDGE_PORT"
    show_final_status
    return 0
  fi

  # Build if needed
  if [[ -z "$(docker images -q viventium-openclaw-bridge-mcp 2>/dev/null)" ]]; then
    log_info "Building MCP server image..."
    docker compose build 2>&1 | tee "$LOG_DIR/openclaw-bridge-build.log"
  fi

  # Start
  log_info "Starting MCP server..."
  docker compose up -d

  # Wait for healthy
  log_info "Waiting for MCP server..."
  local attempts=0
  local max_attempts=30
  while [[ $attempts -lt $max_attempts ]]; do
    if curl -s "http://localhost:$OPENCLAW_BRIDGE_PORT/health" >/dev/null 2>&1; then
      log_success "MCP server ready on port $OPENCLAW_BRIDGE_PORT"
      break
    fi
    attempts=$((attempts + 1))
    sleep 1
  done

  if [[ $attempts -ge $max_attempts ]]; then
    log_error "MCP server failed to start. Check logs with: $0 logs"
    exit 1
  fi

  show_final_status
}

# ----------------------------
# Start natively (no Docker)
# ----------------------------
start_native() {
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  OpenClaw Bridge (Native Mode)${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    log_warn "ANTHROPIC_API_KEY not set — OpenClaw agent tools may not work"
  fi

  # Ensure OpenClaw is installed
  if ! command -v openclaw >/dev/null 2>&1; then
    log_info "OpenClaw not found. Installing globally..."
    npm install -g openclaw@latest
  fi

  # Ensure Python deps
  if ! python3 -c "import fastmcp" 2>/dev/null; then
    log_info "Installing Python dependencies..."
    pip3 install -r "$OPENCLAW_BRIDGE_DIR/requirements.txt"
  fi

  mkdir -p "$OPENCLAW_DATA_DIR"

  log_info "Starting MCP server natively on port $OPENCLAW_BRIDGE_PORT..."
  cd "$OPENCLAW_BRIDGE_DIR"

  python3 mcp_server.py --port "$OPENCLAW_BRIDGE_PORT" --host 127.0.0.1 \
    2>&1 | tee "$LOG_DIR/openclaw-bridge-native.log"
}

# ----------------------------
# Show logs
# ----------------------------
show_logs() {
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-openclaw-bridge-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    docker logs -f "$mcp_container"
  elif [[ -f "$LOG_DIR/openclaw-bridge-native.log" ]]; then
    tail -f "$LOG_DIR/openclaw-bridge-native.log"
  else
    log_error "No running server found. Start it first."
    exit 1
  fi
}

show_final_status() {
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  OpenClaw Bridge Running${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""
  echo -e "  ${CYAN}MCP Server:${NC}      http://localhost:$OPENCLAW_BRIDGE_PORT"
  echo -e "  ${CYAN}MCP Endpoint:${NC}    http://localhost:$OPENCLAW_BRIDGE_PORT/mcp"
  echo -e "  ${CYAN}Health Check:${NC}    http://localhost:$OPENCLAW_BRIDGE_PORT/health"
  echo ""
  echo -e "${CYAN}In LibreChat:${NC}"
  echo "  1. Click 'Integrations' button in chat input"
  echo "  2. Find 'openclaw-bridge' and click 'Initialize'"
  echo "  3. Status should change to 'Connected'"
  echo ""
  echo -e "${CYAN}Available MCP tools:${NC}"
  echo "  - openclaw_vm_start/resume/stop/terminate/list/status/takeover"
  echo "  - openclaw_exec/openclaw_browser/openclaw_agent (vm_id aware)"
  echo "  - openclaw_message/openclaw_cron/openclaw_nodes/openclaw_canvas"
  echo ""
  echo -e "${CYAN}Codex CLI:${NC}"
  echo "  python $OPENCLAW_BRIDGE_DIR/vm_control.py list --user demo"
  echo ""
  echo -e "${YELLOW}Commands:${NC}"
  echo "  $0 status    Show service status"
  echo "  $0 logs      Tail MCP server logs"
  echo "  $0 stop      Stop services"
  echo "  $0 build     Rebuild image"
  echo ""
}

# ----------------------------
# Main
# ----------------------------
COMMAND="${1:-start}"

case "$COMMAND" in
  start)
    start_services
    ;;
  stop)
    stop_services
    ;;
  restart)
    stop_services
    start_services
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  build)
    stop_services
    build_images
    start_services
    ;;
  native)
    start_native
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    log_error "Unknown command: $COMMAND"
    show_help
    exit 1
    ;;
esac
