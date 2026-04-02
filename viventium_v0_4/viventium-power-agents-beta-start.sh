#!/usr/bin/env bash
#
# === VIVENTIUM START ===
# Power Agents Beta: Unleashed Coding Sandboxes (Claude Code + Codex + browser-use)
# Added: 2026-01-27, Updated: 2026-01-28
#
# Documentation: docs/requirements_and_learnings/18_Power_Agents_Beta.md
#
# Purpose:
# - Start Power Agents Beta services for unleashed agent capabilities
# - Runs in isolation from the main LibreChat stack
# - Can be run after viventium-librechat-start.sh
#
# What it provides:
# - Power sandbox containers with Claude Code CLI + Codex CLI
# - browser-use for AI browser automation
# - Per-user isolation with persistent workspaces
# - MCP server for LibreChat integration
#
# Usage:
#   ./viventium-power-agents-beta-start.sh [command]
#
# Commands:
#   start            Start Power Agents Beta services (default)
#   stop             Stop all Power Agents Beta services
#   restart          Stop then start
#   status           Show status of Power Agents Beta services
#   logs             Tail logs from MCP server
#   build            Force rebuild all Docker images
#   help             Show this help
#
# Environment Variables (set in .env.local):
#   ANTHROPIC_API_KEY          - Direct Anthropic API key
#   OPENAI_API_KEY             - OpenAI API key for Codex
#
#   # Azure AI Foundry (for enterprise Claude deployments):
#   CLAUDE_CODE_USE_FOUNDRY=1  - Enable Azure Foundry mode
#   ANTHROPIC_FOUNDRY_API_KEY  - Azure Foundry API key
#   ANTHROPIC_FOUNDRY_RESOURCE - Azure Foundry resource name
#   ANTHROPIC_MODEL            - Model to use (e.g., "claude-opus-4-5")
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
POWER_AGENTS_DIR="$ROOT_DIR/MCPs/power-agents-beta"
LOG_ROOT="$VIVENTIUM_CORE_DIR/.viventium"
LOG_DIR="$LOG_ROOT/logs"

mkdir -p "$LOG_DIR"

# ----------------------------
# Helper functions
# ----------------------------
log_info() {
  echo -e "${CYAN}[power-agents-beta]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[power-agents-beta]${NC} $1"
}

