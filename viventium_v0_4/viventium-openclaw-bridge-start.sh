#!/usr/bin/env bash
#
# === VIVENTIUM START ===
# OpenClaw Bridge: MCP bridge to OpenClaw Gateway capabilities
# Added: 2026-02-12
#
# Documentation: docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md
#
# Purpose:
# - Start the standalone OpenClaw Bridge MCP lab server; LibreChat client wiring is not shipped
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
#   OPENCLAW_RUNTIME               - e2b | direct (default: e2b sandbox)
#   OPENCLAW_ALLOW_DIRECT_HOST_EXEC - explicit true opt-in required for direct host execution
#   OPENCLAW_ISOLATION_TIER        - deprecated alias for OPENCLAW_RUNTIME
#   OPENCLAW_MODEL                 - Default model for OpenClaw agent
#   OPENCLAW_DISABLE_BONJOUR       - Must remain 1 to prevent host-name mDNS advertisement
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
export OPENCLAW_ALLOW_DIRECT_HOST_EXEC="${OPENCLAW_ALLOW_DIRECT_HOST_EXEC:-false}"
export OPENCLAW_MODEL="${OPENCLAW_MODEL:-anthropic/claude-sonnet-4-20250514}"
export OPENCLAW_DISABLE_BONJOUR=1
export FASTMCP_CHECK_FOR_UPDATES=off

# VIVENTIUM START: one reviewed OpenClaw graph for every local launch.
OPENCLAW_REQUIRED_VERSION="2026.7.1-2"
OPENCLAW_REQUIRED_NODE_VERSION="22.23.1"
OPENCLAW_RUNTIME_LOCK_SHA256="e025a05ef3d268747dc293ef54876471d067f22644a8fa26a9139b7d1fe4fbc3"
OPENCLAW_RUNTIME_LOCK_DIR="$OPENCLAW_BRIDGE_DIR/openclaw-runtime-lock"
OPENCLAW_PYTHON_LOCK_SHA256="a63f4d082895912c25805bc7e2dd8b2c5e7c7a694bb09c6bea170e556407038c"
OPENCLAW_PYTHON_LOCK="$OPENCLAW_BRIDGE_DIR/requirements.lock"

openclaw_version_matches() {
  local binary="$1"
  [[ -x "$binary" ]] || return 1
  local reported
  reported="$("$binary" --version 2>/dev/null || true)"
  [[ "$reported" == "$OPENCLAW_REQUIRED_VERSION" || "$reported" == "OpenClaw $OPENCLAW_REQUIRED_VERSION ("*")" ]]
}

ensure_locked_node_runtime() {
  local runtime_parent="$OPENCLAW_DATA_DIR/node-runtime"
  local runtime_root="$runtime_parent/$OPENCLAW_REQUIRED_NODE_VERSION"
  local runtime_node="$runtime_root/bin/node"
  local runtime_npm="$runtime_root/bin/npm"

  if [[ -x "$runtime_node" && -x "$runtime_npm" ]] &&
     [[ "$($runtime_node --version 2>/dev/null)" == "v$OPENCLAW_REQUIRED_NODE_VERSION" ]] &&
     [[ "$($runtime_npm --version 2>/dev/null)" == "10.9.8" ]]; then
    export PATH="$runtime_root/bin:$PATH"
    return 0
  fi
  if [[ -e "$runtime_root" ]]; then
    log_error "The managed OpenClaw Node runtime is incomplete: $runtime_root"
    log_error "Move that one runtime directory aside, then retry so Viventium can rebuild it safely."
    return 1
  fi

  local os_name arch_name archive_sha
  case "$(uname -s)" in
    Darwin) os_name="darwin" ;;
    Linux) os_name="linux" ;;
    *) log_error "The OpenClaw native runtime supports macOS and Linux only."; return 1 ;;
  esac
  case "$(uname -m)" in
    arm64|aarch64) arch_name="arm64" ;;
    x86_64|amd64) arch_name="x64" ;;
    *) log_error "Unsupported OpenClaw native architecture: $(uname -m)"; return 1 ;;
  esac
  case "$os_name-$arch_name" in
    darwin-arm64) archive_sha="ef28d8fab2c0e4314522d4bb1b7173270aa3937e93b92cb7de79c112ac1fa953" ;;
    darwin-x64) archive_sha="b8da981b8a0b1241b70249204916da76c63573ddf5814dbd2d1e41069105cb81" ;;
    linux-arm64) archive_sha="543fa39e57d4c07855939459a323f4deb9a79dd1bb45e6e99458b0f2de10db8d" ;;
    linux-x64) archive_sha="7a8cb04b4a1df4eaf432125324b81b29a088e73570a23259a8de1c65d07fc129" ;;
  esac

  mkdir -p "$runtime_parent"
  local staging archive_name archive_path
  staging="$(mktemp -d "$runtime_parent/.install-${OPENCLAW_REQUIRED_NODE_VERSION}.XXXXXX")"
  archive_name="node-v${OPENCLAW_REQUIRED_NODE_VERSION}-${os_name}-${arch_name}.tar.gz"
  archive_path="$staging/$archive_name"
  if ! curl --fail --silent --show-error --location \
       "https://nodejs.org/dist/v${OPENCLAW_REQUIRED_NODE_VERSION}/${archive_name}" \
       --output "$archive_path" ||
     ! printf '%s  %s\n' "$archive_sha" "$archive_path" | shasum -a 256 -c - ||
     ! tar -xzf "$archive_path" -C "$staging" --strip-components=1 ||
     ! [[ "$($staging/bin/node --version 2>/dev/null)" == "v$OPENCLAW_REQUIRED_NODE_VERSION" ]] ||
     ! [[ "$($staging/bin/npm --version 2>/dev/null)" == "10.9.8" ]]; then
    rm -rf -- "$staging"
    log_error "The exact reviewed Node runtime could not be installed; no fallback was used."
    return 1
  fi
  rm -f -- "$archive_path"
  if ! mv "$staging" "$runtime_root"; then
    rm -rf -- "$staging"
    log_error "The managed OpenClaw Node runtime could not be activated."
    return 1
  fi
  export PATH="$runtime_root/bin:$PATH"
}

ensure_locked_openclaw_runtime() {
  local runtime_parent="$OPENCLAW_DATA_DIR/runtime"
  local runtime_root="$runtime_parent/$OPENCLAW_REQUIRED_VERSION"
  local runtime_bin="$runtime_root/node_modules/.bin/openclaw"

  if openclaw_version_matches "$runtime_bin"; then
    export OPENCLAW_BIN="$runtime_bin"
    return 0
  fi
  if [[ -e "$runtime_root" ]]; then
    log_error "The managed OpenClaw runtime is incomplete or has the wrong version: $runtime_root"
    log_error "Move that one runtime directory aside, then retry so Viventium can rebuild it safely."
    return 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    log_error "Node/npm is required to install the optional OpenClaw runtime."
    return 1
  fi
  if [[ ! -f "$OPENCLAW_RUNTIME_LOCK_DIR/package.json" || ! -f "$OPENCLAW_RUNTIME_LOCK_DIR/package-lock.json" ]]; then
    log_error "The reviewed OpenClaw runtime lock is missing; refusing a mutable fallback."
    return 1
  fi

  local actual_lock_sha
  actual_lock_sha="$(shasum -a 256 "$OPENCLAW_RUNTIME_LOCK_DIR/package-lock.json" | awk '{print $1}')"
  if [[ "$actual_lock_sha" != "$OPENCLAW_RUNTIME_LOCK_SHA256" ]]; then
    log_error "The OpenClaw runtime lock failed its integrity check; refusing installation."
    return 1
  fi

  mkdir -p "$runtime_parent"
  local staging
  staging="$(mktemp -d "$runtime_parent/.install-${OPENCLAW_REQUIRED_VERSION}.XXXXXX")"
  if ! /bin/cp "$OPENCLAW_RUNTIME_LOCK_DIR/package.json" "$OPENCLAW_RUNTIME_LOCK_DIR/package-lock.json" "$staging/" ||
     ! npm ci --omit=dev --prefix "$staging" ||
     ! openclaw_version_matches "$staging/node_modules/.bin/openclaw"; then
    rm -rf -- "$staging"
    log_error "The exact reviewed OpenClaw runtime could not be installed; no fallback was used."
    return 1
  fi
  if ! mv "$staging" "$runtime_root"; then
    rm -rf -- "$staging"
    log_error "The managed OpenClaw runtime could not be activated."
    return 1
  fi
  export OPENCLAW_BIN="$runtime_bin"
}