log_error() {
  echo -e "${RED}[power-agents-beta]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[power-agents-beta]${NC} $1"
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
# Defaults - IMPORTANT: Port range starts at 9100 to avoid conflicts
# ----------------------------
export POWER_AGENT_MCP_PORT="${POWER_AGENT_MCP_PORT:-8085}"
# CRITICAL: This must be an absolute host path for docker-in-docker to work
export POWER_AGENT_DATA_DIR="${POWER_AGENT_DATA_DIR:-$HOME/.viventium/power-agents-beta/users}"
export POWER_AGENT_IMAGE="${POWER_AGENT_IMAGE:-viventium/power-sandbox:latest}"
export POWER_AGENT_PORT_START="${POWER_AGENT_PORT_START:-9100}"
export POWER_AGENT_PORT_END="${POWER_AGENT_PORT_END:-9199}"
export POWER_AGENT_IDLE_HOURS="${POWER_AGENT_IDLE_HOURS:-2}"
export POWER_AGENT_MEMORY="${POWER_AGENT_MEMORY:-4g}"
export POWER_AGENT_CPUS="${POWER_AGENT_CPUS:-2}"

# ----------------------------
# Show help
# ----------------------------
show_help() {
  echo ""
  echo -e "${CYAN}Power Agents Beta${NC}"
  echo ""
  echo "Usage: $0 [command]"
  echo ""
  echo "Commands:"
  echo "  start     Start Power Agents Beta services (default if no command given)"
  echo "  stop      Stop all Power Agents Beta services"
  echo "  restart   Stop then start services"
  echo "  status    Show status of Power Agents Beta services"
  echo "  logs      Tail logs from MCP server"
  echo "  build     Force rebuild all Docker images"
  echo "  help      Show this help"
  echo ""
  echo "What it provides:"
  echo "  - Power sandbox containers with Claude Code CLI + Codex CLI"
  echo "  - browser-use for AI browser automation"
  echo "  - Per-user isolated containers with persistent workspaces"
  echo "  - MCP server for LibreChat integration"
  echo ""
  echo "Data directory: $POWER_AGENT_DATA_DIR"
  echo ""
}

# ----------------------------
# Status
# ----------------------------
show_status() {
  require_docker
  
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  Power Agents Beta Status${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""
  
  # Check MCP server
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-power-agent-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    log_success "MCP Server: running on port $POWER_AGENT_MCP_PORT"
    
    # Get stats from MCP server
    local stats
    stats=$(curl -s "http://localhost:$POWER_AGENT_MCP_PORT/health" 2>/dev/null || echo "{}")
    local active_containers
    active_containers=$(echo "$stats" | python3 -c "import sys, json; print(json.load(sys.stdin).get('active_containers', 0))" 2>/dev/null || echo "0")
    echo "  Active user containers: $active_containers"
    
    # Check MCP protocol
    local mcp_test
    mcp_test=$(curl -s -X POST "http://localhost:$POWER_AGENT_MCP_PORT/mcp" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}' 2>/dev/null || echo "")
    if [[ "$mcp_test" == *"serverInfo"* ]]; then
      log_success "MCP Protocol: working"
    else
      log_warn "MCP Protocol: not responding correctly"
    fi
  else
    log_warn "MCP Server: not running"
  fi
  
  # Check power sandbox image
  local image_exists
  image_exists=$(docker images -q "$POWER_AGENT_IMAGE" 2>/dev/null || true)
  if [[ -n "$image_exists" ]]; then
    log_success "Power Sandbox Image: available"
  else
    log_warn "Power Sandbox Image: not built (will build on first use)"
  fi
  
  # Check MCP server image
  local mcp_image_exists
  mcp_image_exists=$(docker images -q "viventium/power-agent-mcp:latest" 2>/dev/null || true)
  if [[ -n "$mcp_image_exists" ]]; then
    log_success "MCP Server Image: available"
  else
    log_warn "MCP Server Image: not built"
  fi
  
  # List user containers
  local user_containers
  user_containers=$(docker ps --filter "label=viventium.service=power-agent" --format "{{.Names}}\t{{.Status}}" 2>/dev/null || true)
  if [[ -n "$user_containers" ]]; then
    echo ""
    echo "  User containers:"
    echo "$user_containers" | while read -r line; do
      echo "    $line"
    done
  fi
  
  echo ""
  echo "Data directory: $POWER_AGENT_DATA_DIR"
  echo ""
}

# ----------------------------
# Show logs
# ----------------------------
show_logs() {
  require_docker
  
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-power-agent-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    docker logs -f "$mcp_container"
  else
    log_error "MCP Server not running. Start it first with: $0 start"
    exit 1
  fi
}

# ----------------------------
# Stop services
# ----------------------------
stop_services() {
  require_docker
  
  log_warn "Stopping Power Agents Beta services..."
  
  # Stop MCP server
  cd "$POWER_AGENTS_DIR"
  docker compose down 2>/dev/null || true
  
  # Stop all user containers
  local user_containers
  user_containers=$(docker ps -q --filter "label=viventium.service=power-agent" 2>/dev/null || true)
  if [[ -n "$user_containers" ]]; then
    log_warn "Stopping user containers..."
    docker rm -f $user_containers >/dev/null 2>&1 || true
  fi
  
  log_success "Power Agents Beta services stopped"
}

# ----------------------------
# Build images
# ----------------------------
build_images() {
  require_docker
  
  cd "$POWER_AGENTS_DIR"
  
  log_info "Building power sandbox image..."
  docker build -t "$POWER_AGENT_IMAGE" -f Dockerfile . 2>&1 | tee "$LOG_DIR/power-sandbox-build.log"
  log_success "Power sandbox image built: $POWER_AGENT_IMAGE"
  
  log_info "Building MCP server image..."
  docker compose build --no-cache 2>&1 | tee "$LOG_DIR/mcp-server-build.log"
  log_success "MCP server image built: viventium/power-agent-mcp:latest"
}

# ----------------------------
# Start services
# ----------------------------
start_services() {
  require_docker

  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  Power Agents Beta${NC}"
  echo -e "${CYAN}  Power Agents (Claude Code + Codex)${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  # Check API keys
  local has_claude_key=false
  local has_openai_key=false
  
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]] || [[ "${CLAUDE_CODE_USE_FOUNDRY:-}" == "1" ]]; then
    has_claude_key=true
  fi
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    has_openai_key=true
  fi
  
  if [[ "$has_claude_key" == "false" ]] && [[ "$has_openai_key" == "false" ]]; then
    log_error "No API keys configured!"
    log_error "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env.local"
    log_error "Or configure Azure Foundry with CLAUDE_CODE_USE_FOUNDRY=1"
    exit 1
  fi
  
  if [[ "$has_claude_key" == "false" ]]; then
    log_warn "ANTHROPIC_API_KEY not set - Claude Code will not work"
  fi
  if [[ "$has_openai_key" == "false" ]]; then
    log_warn "OPENAI_API_KEY not set - Codex will not work"
  fi

  # Show configuration
  echo -e "Configuration:"
  echo -e "  MCP Port:          ${GREEN}$POWER_AGENT_MCP_PORT${NC}"
  echo -e "  Data Directory:    ${GREEN}$POWER_AGENT_DATA_DIR${NC}"
  echo -e "  Container Memory:  ${GREEN}$POWER_AGENT_MEMORY${NC}"
  echo -e "  Container CPUs:    ${GREEN}$POWER_AGENT_CPUS${NC}"
  echo -e "  Idle Timeout:      ${GREEN}${POWER_AGENT_IDLE_HOURS}h${NC}"
  echo -e "  Port Range:        ${GREEN}$POWER_AGENT_PORT_START-$POWER_AGENT_PORT_END${NC}"
  
  if [[ "${CLAUDE_CODE_USE_FOUNDRY:-}" == "1" ]]; then
    echo -e "  Claude Mode:       ${GREEN}Azure Foundry${NC}"
    echo -e "  Foundry Resource:  ${GREEN}${ANTHROPIC_FOUNDRY_RESOURCE:-not set}${NC}"
    echo -e "  Model:             ${GREEN}${ANTHROPIC_MODEL:-default}${NC}"
  elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "  Anthropic Key:     ${GREEN}${ANTHROPIC_API_KEY:0:8}...${NC}"
  fi
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo -e "  OpenAI Key:        ${GREEN}${OPENAI_API_KEY:0:8}...${NC}"
  fi
  echo ""

  # Ensure data directory exists
  mkdir -p "$POWER_AGENT_DATA_DIR"
  
  cd "$POWER_AGENTS_DIR"

  # Build power sandbox image if not exists
  if [[ -z "$(docker images -q $POWER_AGENT_IMAGE 2>/dev/null)" ]]; then
    log_info "Power sandbox image not found. Building..."
    docker build -t "$POWER_AGENT_IMAGE" -f Dockerfile . 2>&1 | tee "$LOG_DIR/power-sandbox-build.log"
    log_success "Power sandbox image built: $POWER_AGENT_IMAGE"
  fi

  # Check if MCP server already running
  local mcp_container
  mcp_container=$(docker ps -q --filter "name=viventium-power-agent-mcp" 2>/dev/null || true)
  if [[ -n "$mcp_container" ]]; then
    log_success "MCP server already running on port $POWER_AGENT_MCP_PORT"
    show_final_status
    return 0
  fi

  # Build MCP server image if not exists
  if [[ -z "$(docker images -q viventium/power-agent-mcp:latest 2>/dev/null)" ]]; then
    log_info "MCP server image not found. Building..."
    docker compose build 2>&1 | tee "$LOG_DIR/mcp-server-build.log"
    log_success "MCP server image built"
  fi

  # Start MCP server
  log_info "Starting MCP server..."
  docker compose up -d

  # Wait for MCP server to be ready
  log_info "Waiting for MCP server..."
  local attempts=0
  local max_attempts=30
  while [[ $attempts -lt $max_attempts ]]; do
    if curl -s "http://localhost:$POWER_AGENT_MCP_PORT/health" >/dev/null 2>&1; then
      log_success "MCP server ready on port $POWER_AGENT_MCP_PORT"
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

show_final_status() {
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  Power Agents Beta Running${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""
  echo -e "  ${CYAN}MCP Server:${NC}      http://localhost:$POWER_AGENT_MCP_PORT"
  echo -e "  ${CYAN}MCP Endpoint:${NC}    http://localhost:$POWER_AGENT_MCP_PORT/mcp"
  echo -e "  ${CYAN}Health Check:${NC}    http://localhost:$POWER_AGENT_MCP_PORT/health"
  echo ""
  echo -e "${CYAN}In LibreChat:${NC}"
  echo "  1. Click 'Integrations' button in chat input"
  echo "  2. Find 'power-agents' and click 'Initialize'"
  echo "  3. Status should change to 'Connected'"
  echo ""
  echo -e "${CYAN}Available MCP tools:${NC}"
  echo "  - power_agent_code    (Claude Code / Codex tasks)"
  echo "  - power_agent_browse  (browser automation)"
  echo "  - power_agent_shell   (run shell commands)"
  echo "  - power_agent_workspace_list"
  echo "  - power_agent_workspace_read"
  echo ""
  echo -e "${YELLOW}Commands:${NC}"
  echo "  $0 status    Show service status"
  echo "  $0 logs      Tail MCP server logs"
  echo "  $0 stop      Stop Power Agents Beta services"
  echo "  $0 build     Rebuild all images"
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
  help|--help|-h)
    show_help
    ;;
  *)
    log_error "Unknown command: $COMMAND"
    show_help
    exit 1
    ;;
esac