ensure_locked_python_runtime() {
  local runtime_parent="$OPENCLAW_DATA_DIR/python-runtime"
  local runtime_root="$runtime_parent/$OPENCLAW_PYTHON_LOCK_SHA256"
  local runtime_python="$runtime_root/bin/python"

  if [[ -x "$runtime_python" ]] && "$runtime_python" -c \
     'from importlib.metadata import version; assert version("fastmcp") == "3.4.4"' 2>/dev/null; then
    export OPENCLAW_PYTHON_BIN="$runtime_python"
    return 0
  fi
  if [[ -e "$runtime_root" ]]; then
    log_error "The managed OpenClaw Python runtime is incomplete: $runtime_root"
    log_error "Move that one runtime directory aside, then retry so Viventium can rebuild it safely."
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log_error "Python 3 is required to install the optional OpenClaw bridge runtime."
    return 1
  fi
  if [[ ! -f "$OPENCLAW_PYTHON_LOCK" ]]; then
    log_error "The reviewed OpenClaw Python lock is missing; refusing a mutable fallback."
    return 1
  fi

  local actual_lock_sha
  actual_lock_sha="$(shasum -a 256 "$OPENCLAW_PYTHON_LOCK" | awk '{print $1}')"
  if [[ "$actual_lock_sha" != "$OPENCLAW_PYTHON_LOCK_SHA256" ]]; then
    log_error "The OpenClaw Python lock failed its integrity check; refusing installation."
    return 1
  fi

  mkdir -p "$runtime_parent"
  local staging
  staging="$(mktemp -d "$runtime_parent/.install-${OPENCLAW_PYTHON_LOCK_SHA256}.XXXXXX")"
  if ! python3 -m venv "$staging" ||
     ! "$staging/bin/python" -m pip install --disable-pip-version-check --require-hashes -r "$OPENCLAW_PYTHON_LOCK" ||
     ! "$staging/bin/python" -c 'from importlib.metadata import version; assert version("fastmcp") == "3.4.4"'; then
    rm -rf -- "$staging"
    log_error "The exact reviewed OpenClaw Python runtime could not be installed; no fallback was used."
    return 1
  fi
  if ! mv "$staging" "$runtime_root"; then
    rm -rf -- "$staging"
    log_error "The managed OpenClaw Python runtime could not be activated."
    return 1
  fi
  export OPENCLAW_PYTHON_BIN="$runtime_python"
}

ensure_bridge_secret() {
  if [[ -n "${OPENCLAW_BRIDGE_SECRET:-}" ]]; then
    if [[ ! "$OPENCLAW_BRIDGE_SECRET" =~ ^[0-9a-fA-F]{64}$ ]]; then
      log_error "OPENCLAW_BRIDGE_SECRET must be a 64-character hexadecimal secret."
      return 1
    fi
    export OPENCLAW_BRIDGE_SECRET
    return 0
  fi
  local secret_path="$OPENCLAW_DATA_DIR/.bridge-secret"
  if [[ -L "$OPENCLAW_DATA_DIR" ]]; then
    log_error "The OpenClaw data directory cannot be a symlink."
    return 1
  fi
  mkdir -p "$OPENCLAW_DATA_DIR"
  chmod 700 "$OPENCLAW_DATA_DIR"
  if [[ -L "$secret_path" || ( -e "$secret_path" && ! -f "$secret_path" ) ]]; then
    log_error "The OpenClaw bridge secret path must be a regular file, never a symlink."
    return 1
  fi
  if [[ ! -e "$secret_path" ]]; then
    if [[ ! -x /usr/bin/openssl ]]; then
      log_error "OpenSSL is required to create the local OpenClaw bridge secret."
      return 1
    fi
    local generated_secret staging_secret
    generated_secret="$(/usr/bin/openssl rand -hex 32)"
    staging_secret="$(mktemp "$OPENCLAW_DATA_DIR/.bridge-secret.XXXXXX")"
    chmod 600 "$staging_secret"
    printf '%s\n' "$generated_secret" > "$staging_secret"
    if ! ln "$staging_secret" "$secret_path" 2>/dev/null; then
      rm -f -- "$staging_secret"
      if [[ -L "$secret_path" || ! -f "$secret_path" ]]; then
        log_error "The OpenClaw bridge secret path changed while it was being created."
        return 1
      fi
    else
      rm -f -- "$staging_secret"
    fi
  fi
  local secret_owner secret_mode secret_bytes
  secret_owner="$(stat -f '%u' "$secret_path" 2>/dev/null || true)"
  secret_mode="$(stat -f '%Lp' "$secret_path" 2>/dev/null || true)"
  secret_bytes="$(wc -c < "$secret_path" | tr -d ' ')"
  if [[ "$secret_owner" != "$(id -u)" || "$secret_mode" != "600" || "$secret_bytes" != "65" ]]; then
    log_error "The OpenClaw bridge secret must be owned by the current user, mode 600, and exactly 64 hexadecimal characters."
    return 1
  fi
  IFS= read -r OPENCLAW_BRIDGE_SECRET < "$secret_path"
  if [[ ! "$OPENCLAW_BRIDGE_SECRET" =~ ^[0-9a-fA-F]{64}$ ]]; then
    log_error "The local OpenClaw bridge secret is invalid; refusing to start."
    return 1
  fi
  export OPENCLAW_BRIDGE_SECRET
}
# VIVENTIUM END

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

  # Check the managed exact OpenClaw binary; a random global install is not accepted.
  local managed_openclaw="$OPENCLAW_DATA_DIR/runtime/$OPENCLAW_REQUIRED_VERSION/node_modules/.bin/openclaw"
  if openclaw_version_matches "$managed_openclaw"; then
    local oc_version
    oc_version=$("$managed_openclaw" --version 2>/dev/null || echo "unknown")
    log_success "OpenClaw binary: $oc_version"
  else
    log_warn "OpenClaw binary: reviewed runtime not installed (run this launcher with 'native')"
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
  echo "  Bonjour:         disabled"
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
  ensure_bridge_secret

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
    echo -e "  Anthropic Key:    ${GREEN}Configured${NC}"
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

  ensure_bridge_secret

  # Install or reuse only the reviewed app-owned runtimes and dependency graphs.
  ensure_locked_node_runtime
  ensure_locked_openclaw_runtime

  # Install or reuse the reviewed app-owned Python dependency graph.
  ensure_locked_python_runtime

  mkdir -p "$OPENCLAW_DATA_DIR"

  log_info "Starting MCP server natively on port $OPENCLAW_BRIDGE_PORT..."
  cd "$OPENCLAW_BRIDGE_DIR"

  "$OPENCLAW_PYTHON_BIN" mcp_server.py --port "$OPENCLAW_BRIDGE_PORT" --host 127.0.0.1 \
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
  echo -e "${YELLOW}Standalone lab status:${NC}"
  echo "  The current public Viventium config does not register this bridge in LibreChat."
  echo "  Starting the bridge alone does not make OpenClaw available in chat."
  echo "  Client secret delivery and lifecycle QA must land before that path is supported."
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
