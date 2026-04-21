#!/usr/bin/env bash
#
# === VIVENTIUM START ===
# Unified dev launcher: LibreChat + LiveKit + Agents Playground + Voice Gateway + MCPs + Telegram
# Added: 2026-01-08
#
# Goals:
# - Single command to bring up the full voice-call stack for local testing
# - Auto-loads credentials from viventium_core/.env.local
# - Minimal coupling to upstream projects (we call their existing scripts/CLIs)
#
# Usage:
#   ./viventium-librechat-start.sh [options]
#
# Options:
#   --skip-livekit        Don't start LiveKit server
#   --skip-librechat      Don't start LibreChat
#   --skip-playground     Don't start Agents Playground
#   --modern-playground   Use the agent-starter-react playground UI
#   --skip-voice-gateway  Don't start Voice Gateway worker
#   --skip-google-mcp     Don't start Google Workspace MCP
#   --skip-ms365-mcp      Don't start MS365 MCP
#   --skip-scheduling-mcp Don't start Scheduling Cortex MCP
#   --skip-rag-api        Don't start local RAG API / conversation-recall vector service
#   --skip-skyvern        Don't start Skyvern Browser Agent
#   --skip-code-interpreter  Don't start LibreCodeInterpreter API
#   --skip-firecrawl      Don't start Firecrawl scraper
#   --skip-telegram       Don't start Telegram bridge
#   --skip-v1-agent       Don't start V1 LiveKit agent
#   --skip-docker         Don't stop/restart Docker services (LiveKit/MS365/Code Interpreter)
#   --skip-health-checks  Skip final HTTP health checks
#   --skip-v1-sync        Skip uv sync + model download for V1 agent
#   --skip-voice-deps     Skip voice gateway venv/dependency checks
#   --skip-mcp-verify     Skip MCP tools verification
#   --no-bootstrap        Do not auto-bootstrap missing nested repos before startup
#   --private-overlay     Also load a private machine-local override env file (if present)
#   --profile=<name>      Runtime profile: isolated (default) or compat
#   --fast                Shortcut for --skip-health-checks --skip-v1-sync --skip-mcp-verify
#   --restart             Stop running services first, then start fresh
#   --stop                Stop running services and exit
#   --help                Show this help
#
# === VIVENTIUM END ===
#

set -euo pipefail

# === VIVENTIUM START ===
if [[ -d "/opt/homebrew/bin" ]]; then
  export PATH="/opt/homebrew/bin:${PATH}"
fi
if [[ -d "/usr/local/bin" ]]; then
  export PATH="/usr/local/bin:${PATH}"
fi
if [[ -d "/opt/homebrew/opt/python@3.12/libexec/bin" ]]; then
  export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:${PATH}"
fi
if [[ -d "/usr/local/opt/python@3.12/libexec/bin" ]]; then
  export PATH="/usr/local/opt/python@3.12/libexec/bin:${PATH}"
fi
if [[ -d "/opt/homebrew/opt/node@20/bin" ]]; then
  export PATH="/opt/homebrew/opt/node@20/bin:${PATH}"
fi
if [[ -d "/usr/local/opt/node@20/bin" ]]; then
  export PATH="/usr/local/opt/node@20/bin:${PATH}"
fi
# === VIVENTIUM END ===

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

current_node_major_version() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi

  local version=""
  version="$(node -v 2>/dev/null || true)"
  version="${version#v}"
  version="${version%%.*}"
  if [[ ! "$version" =~ ^[0-9]+$ ]]; then
    return 1
  fi

  printf '%s\n' "$version"
}

prepend_node20_to_path() {
  local node20_prefix=""
  if command -v brew >/dev/null 2>&1; then
    node20_prefix="$(brew --prefix node@20 2>/dev/null || true)"
  fi
  if [[ -n "$node20_prefix" && -d "$node20_prefix/bin" ]]; then
    export PATH="$node20_prefix/bin:${PATH}"
    hash -r 2>/dev/null || true
  fi
}

ensure_validated_node20_runtime() {
  prepend_node20_to_path

  local major=""
  major="$(current_node_major_version || true)"
  if [[ "$major" == "20" ]] && command -v npm >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v brew >/dev/null 2>&1; then
    log_error "Validated node@20 runtime required, but Homebrew is unavailable to install it"
    return 1
  fi

  if [[ "${VIVENTIUM_AUTO_INSTALL_NODE:-true}" != "true" ]]; then
    log_error "Validated node@20 runtime required, but automatic node installation is disabled"
    return 1
  fi

  local current_version="missing"
  if command -v node >/dev/null 2>&1; then
    current_version="$(node -v 2>/dev/null || printf 'unknown')"
  fi

  log_warn "Validated node@20 runtime required; found ${current_version}. Installing/activating Homebrew node@20"
  HOMEBREW_NO_AUTO_UPDATE=1 brew install node@20 >/dev/null 2>&1 || return 1
  prepend_node20_to_path

  major="$(current_node_major_version || true)"
  if [[ "$major" != "20" || ! "$(command -v npm || true)" ]]; then
    log_error "Unable to activate the validated node@20 runtime after Homebrew install"
    return 1
  fi

  return 0
}

detect_livekit_node_ip() {
  if [[ -n "${LIVEKIT_NODE_IP:-}" ]]; then
    printf '%s\n' "$LIVEKIT_NODE_IP"
    return 0
  fi

  local preferred_iface=""
  if command -v route >/dev/null 2>&1; then
    preferred_iface="$(route get default 2>/dev/null | awk '/interface:/{print $2; exit}' || true)"
  fi

  if command -v ipconfig >/dev/null 2>&1; then
    local iface=""
    local candidate=""
    for iface in "$preferred_iface" en0 en1; do
      [[ -z "$iface" ]] && continue
      candidate="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
      if [[ -n "$candidate" && "$candidate" != 127.* ]]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
  fi

  if command -v hostname >/dev/null 2>&1; then
    local host_ip=""
    host_ip="$(hostname -I 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i !~ /^127\\./) {print $i; exit}}' || true)"
    if [[ -n "$host_ip" ]]; then
      printf '%s\n' "$host_ip"
      return 0
    fi
  fi

  printf '%s\n' "127.0.0.1"
  return 0
}

livekit_native_binary_path() {
  if command -v livekit-server >/dev/null 2>&1; then
    command -v livekit-server
    return 0
  fi
  if command -v livekit >/dev/null 2>&1; then
    command -v livekit
    return 0
  fi
  return 1
}

librechat_client_build_node_options() {
  local max_old_space_size="${VIVENTIUM_CLIENT_BUILD_MAX_OLD_SPACE_SIZE:-4096}"
  if [[ -n "$max_old_space_size" ]]; then
    printf '%s\n' "--max-old-space-size=${max_old_space_size}"
  fi
}

ROOT_DIR="${VIVENTIUM_HELPER_V0_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
VIVENTIUM_CORE_DIR="${VIVENTIUM_HELPER_CORE_ROOT:-$(dirname "$ROOT_DIR")}"
VIVENTIUM_WORKSPACE_DIR="${VIVENTIUM_HELPER_WORKSPACE_ROOT:-$(dirname "$VIVENTIUM_CORE_DIR")}"
if [[ -f "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh" ]]; then
  # shellcheck source=/dev/null
  source "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh"
fi

if ! declare -F discover_workspace_repo_dir >/dev/null 2>&1; then
  discover_workspace_repo_dir() {
    local repo_name="$1"
    local workspace_root="$2"
    local repo_root="${3:-$workspace_root}"
    local candidate=""
    local candidates=(
      "$repo_root/$repo_name"
      "$workspace_root/$repo_name"
    )
    for candidate in "${candidates[@]}"; do
      if declare -F path_is_git_repo_root >/dev/null 2>&1; then
        if path_is_git_repo_root "$candidate"; then
          printf '%s\n' "$candidate"
          return 0
        fi
      elif [[ -d "$candidate" ]] && git -C "$candidate" rev-parse --show-toplevel >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
    return 1
  }
fi

VIVENTIUM_PRIVATE_REPO_DIR="${VIVENTIUM_PRIVATE_REPO_DIR:-$(discover_private_repo_dir "$VIVENTIUM_WORKSPACE_DIR" "$VIVENTIUM_CORE_DIR" || true)}"
VIVENTIUM_DEPLOY_REPO_DIR="${VIVENTIUM_DEPLOY_REPO_DIR:-$(discover_workspace_repo_dir "enterprise-deployment-repo" "$VIVENTIUM_WORKSPACE_DIR" "$VIVENTIUM_CORE_DIR" || true)}"
if [[ -n "$VIVENTIUM_PRIVATE_REPO_DIR" ]]; then
  VIVENTIUM_PRIVATE_CURATED_DIR="${VIVENTIUM_PRIVATE_CURATED_DIR:-$VIVENTIUM_PRIVATE_REPO_DIR/curated}"
  VIVENTIUM_PRIVATE_MIRROR_DIR="${VIVENTIUM_PRIVATE_MIRROR_DIR:-$VIVENTIUM_PRIVATE_REPO_DIR/mirror}"
else
  VIVENTIUM_PRIVATE_CURATED_DIR="${VIVENTIUM_PRIVATE_CURATED_DIR:-}"
  VIVENTIUM_PRIVATE_MIRROR_DIR="${VIVENTIUM_PRIVATE_MIRROR_DIR:-}"
fi

first_existing_path() {
  local candidate
  for candidate in "$@"; do
    if [[ -n "$candidate" && -e "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

first_existing_dir() {
  local candidate
  for candidate in "$@"; do
    if [[ -n "$candidate" && -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_path_or_default() {
  local fallback="$1"
  shift
  local resolved=""
  if resolved="$(first_existing_path "$@")"; then
    printf '%s\n' "$resolved"
  else
    printf '%s\n' "$fallback"
  fi
}

resolve_dir_or_default() {
  local fallback="$1"
  shift
  local resolved=""
  if resolved="$(first_existing_dir "$@")"; then
    printf '%s\n' "$resolved"
  else
    printf '%s\n' "$fallback"
  fi
}

text_file_is_readable_with_timeout() {
  local text_file="$1"
  local timeout_seconds="${VIVENTIUM_PRIVATE_TEXT_READ_TIMEOUT_SECONDS:-3}"
  [[ -f "$text_file" ]] || return 1
  python3.11 - "$text_file" "$timeout_seconds" <<'PY'
import math
import signal
import sys


def timeout_handler(signum, frame):
    raise TimeoutError("timed out while reading text file")


timeout_seconds = max(1, int(math.ceil(float(sys.argv[2]))))
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(timeout_seconds)
try:
    with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as handle:
        handle.read(1)
finally:
    signal.alarm(0)
PY
}

PRIVATE_OVERLAY_FLAGS=(--private-overlay)
PRIVATE_OVERLAY_ENV_CANDIDATES=()
PRIVATE_LAUNCHER_COMPAT_FILE="${VIVENTIUM_PRIVATE_LAUNCHER_COMPAT_FILE:-$(resolve_path_or_default \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/launcher-private-compat.sh" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/launcher-private-compat.sh" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/configs/launcher-private-compat.sh" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/launcher-private-compat.sh" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/launcher-private-compat.sh")}"
if [[ -n "$PRIVATE_LAUNCHER_COMPAT_FILE" && -f "$PRIVATE_LAUNCHER_COMPAT_FILE" ]]; then
  if text_file_is_readable_with_timeout "$PRIVATE_LAUNCHER_COMPAT_FILE"; then
    # shellcheck source=/dev/null
    source "$PRIVATE_LAUNCHER_COMPAT_FILE"
  else
    echo "Warning: ignoring unreadable private launcher compat file at $PRIVATE_LAUNCHER_COMPAT_FILE" >&2
  fi
fi

is_private_overlay_arg() {
  local candidate="$1"
  local overlay_arg=""
  for overlay_arg in "${PRIVATE_OVERLAY_FLAGS[@]}"; do
    if [[ "$candidate" == "$overlay_arg" ]]; then
      return 0
    fi
  done
  return 1
}

resolve_private_overlay_env_file() {
  local fallback="$VIVENTIUM_CORE_DIR/.env.private-overlay.local"
  local base_candidates=(
    "$VIVENTIUM_CORE_DIR/.env.private-overlay.local"
    "$VIVENTIUM_PRIVATE_REPO_DIR/.env.private-overlay.local"
    "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/env.private-overlay.local"
    "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/.env.private-overlay.local"
    "$VIVENTIUM_PRIVATE_MIRROR_DIR/.env.private-overlay.local"
  )
  local all_candidates=("${base_candidates[@]}")
  if [[ "${#PRIVATE_OVERLAY_ENV_CANDIDATES[@]}" -gt 0 ]]; then
    all_candidates+=("${PRIVATE_OVERLAY_ENV_CANDIDATES[@]}")
  fi
  resolve_path_or_default "$fallback" "${all_candidates[@]}"
}

LEGACY_V0_3_DIR="$(resolve_dir_or_default \
  "$VIVENTIUM_CORE_DIR/viventium_v0_3_py" \
  "$VIVENTIUM_CORE_DIR/viventium_v0_3_py" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/viventium_v0_3_py" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/legacy/viventium_v0_3_py" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/misc/viventium_v0_3_py" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/viventium_v0_3_py" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_3_py")"
# === VIVENTIUM START ===
# Allow running the unified launcher against a different LibreChat checkout,
# such as a clean port worktree, without relocating the rest of the Viventium stack.
LIBRECHAT_DIR="${VIVENTIUM_LIBRECHAT_DIR:-$ROOT_DIR/LibreChat}"
# === VIVENTIUM END ===
if [[ -n "$VIVENTIUM_PRIVATE_CURATED_DIR" ]]; then
  LIBRECHAT_PRIVATE_CONFIG_DIR="$VIVENTIUM_PRIVATE_CURATED_DIR/configs/librechat"
else
  LIBRECHAT_PRIVATE_CONFIG_DIR=""
fi
LIBRECHAT_CANONICAL_ENV_FILE="${VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE:-$(resolve_path_or_default \
  "$LIBRECHAT_PRIVATE_CONFIG_DIR/librechat.env" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/LibreChat/.env" \
  "$LIBRECHAT_DIR/.env")}"
LIBRECHAT_RUNTIME_ENV_FILE="$LIBRECHAT_DIR/.env"
LIBRECHAT_LOCAL_SOURCE_OF_TRUTH="${VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH:-$(resolve_path_or_default \
  "$LIBRECHAT_PRIVATE_CONFIG_DIR/source_of_truth/local.librechat.yaml" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml" \
  "$LIBRECHAT_DIR/viventium/source_of_truth/local.librechat.yaml")}"
PLAYGROUND_DIR="$ROOT_DIR/agents-playground"
MODERN_PLAYGROUND_DIR="$ROOT_DIR/agent-starter-react"
VOICE_GATEWAY_DIR="$ROOT_DIR/voice-gateway"
GOOGLE_MCP_DIR="$ROOT_DIR/MCPs/google_workspace_mcp"
SCHEDULING_MCP_DIR="$LIBRECHAT_DIR/viventium/MCPs/scheduling-cortex"
GLASSHIVE_DIR="$ROOT_DIR/GlassHive"
GLASSHIVE_RUNTIME_DIR="$GLASSHIVE_DIR/runtime_phase1"
GLASSHIVE_UI_DIR="$GLASSHIVE_DIR/frontends/glass-drive-ui"
V1_AGENT_DIR="$LEGACY_V0_3_DIR/viventium_v1/backend/brain/frontal-cortex"
TELEGRAM_DIR_PRIMARY="$ROOT_DIR/telegram-viventium"
TELEGRAM_DIR_FALLBACK="$LEGACY_V0_3_DIR/interfaces/telegram-viventium"
TELEGRAM_CODEX_DIR="$ROOT_DIR/telegram-codex"
CODE_INTERPRETER_DIR="$LIBRECHAT_DIR/viventium/services/librecodeinterpreter"
VIVENTIUM_APP_SUPPORT_ROOT="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
TELEGRAM_RUNTIME_CONFIG_ENV_FILE="${VIVENTIUM_TELEGRAM_RUNTIME_ENV_FILE:-}"
if [[ -z "$TELEGRAM_RUNTIME_CONFIG_ENV_FILE" ]]; then
  if [[ -n "${VIVENTIUM_ENV_FILE:-}" ]]; then
    TELEGRAM_RUNTIME_CONFIG_ENV_FILE="$(dirname "$VIVENTIUM_ENV_FILE")/service-env/telegram.config.env"
  else
    TELEGRAM_RUNTIME_CONFIG_ENV_FILE="$VIVENTIUM_APP_SUPPORT_ROOT/runtime/service-env/telegram.config.env"
  fi
fi
TELEGRAM_CONFIG_ENV_FILE="${VIVENTIUM_TELEGRAM_ENV_FILE:-$(resolve_path_or_default   "$TELEGRAM_RUNTIME_CONFIG_ENV_FILE"   "$TELEGRAM_RUNTIME_CONFIG_ENV_FILE"   "$VIVENTIUM_APP_SUPPORT_ROOT/runtime/service-env/telegram.config.env"   "$TELEGRAM_DIR_PRIMARY/config.env"   "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/telegram/config.env"   "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/telegram-viventium/config.env")}"
TELEGRAM_CODEX_ENV_FILE="${VIVENTIUM_TELEGRAM_CODEX_ENV_FILE:-$TELEGRAM_CODEX_DIR/.env}"
TELEGRAM_CODEX_SETTINGS_FILE="${VIVENTIUM_TELEGRAM_CODEX_SETTINGS_FILE:-$TELEGRAM_CODEX_DIR/config/settings.yaml}"
TELEGRAM_CODEX_PROJECTS_FILE="${VIVENTIUM_TELEGRAM_CODEX_PROJECTS_FILE:-$TELEGRAM_CODEX_DIR/config/projects.yaml}"
TELEGRAM_USER_CONFIGS_DIR="${VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR:-$(resolve_dir_or_default \
  "$TELEGRAM_DIR_PRIMARY/TelegramVivBot/user_configs" \
  "$TELEGRAM_DIR_PRIMARY/TelegramVivBot/user_configs" \
  "$TELEGRAM_DIR_PRIMARY/user_configs" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/telegram-user-configs" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/telegram-viventium/TelegramVivBot/user_configs")}"
SKYVERN_ENV_FILE="${VIVENTIUM_SKYVERN_ENV_FILE:-$(resolve_path_or_default \
  "$ROOT_DIR/docker/skyvern/.env" \
  "$ROOT_DIR/docker/skyvern/.env" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/skyvern/skyvern.env" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/.env")}"
SKYVERN_POSTGRES_DATA_DIR="${VIVENTIUM_SKYVERN_POSTGRES_DATA_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/postgres-data" \
  "$ROOT_DIR/docker/skyvern/postgres-data" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/postgres-data" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/postgres-data")}"
SKYVERN_STREAMLIT_DIR="${VIVENTIUM_SKYVERN_STREAMLIT_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/.streamlit" \
  "$ROOT_DIR/docker/skyvern/.streamlit" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/.streamlit" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/.streamlit")}"
SKYVERN_ARTIFACTS_DIR="${VIVENTIUM_SKYVERN_ARTIFACTS_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/artifacts" \
  "$ROOT_DIR/docker/skyvern/artifacts" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/artifacts" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/artifacts")}"
SKYVERN_VIDEOS_DIR="${VIVENTIUM_SKYVERN_VIDEOS_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/videos" \
  "$ROOT_DIR/docker/skyvern/videos" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/videos" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/videos")}"
SKYVERN_HAR_DIR="${VIVENTIUM_SKYVERN_HAR_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/har" \
  "$ROOT_DIR/docker/skyvern/har" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/har" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/har")}"
SKYVERN_LOG_DATA_DIR="${VIVENTIUM_SKYVERN_LOG_DIR:-$(resolve_dir_or_default \
  "$ROOT_DIR/docker/skyvern/log" \
  "$ROOT_DIR/docker/skyvern/log" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/log" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/log")}"
export SKYVERN_ENV_FILE SKYVERN_POSTGRES_DATA_DIR SKYVERN_STREAMLIT_DIR SKYVERN_ARTIFACTS_DIR SKYVERN_VIDEOS_DIR SKYVERN_HAR_DIR SKYVERN_LOG_DATA_DIR
VIVENTIUM_BASE_STATE_DIR="${VIVENTIUM_BASE_STATE_DIR:-$(resolve_dir_or_default \
  "$VIVENTIUM_CORE_DIR/.viventium" \
  "$VIVENTIUM_CORE_DIR/.viventium" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/.viventium" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/.viventium" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/.viventium" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/.viventium")}"
LOG_ROOT="$VIVENTIUM_BASE_STATE_DIR"
LOG_DIR="$LOG_ROOT/logs"
GOOGLE_MCP_PID_FILE="$LOG_ROOT/google_workspace_mcp.pid"
SCHEDULING_MCP_PID_FILE="$LOG_ROOT/scheduling_cortex_mcp.pid"
GLASSHIVE_RUNTIME_PID_FILE="$LOG_ROOT/glasshive_runtime.pid"
GLASSHIVE_MCP_PID_FILE="$LOG_ROOT/glasshive_mcp.pid"
GLASSHIVE_UI_PID_FILE="$LOG_ROOT/glasshive_ui.pid"
TELEGRAM_BOT_PID_FILE="$LOG_ROOT/telegram_bot.pid"
TELEGRAM_LOCAL_BOT_API_PID_FILE="$LOG_ROOT/telegram-local-bot-api.pid"
TELEGRAM_LOCAL_BOT_API_LOG_FILE="$LOG_DIR/telegram-local-bot-api.log"
TELEGRAM_LOCAL_BOT_API_STATE_DIR="$VIVENTIUM_STATE_ROOT/telegram-local-bot-api"
TELEGRAM_LOCAL_BOT_API_WORK_DIR="$TELEGRAM_LOCAL_BOT_API_STATE_DIR/work"
TELEGRAM_LOCAL_BOT_API_TEMP_DIR="$TELEGRAM_LOCAL_BOT_API_STATE_DIR/tmp"
TELEGRAM_LOCAL_BOT_API_HOSTED_LOGOUT_MARKER_FILE="$TELEGRAM_LOCAL_BOT_API_STATE_DIR/hosted-logout.sha256"
TELEGRAM_BOT_DEFERRED_PID_FILE="$LOG_ROOT/telegram_bot_deferred.pid"
TELEGRAM_BOT_DEFERRED_MARKER_FILE="$LOG_ROOT/telegram_bot_deferred.pending"
TELEGRAM_CODEX_PID_FILE="$LOG_ROOT/telegram_codex.pid"
MONGO_CONTAINER_NAME="${VIVENTIUM_LOCAL_MONGO_CONTAINER:-viventium-mongodb}"
MONGO_VOLUME_NAME="${VIVENTIUM_LOCAL_MONGO_VOLUME:-viventium-mongodb-data}"
MONGO_IMAGE="${MONGO_IMAGE:-mongo:8.0.17}"
MEILI_CONTAINER_NAME="${VIVENTIUM_LOCAL_MEILI_CONTAINER:-viventium-meilisearch}"
MEILI_VOLUME_NAME="${VIVENTIUM_LOCAL_MEILI_VOLUME:-viventium-meilisearch-data}"
MEILI_IMAGE="${MEILI_IMAGE:-getmeili/meilisearch:v1.12.3}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DOCKER_BIN="$(command -v docker || true)"

docker() {
  if [[ -z "$DOCKER_BIN" ]]; then
    echo "docker: command not found" >&2
    return 127
  fi

  local timeout_seconds="${VIVENTIUM_DOCKER_TIMEOUT_SECONDS:-20}"
  local docker_args=("$@")
  if [[ "${docker_args[0]:-}" == "compose" ]]; then
    local compose_timeout="${VIVENTIUM_DOCKER_COMPOSE_TIMEOUT_SECONDS:-60}"
    local compose_up_timeout="${VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS:-600}"
    timeout_seconds="$compose_timeout"
    local compose_index=1
    if [[ "${docker_args[$compose_index]:-}" == "-f" ]]; then
      compose_index=$((compose_index + 2))
    fi
    if [[ "${docker_args[$compose_index]:-}" == "up" ]]; then
      timeout_seconds="$compose_up_timeout"
    fi
  elif [[ "${docker_args[0]:-}" == "run" ]]; then
    local run_timeout="${VIVENTIUM_DOCKER_RUN_TIMEOUT_SECONDS:-300}"
    timeout_seconds="$run_timeout"
  elif [[ "${docker_args[0]:-}" == "pull" ]]; then
    local pull_timeout="${VIVENTIUM_DOCKER_PULL_TIMEOUT_SECONDS:-300}"
    timeout_seconds="$pull_timeout"
  fi
  "$PYTHON_BIN" - "$timeout_seconds" "$DOCKER_BIN" "$@" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
docker_bin = sys.argv[2]
args = [docker_bin, *sys.argv[3:]]

try:
    completed = subprocess.run(args, timeout=timeout)
except subprocess.TimeoutExpired:
    sys.stderr.write(
        f"[viventium] Docker command timed out after {timeout:.0f}s: {' '.join(args[1:])}\n"
    )
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
}

docker_daemon_ready() {
  if [[ -z "$DOCKER_BIN" ]]; then
    return 1
  fi

  local readiness_timeout="${VIVENTIUM_DOCKER_READINESS_TIMEOUT_SECONDS:-3}"
  if ! [[ "$readiness_timeout" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    readiness_timeout=3
  fi

  VIVENTIUM_DOCKER_TIMEOUT_SECONDS="$readiness_timeout" docker ps >/dev/null 2>&1
}

DOCKER_DESKTOP_LAUNCH_REQUESTED=false

request_docker_desktop_launch() {
  local message="${1:-Docker daemon not reachable; attempting to launch Docker Desktop}"

  if [[ "$DOCKER_DESKTOP_LAUNCH_REQUESTED" == "true" ]]; then
    return 0
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi
  if [[ "${VIVENTIUM_AUTO_START_DOCKER:-true}" != "true" ]]; then
    return 1
  fi
  if [[ -z "$DOCKER_BIN" ]]; then
    return 1
  fi
  if docker_daemon_ready; then
    return 0
  fi

  log_warn "$message"
  open -a Docker >/dev/null 2>&1 || true
  DOCKER_DESKTOP_LAUNCH_REQUESTED=true
  return 0
}

ensure_docker_daemon_for_service() {
  local service_label="${1:-service}"
  local message="${2:-Docker daemon not reachable; waiting for Docker Desktop before starting ${service_label}}"

  if docker_daemon_ready; then
    return 0
  fi

  request_docker_desktop_launch "$message" || true

  local retries="${VIVENTIUM_OPTIONAL_DOCKER_WAIT_RETRIES:-75}"
  if ! [[ "$retries" =~ ^[0-9]+$ ]] || [[ "$retries" -lt 1 ]]; then
    retries=75
  fi

  local poll_seconds="${VIVENTIUM_OPTIONAL_DOCKER_WAIT_POLL_SECONDS:-2}"
  if ! [[ "$poll_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    poll_seconds=2
  fi

  local attempt=0
  while [[ "$attempt" -lt "$retries" ]]; do
    if docker_daemon_ready; then
      return 0
    fi
    sleep "$poll_seconds"
    attempt=$((attempt + 1))
  done

  log_error "Docker is not running (required for ${service_label})"
  return 1
}

docker_backed_services_requested() {
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    return 1
  fi
  if [[ "$SKIP_LIVEKIT" != "true" ]]; then
    return 0
  fi
  if [[ "$START_CODE_INTERPRETER" == "true" ]]; then
    return 0
  fi
  if [[ "$START_MS365_MCP" == "true" ]]; then
    return 0
  fi
  if [[ "$START_RAG_API" == "true" && "${SKIP_LIBRECHAT:-false}" != "true" ]]; then
    return 0
  fi
  if [[ "$START_FIRECRAWL" == "true" ]]; then
    return 0
  fi
  if [[ "$START_SEARXNG" == "true" ]]; then
    return 0
  fi
  if [[ "$START_SKYVERN" == "true" ]]; then
    return 0
  fi
  return 1
}

prewarm_docker_desktop_startup() {
  if ! docker_backed_services_requested; then
    return 0
  fi
  request_docker_desktop_launch \
    "Docker daemon not reachable; starting Docker Desktop early while Viventium prepares runtime files" || true
}

generate_hex_secret() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes" 2>/dev/null | tr -d '\n'
    return 0
  fi

  "$PYTHON_BIN" - <<PY
import secrets
print(secrets.token_hex($bytes))
PY
}

resolve_local_meili_master_key() {
  if [[ -n "${MEILI_MASTER_KEY:-}" ]]; then
    printf '%s' "$MEILI_MASTER_KEY"
    return 0
  fi
  if [[ -n "${VIVENTIUM_LOCAL_MEILI_MASTER_KEY:-}" ]]; then
    printf '%s' "$VIVENTIUM_LOCAL_MEILI_MASTER_KEY"
    return 0
  fi
  if [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
    printf '%s' "$VIVENTIUM_CALL_SESSION_SECRET"
    return 0
  fi
  generate_hex_secret 32
}

is_librechat_default_secret() {
  local key="${1:-}"
  local value="${2:-}"

  case "$key:$value" in
    CREDS_KEY:CHANGE_ME_GENERATE_64_HEX_CHARS|\
    CREDS_IV:CHANGE_ME_GENERATE_32_HEX_CHARS|\
    JWT_SECRET:CHANGE_ME_GENERATE_64_HEX_CHARS|\
    JWT_REFRESH_SECRET:CHANGE_ME_GENERATE_64_HEX_CHARS)
      return 0
      ;;
  esac

  return 1
}

RUNTIME_PROFILE_OVERRIDE=""
USE_PRIVATE_OVERLAY_ENV=false
RAW_ARGS=("$@")
for ((arg_idx = 0; arg_idx < ${#RAW_ARGS[@]}; arg_idx++)); do
  raw_arg="${RAW_ARGS[$arg_idx]}"
  if is_private_overlay_arg "$raw_arg"; then
    USE_PRIVATE_OVERLAY_ENV=true
    continue
  fi
  if [[ "$raw_arg" == --profile=* ]]; then
    RUNTIME_PROFILE_OVERRIDE="${raw_arg#*=}"
    continue
  fi
  if [[ "$raw_arg" == "--profile" ]]; then
    next_idx=$((arg_idx + 1))
    if [[ "$next_idx" -lt "${#RAW_ARGS[@]}" ]]; then
      RUNTIME_PROFILE_OVERRIDE="${RAW_ARGS[$next_idx]}"
    fi
  fi
done

# ----------------------------
# Load environment from the local workspace or the optional companion workspace.
# ----------------------------
ENV_FILE_PRIMARY="${VIVENTIUM_ENV_FILE:-$(resolve_path_or_default \
  "$VIVENTIUM_CORE_DIR/.env" \
  "$VIVENTIUM_CORE_DIR/.env" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/.env" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/root.env" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/.env" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/.env")}"
ENV_FILE_LOCAL="${VIVENTIUM_ENV_LOCAL_FILE:-$(resolve_path_or_default \
  "$VIVENTIUM_CORE_DIR/.env.local" \
  "$VIVENTIUM_CORE_DIR/.env.local" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/.env.local" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/root.env.local" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/workspace-root/.env.local" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/.env.local")}"
ENV_FILE_PRIVATE_OVERLAY="${VIVENTIUM_ENV_PRIVATE_OVERLAY_FILE:-$(resolve_private_overlay_env_file)}"

load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 1
  fi

  echo -e "${CYAN}[viventium]${NC} Loading credentials from $env_file"

  while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue

    # Remove inline comments
    line="${line%%#*}"
    line=$(echo "$line" | xargs 2>/dev/null || echo "$line")

    [[ -z "$line" ]] && continue

    # Export valid key=value pairs
    if [[ "$line" =~ ^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local value="${BASH_REMATCH[2]}"
      if [[ "${VIVENTIUM_CANONICAL_ENV_LOCK_EXISTING_KEYS:-}" == "1" ]] && declare -p "$key" >/dev/null 2>&1; then
        continue
      fi
      # Remove surrounding quotes if present
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      # Correct export syntax: export KEY="value"
      export "$key"="$value"
    fi
  done < "$env_file"
  return 0
}

apply_telegram_overlay_env() {
  local overlay_file="$1"
  local _env_unset_marker="__VIVENTIUM_UNSET__"
  local preserved_names=(
    API_KEY
    BASE_URL
    BOT_TOKEN
    LIVEKIT_URL
    LIVEKIT_API_KEY
    LIVEKIT_API_SECRET
    LIVEKIT_API_HOST
    NEXT_PUBLIC_LIVEKIT_URL
    LIVEKIT_AGENT_NAME
    VIVENTIUM_LIBRECHAT_ORIGIN
    VIVENTIUM_CALL_SESSION_SECRET
    VIVENTIUM_TELEGRAM_SECRET
    VIVENTIUM_TELEGRAM_BACKEND
    WHISPER_MODE
    LOCAL_WHISPER_MODEL_PATH
    LOCAL_WHISPER_THREADS
    LOCAL_WHISPER_LANG
    LOCAL_WHISPER_VERBOSE
    STT_PROVIDER
    TTS_PROVIDER
    TTS_PROVIDER_PRIMARY
    TTS_PROVIDER_FALLBACK
    TTS_MODEL
    TTS_VOICE
    TTS_RESPONSE_FORMAT
    VIVENTIUM_STT_PROVIDER
    VIVENTIUM_TTS_PROVIDER
    VIVENTIUM_TTS_PROVIDER_FALLBACK
    VIVENTIUM_OPENAI_TTS_MODEL
    VIVENTIUM_OPENAI_TTS_VOICE
    VIVENTIUM_OPENAI_TTS_SPEED
  )
  local preserved_values=()
  local name=""
  local value=""

  for name in "${preserved_names[@]}"; do
    value="${!name-$_env_unset_marker}"
    preserved_values+=("$name" "$value")
  done

  if [[ -f "$overlay_file" ]]; then
    set -a
    source "$overlay_file"
    set +a
  fi

  local idx=0
  while [[ $idx -lt ${#preserved_values[@]} ]]; do
    name="${preserved_values[$idx]}"
    value="${preserved_values[$((idx + 1))]}"
    if [[ "$value" == "$_env_unset_marker" ]]; then
      unset "$name"
    else
      export "$name"="$value"
    fi
    idx=$((idx + 2))
  done
}

# Load .env first, then .env.local (overrides)
if [[ -n "$ENV_FILE_PRIMARY" && -f "$ENV_FILE_PRIMARY" ]]; then
  load_env_file "$ENV_FILE_PRIMARY"
fi
if [[ -n "$ENV_FILE_LOCAL" && -f "$ENV_FILE_LOCAL" ]]; then
  load_env_file "$ENV_FILE_LOCAL"
fi
if [[ "$USE_PRIVATE_OVERLAY_ENV" == "true" ]]; then
  if [[ -n "$ENV_FILE_PRIVATE_OVERLAY" && -f "$ENV_FILE_PRIVATE_OVERLAY" ]]; then
    load_env_file "$ENV_FILE_PRIVATE_OVERLAY"
  else
    echo -e "${YELLOW}[viventium]${NC} --private-overlay set but ${ENV_FILE_PRIVATE_OVERLAY:-unset} not found; continuing with base local env"
  fi
fi

# === VIVENTIUM START ===
# Purpose: Prefer structured librechat.yaml balance config over deprecated env flags.
# This keeps private legacy env files intact while avoiding noisy startup warnings.
unset CHECK_BALANCE START_BALANCE
# === VIVENTIUM END ===

# ----------------------------
# Runtime profile + isolated defaults
# ----------------------------
if [[ -n "$RUNTIME_PROFILE_OVERRIDE" ]]; then
  export VIVENTIUM_RUNTIME_PROFILE="$RUNTIME_PROFILE_OVERRIDE"
fi
if [[ -z "${VIVENTIUM_RUNTIME_PROFILE:-}" ]]; then
  export VIVENTIUM_RUNTIME_PROFILE="isolated"
fi
VIVENTIUM_RUNTIME_PROFILE="$(echo "$VIVENTIUM_RUNTIME_PROFILE" | tr '[:upper:]' '[:lower:]')"
export VIVENTIUM_RUNTIME_PROFILE
if [[ "$VIVENTIUM_RUNTIME_PROFILE" != "isolated" && "$VIVENTIUM_RUNTIME_PROFILE" != "compat" ]]; then
  echo -e "${RED}[viventium]${NC} Invalid runtime profile: $VIVENTIUM_RUNTIME_PROFILE (expected isolated|compat)"
  exit 1
fi

if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
  PROFILE_LC_API_PORT=3180
  PROFILE_LC_FRONTEND_PORT=3190
  PROFILE_PLAYGROUND_PORT=3300
  PROFILE_MONGO_PORT=27117
  PROFILE_MONGO_DB="LibreChatViventium"
  PROFILE_MEILI_PORT=7700
  PROFILE_GOOGLE_MCP_PORT=8111
  PROFILE_SCHEDULING_MCP_PORT=7110
  PROFILE_RAG_API_PORT=8110
  PROFILE_CODE_INTERPRETER_PORT=8101
  PROFILE_SKYVERN_API_PORT=8200
  PROFILE_SKYVERN_UI_PORT=8280
  PROFILE_LIVEKIT_HTTP_PORT=7888
  PROFILE_LIVEKIT_TCP_PORT=7889
  PROFILE_LIVEKIT_UDP_PORT=7890
  PROFILE_MONGO_CONTAINER="viventium-mongodb-isolated"
  PROFILE_MEILI_CONTAINER="viventium-meilisearch-isolated"
else
  PROFILE_LC_API_PORT=3080
  PROFILE_LC_FRONTEND_PORT=3090
  PROFILE_PLAYGROUND_PORT=3000
  PROFILE_MONGO_PORT=27017
  PROFILE_MONGO_DB="LibreChat"
  PROFILE_MEILI_PORT=7701
  PROFILE_GOOGLE_MCP_PORT=8000
  PROFILE_SCHEDULING_MCP_PORT=7010
  PROFILE_RAG_API_PORT=8000
  PROFILE_CODE_INTERPRETER_PORT=8001
  PROFILE_SKYVERN_API_PORT=8000
  PROFILE_SKYVERN_UI_PORT=8080
  PROFILE_LIVEKIT_HTTP_PORT=7880
  PROFILE_LIVEKIT_TCP_PORT=7881
  PROFILE_LIVEKIT_UDP_PORT=7882
  PROFILE_MONGO_CONTAINER="viventium-mongodb"
  PROFILE_MEILI_CONTAINER="viventium-meilisearch"
fi

export VIVENTIUM_LC_API_PORT="${VIVENTIUM_LC_API_PORT:-$PROFILE_LC_API_PORT}"
export VIVENTIUM_LC_FRONTEND_PORT="${VIVENTIUM_LC_FRONTEND_PORT:-$PROFILE_LC_FRONTEND_PORT}"
export VIVENTIUM_PLAYGROUND_PORT="${VIVENTIUM_PLAYGROUND_PORT:-$PROFILE_PLAYGROUND_PORT}"
export VIVENTIUM_LOCAL_MONGO_PORT="${VIVENTIUM_LOCAL_MONGO_PORT:-$PROFILE_MONGO_PORT}"
export VIVENTIUM_LOCAL_MONGO_DB="${VIVENTIUM_LOCAL_MONGO_DB:-$PROFILE_MONGO_DB}"
export VIVENTIUM_LOCAL_MEILI_PORT="${VIVENTIUM_LOCAL_MEILI_PORT:-$PROFILE_MEILI_PORT}"
export VIVENTIUM_GOOGLE_MCP_PORT="${VIVENTIUM_GOOGLE_MCP_PORT:-$PROFILE_GOOGLE_MCP_PORT}"
export VIVENTIUM_SCHEDULING_MCP_PORT="${VIVENTIUM_SCHEDULING_MCP_PORT:-$PROFILE_SCHEDULING_MCP_PORT}"
export VIVENTIUM_RAG_API_PORT="${VIVENTIUM_RAG_API_PORT:-$PROFILE_RAG_API_PORT}"
export VIVENTIUM_CODE_INTERPRETER_PORT="${VIVENTIUM_CODE_INTERPRETER_PORT:-$PROFILE_CODE_INTERPRETER_PORT}"
export VIVENTIUM_SKYVERN_API_PORT="${VIVENTIUM_SKYVERN_API_PORT:-$PROFILE_SKYVERN_API_PORT}"
export VIVENTIUM_SKYVERN_UI_PORT="${VIVENTIUM_SKYVERN_UI_PORT:-$PROFILE_SKYVERN_UI_PORT}"
export LIVEKIT_HTTP_PORT="${LIVEKIT_HTTP_PORT:-$PROFILE_LIVEKIT_HTTP_PORT}"
export LIVEKIT_TCP_PORT="${LIVEKIT_TCP_PORT:-$PROFILE_LIVEKIT_TCP_PORT}"
export LIVEKIT_UDP_PORT="${LIVEKIT_UDP_PORT:-$PROFILE_LIVEKIT_UDP_PORT}"
export VIVENTIUM_LOCAL_MONGO_CONTAINER="${VIVENTIUM_LOCAL_MONGO_CONTAINER:-$PROFILE_MONGO_CONTAINER}"
export VIVENTIUM_LOCAL_MONGO_VOLUME="${VIVENTIUM_LOCAL_MONGO_VOLUME:-${VIVENTIUM_LOCAL_MONGO_CONTAINER}-data}"
export VIVENTIUM_LOCAL_MEILI_CONTAINER="${VIVENTIUM_LOCAL_MEILI_CONTAINER:-$PROFILE_MEILI_CONTAINER}"
export VIVENTIUM_LOCAL_MEILI_VOLUME="${VIVENTIUM_LOCAL_MEILI_VOLUME:-${VIVENTIUM_LOCAL_MEILI_CONTAINER}-data}"

PROFILE_STATE_ROOT_DEFAULT="$VIVENTIUM_BASE_STATE_DIR/runtime/$VIVENTIUM_RUNTIME_PROFILE"
export VIVENTIUM_STATE_ROOT="${VIVENTIUM_STATE_ROOT:-$PROFILE_STATE_ROOT_DEFAULT}"
if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
  export VIVENTIUM_LOCAL_MONGO_DATA_PATH="${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-$VIVENTIUM_STATE_ROOT/mongo-data}"
fi
export VIVENTIUM_LOCAL_MEILI_DATA_PATH="${VIVENTIUM_LOCAL_MEILI_DATA_PATH:-$VIVENTIUM_STATE_ROOT/meili-data}"
export VIVENTIUM_RAG_PGDATA_PATH="${VIVENTIUM_RAG_PGDATA_PATH:-$VIVENTIUM_STATE_ROOT/rag-pgdata}"
export SCHEDULING_DB_PATH="${SCHEDULING_DB_PATH:-$VIVENTIUM_STATE_ROOT/scheduling/schedules.db}"
export SCHEDULING_MCP_DB_PATH="${SCHEDULING_MCP_DB_PATH:-$SCHEDULING_DB_PATH}"
export VIVENTIUM_PUBLIC_NETWORK_STATE_FILE="${VIVENTIUM_PUBLIC_NETWORK_STATE_FILE:-$VIVENTIUM_STATE_ROOT/public-network.json}"
export VIVENTIUM_CALL_TUNNEL_LOG_DIR="${VIVENTIUM_CALL_TUNNEL_LOG_DIR:-$VIVENTIUM_STATE_ROOT/logs}"
export VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT="${VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT:-$VIVENTIUM_CORE_DIR/scripts/viventium/remote_call_tunnel.py}"
export VIVENTIUM_REMOTE_CALL_MODE="${VIVENTIUM_REMOTE_CALL_MODE:-disabled}"
export VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL="${VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL:-true}"
export VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS="${VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS:-150}"
export VIVENTIUM_REMOTE_CALL_PREWARM="${VIVENTIUM_REMOTE_CALL_PREWARM:-true}"
export VIVENTIUM_REMOTE_CALL_PREWARM_TIMEOUT_SECONDS="${VIVENTIUM_REMOTE_CALL_PREWARM_TIMEOUT_SECONDS:-60}"
export VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_SECONDS="${VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_SECONDS:-3600}"
export VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE="${VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE:-$VIVENTIUM_STATE_ROOT/public-network-refresh.pid}"
export VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE="${VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE:-$VIVENTIUM_CALL_TUNNEL_LOG_DIR/remote-call-upnp-refresh.log}"
export MCP_PERSISTENT_CONNECTION_SERVERS="${MCP_PERSISTENT_CONNECTION_SERVERS:-scheduling-cortex}"
export MCP_PERSISTENT_WARMUP_COOLDOWN_MS="${MCP_PERSISTENT_WARMUP_COOLDOWN_MS:-10000}"
export MCP_CONNECTION_STATUS_SETTLE_WINDOW_MS="${MCP_CONNECTION_STATUS_SETTLE_WINDOW_MS:-3500}"
export MCP_CONNECTION_STATUS_SETTLE_POLL_MS="${MCP_CONNECTION_STATUS_SETTLE_POLL_MS:-500}"
mkdir -p "$VIVENTIUM_RAG_PGDATA_PATH"

# === VIVENTIUM START ===
# Feature: Curated local OpenAI model inventory.
# Purpose: Prevent local Viventium from falling back to older OpenAI families.
# The launcher owns the default local OpenAI model inventory for both the chat
# surface and Agent Builder/Assistants surface, while still allowing explicit
# env overrides when needed.
DEFAULT_VIVENTIUM_OPENAI_MODELS="gpt-5.4,gpt-5,gpt-5-chat-latest,gpt-5-mini,gpt-5-nano,o3,o4-mini"
DEFAULT_VIVENTIUM_ASSISTANTS_MODELS="gpt-5.4,gpt-5,gpt-5-chat-latest,gpt-5-codex,gpt-5-mini,gpt-5-nano,o3,o4-mini"
CONNECTED_ACCOUNT_VIVENTIUM_OPENAI_MODELS="gpt-5.4,gpt-5.4-pro,gpt-5,gpt-5-pro,gpt-5-chat-latest,gpt-5-codex,gpt-5-mini,gpt-5-nano,o3-pro,o3,o4-mini"
CONNECTED_ACCOUNT_VIVENTIUM_ASSISTANTS_MODELS="gpt-5.4,gpt-5.4-pro,gpt-5,gpt-5-pro,gpt-5-chat-latest,gpt-5-codex,gpt-5-mini,gpt-5-nano,o3-pro,o3,o4-mini"
# === VIVENTIUM END ===

MONGO_CONTAINER_NAME="$VIVENTIUM_LOCAL_MONGO_CONTAINER"
MONGO_VOLUME_NAME="$VIVENTIUM_LOCAL_MONGO_VOLUME"
MEILI_CONTAINER_NAME="$VIVENTIUM_LOCAL_MEILI_CONTAINER"
MEILI_VOLUME_NAME="$VIVENTIUM_LOCAL_MEILI_VOLUME"
LOG_ROOT="$VIVENTIUM_STATE_ROOT"
LOG_DIR="$LOG_ROOT/logs"
GOOGLE_MCP_PID_FILE="$LOG_ROOT/google_workspace_mcp.pid"
SCHEDULING_MCP_PID_FILE="$LOG_ROOT/scheduling_cortex_mcp.pid"
GLASSHIVE_RUNTIME_PID_FILE="$LOG_ROOT/glasshive_runtime.pid"
GLASSHIVE_MCP_PID_FILE="$LOG_ROOT/glasshive_mcp.pid"
GLASSHIVE_UI_PID_FILE="$LOG_ROOT/glasshive_ui.pid"
TELEGRAM_BOT_PID_FILE="$LOG_ROOT/telegram_bot.pid"
TELEGRAM_BOT_DEFERRED_PID_FILE="$LOG_ROOT/telegram_bot_deferred.pid"
TELEGRAM_BOT_DEFERRED_MARKER_FILE="$LOG_ROOT/telegram_bot_deferred.pending"
TELEGRAM_CODEX_PID_FILE="$LOG_ROOT/telegram_codex.pid"
DETACHED_LAUNCH_PGID_FILE="$LOG_ROOT/detached-launch.pgid"
LIBRECHAT_API_WATCHDOG_PID_FILE="$LOG_ROOT/librechat-api-watchdog.pid"
LIBRECHAT_API_WATCHDOG_LOG_FILE="$LOG_DIR/librechat-api-watchdog.log"
MONGO_NATIVE_PID_FILE="$LOG_ROOT/mongodb-native.pid"
MONGO_NATIVE_LOG_FILE="$LOG_DIR/mongodb-native.log"
MEILI_NATIVE_PID_FILE="$LOG_ROOT/meilisearch-native.pid"
MEILI_NATIVE_LOG_FILE="$LOG_DIR/meilisearch-native.log"
mkdir -p "$LOG_DIR" "$(dirname "$SCHEDULING_DB_PATH")"

LC_API_PORT="$VIVENTIUM_LC_API_PORT"
LC_FRONTEND_PORT="$VIVENTIUM_LC_FRONTEND_PORT"
LC_API_URL="http://localhost:${LC_API_PORT}"
LC_FRONTEND_URL="http://localhost:${LC_FRONTEND_PORT}"

# ----------------------------
# Defaults (after loading env files)
# ----------------------------

# === VIVENTIUM START ===
# Feature: Local timezone fallback hardening for one-click runs.
# Purpose: If no explicit timezone is configured, derive the host IANA timezone
# so time-context injection does not default to UTC on local machines.
if [[ -z "${VIVENTIUM_DEFAULT_TIMEZONE:-}" ]]; then
  _detected_timezone=""
  if command -v node >/dev/null 2>&1; then
    _detected_timezone="$(node -e 'process.stdout.write(Intl.DateTimeFormat().resolvedOptions().timeZone || "")' 2>/dev/null || true)"
  fi
  if [[ -z "$_detected_timezone" ]] && command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    _detected_timezone="$("$PYTHON_BIN" - <<'PY'
import datetime
try:
    print(datetime.datetime.now().astimezone().tzinfo.key)
except Exception:
    print("")
PY
)"
  fi
  if [[ -z "$_detected_timezone" ]]; then
    _detected_timezone="UTC"
  fi
  export VIVENTIUM_DEFAULT_TIMEZONE="$_detected_timezone"
  echo -e "${YELLOW}[viventium]${NC} VIVENTIUM_DEFAULT_TIMEZONE not set; using ${VIVENTIUM_DEFAULT_TIMEZONE}"
fi
# === VIVENTIUM END ===

# LiveKit defaults for dev mode
export LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-devkey}"
export LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-secret}"
export LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:${LIVEKIT_HTTP_PORT}}"
export LIVEKIT_API_HOST="${LIVEKIT_API_HOST:-http://localhost:${LIVEKIT_HTTP_PORT}}"
export NEXT_PUBLIC_LIVEKIT_URL="${NEXT_PUBLIC_LIVEKIT_URL:-$LIVEKIT_URL}"
# === VIVENTIUM START ===
# Feature: Normalize stale compat-era local URLs when isolated profile is selected.
# Purpose: Keep private legacy env overlays intact while ensuring the isolated
# runtime uses the current profile-derived playground/LiveKit endpoints and
# generated local LiveKit credentials.
if [[ "${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" ]]; then
  if [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
    if [[ "${LIVEKIT_API_KEY}" == "devkey" ]]; then
      export LIVEKIT_API_KEY="viventium-local"
    fi
    if [[ "${LIVEKIT_API_SECRET}" == "secret" ]]; then
      export LIVEKIT_API_SECRET="${VIVENTIUM_CALL_SESSION_SECRET}"
    fi
  fi
  if [[ "${LIVEKIT_URL}" == "ws://localhost:7880" ]]; then
    export LIVEKIT_URL="ws://localhost:${LIVEKIT_HTTP_PORT}"
  fi
  if [[ "${LIVEKIT_API_HOST}" == "http://localhost:7880" ]]; then
    export LIVEKIT_API_HOST="http://localhost:${LIVEKIT_HTTP_PORT}"
  fi
  if [[ "${NEXT_PUBLIC_LIVEKIT_URL}" == "ws://localhost:7880" ]]; then
    export NEXT_PUBLIC_LIVEKIT_URL="$LIVEKIT_URL"
  fi
fi
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Fix: Default LiveKit node IP to a LAN-reachable address instead of loopback.
# Reason: secure remote-device calls can succeed at HTTPS/WSS signaling while still failing WebRTC
# ICE if LiveKit advertises only `127.0.0.1` candidates.
export LIVEKIT_NODE_IP="${LIVEKIT_NODE_IP:-$(detect_livekit_node_ip)}"
# === VIVENTIUM END ===
# Default agent name for LiveKit dispatch (preserve explicit empty if desired)
export LIVEKIT_AGENT_NAME="${LIVEKIT_AGENT_NAME-viventium}"

# Code interpreter defaults (LibreCodeInterpreter)
CODE_INTERPRETER_PORT="${CODE_INTERPRETER_PORT:-$VIVENTIUM_CODE_INTERPRETER_PORT}"
CODE_BASEURL_WAS_DEFAULT=false
if [[ -z "${LIBRECHAT_CODE_BASEURL:-}" ]]; then
  CODE_BASEURL_WAS_DEFAULT=true
  export LIBRECHAT_CODE_BASEURL="http://localhost:${CODE_INTERPRETER_PORT}"
fi
export LIBRECHAT_CODE_API_KEY="${LIBRECHAT_CODE_API_KEY:-${CODE_API_KEY:-}}"
export CODE_API_KEY="${CODE_API_KEY:-${LIBRECHAT_CODE_API_KEY:-}}"
if [[ -n "${LIBRECHAT_CODE_BASEURL:-}" ]]; then
  ci_port_candidate="${LIBRECHAT_CODE_BASEURL##*:}"
  ci_port_candidate="${ci_port_candidate%%/*}"
  if [[ "$ci_port_candidate" =~ ^[0-9]+$ ]]; then
    CODE_INTERPRETER_PORT="$ci_port_candidate"
  fi
fi

# LibreChat database defaults
if [[ -z "${MONGO_URI:-}" ]]; then
  export MONGO_URI="mongodb://127.0.0.1:${VIVENTIUM_LOCAL_MONGO_PORT}/${VIVENTIUM_LOCAL_MONGO_DB}"
fi

# === VIVENTIUM START ===
# Feature: Local conversation search parity with upstream LibreChat.
# Purpose: Enable Meilisearch-backed message/conversation search for local runs,
# including first-time backfill of existing history.
export SEARCH="${SEARCH:-true}"
export MEILI_NO_ANALYTICS="${MEILI_NO_ANALYTICS:-true}"
export MEILI_SYNC_THRESHOLD="${MEILI_SYNC_THRESHOLD:-0}"
if [[ -z "${MEILI_MASTER_KEY:-}" ]]; then
  export MEILI_MASTER_KEY="$(resolve_local_meili_master_key)"
fi
if [[ -z "${MEILI_HOST:-}" ]]; then
  export MEILI_HOST="http://127.0.0.1:${VIVENTIUM_LOCAL_MEILI_PORT}"
fi
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Skyvern Browser Agent defaults.
# Purpose: Provide stable local defaults for Skyvern API/UI ports.
# === VIVENTIUM END ===
export SKYVERN_API_PORT="${SKYVERN_API_PORT:-$VIVENTIUM_SKYVERN_API_PORT}"
export SKYVERN_UI_PORT="${SKYVERN_UI_PORT:-$VIVENTIUM_SKYVERN_UI_PORT}"
expected_skyvern_base_url="http://localhost:${SKYVERN_API_PORT}"
expected_skyvern_app_url="http://localhost:${SKYVERN_UI_PORT}"
if [[ -z "${SKYVERN_BASE_URL:-}" || "${SKYVERN_BASE_URL}" != "${expected_skyvern_base_url}" ]]; then
  export SKYVERN_BASE_URL="${expected_skyvern_base_url}"
fi
if [[ -z "${SKYVERN_APP_URL:-}" || "${SKYVERN_APP_URL}" != "${expected_skyvern_app_url}" ]]; then
  export SKYVERN_APP_URL="${expected_skyvern_app_url}"
fi

# SearxNG defaults
SEARXNG_PORT="${SEARXNG_PORT:-8082}"
if [[ -z "${SEARXNG_INSTANCE_URL:-}" ]]; then
  export SEARXNG_INSTANCE_URL="http://localhost:${SEARXNG_PORT}"
fi
if [[ -z "${SEARXNG_BASE_URL:-}" ]]; then
  export SEARXNG_BASE_URL="${SEARXNG_INSTANCE_URL%/}/"
fi

# Firecrawl defaults
FIRECRAWL_PORT="${FIRECRAWL_PORT:-3003}"
if [[ -z "${FIRECRAWL_BASE_URL:-}" ]]; then
  export FIRECRAWL_BASE_URL="http://localhost:${FIRECRAWL_PORT}"
fi
if [[ -z "${FIRECRAWL_VERSION:-}" ]]; then
  export FIRECRAWL_VERSION="v2"
fi
if [[ -z "${FIRECRAWL_API_URL:-}" ]]; then
  export FIRECRAWL_API_URL="${FIRECRAWL_BASE_URL%/}"
fi
# === VIVENTIUM START ===
# Feature: Normalize Firecrawl API URL for LibreChat tool compatibility.
# Purpose: `createFirecrawlScraper()` appends `/${FIRECRAWL_VERSION}/scrape`, so API_URL must be a base URL.
if [[ "${FIRECRAWL_API_URL}" =~ ^(https?://[^[:space:]]+)/v[0-9]+$ ]]; then
  local_firecrawl_base="${BASH_REMATCH[1]}"
  export FIRECRAWL_API_URL="${local_firecrawl_base}"
fi
# === VIVENTIUM END ===

# MCP defaults (used by LibreChat + v1 agent)
GOOGLE_MCP_PORT_WAS_DEFAULT=false
if [[ -z "${GOOGLE_MCP_PORT:-}" ]]; then
  GOOGLE_MCP_PORT_WAS_DEFAULT=true
  GOOGLE_MCP_PORT="$VIVENTIUM_GOOGLE_MCP_PORT"
fi
GOOGLE_MCP_URLS_WERE_DEFAULT=true
google_default_origin="http://localhost:${GOOGLE_MCP_PORT}"
google_default_url="${google_default_origin}/mcp"
google_default_auth="${google_default_origin}/authorize"
google_default_token="${google_default_origin}/token"
google_default_legacy_auth="${google_default_origin}/oauth2/authorize"
google_default_legacy_token="${google_default_origin}/oauth2/token"
google_legacy_compat_origin="http://localhost:8000"
google_legacy_compat_url="${google_legacy_compat_origin}/mcp"
google_legacy_compat_auth="${google_legacy_compat_origin}/authorize"
google_legacy_compat_token="${google_legacy_compat_origin}/token"
google_legacy_compat_auth_oauth2="${google_legacy_compat_origin}/oauth2/authorize"
google_legacy_compat_token_oauth2="${google_legacy_compat_origin}/oauth2/token"
is_default_google_auth_url() {
  local value="${1:-}"
  [[ -z "$value" ]] && return 1
  if [[ "$value" == "$google_default_auth" ]]; then
    return 0
  fi
  if [[ "${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" ]]; then
    case "$value" in
      "$google_default_legacy_auth"|"$google_legacy_compat_auth"|"$google_legacy_compat_auth_oauth2")
        return 0
        ;;
    esac
  fi
  return 1
}
is_default_google_token_url() {
  local value="${1:-}"
  [[ -z "$value" ]] && return 1
  if [[ "$value" == "$google_default_token" ]]; then
    return 0
  fi
  if [[ "${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" ]]; then
    case "$value" in
      "$google_default_legacy_token"|"$google_legacy_compat_token"|"$google_legacy_compat_token_oauth2")
        return 0
        ;;
    esac
  fi
  return 1
}
if [[ -n "${GOOGLE_WORKSPACE_MCP_URL:-}" &&
  "${GOOGLE_WORKSPACE_MCP_URL}" != "$google_default_url" &&
  ! ("${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" && "${GOOGLE_WORKSPACE_MCP_URL}" == "$google_legacy_compat_url") ]]; then
  GOOGLE_MCP_URLS_WERE_DEFAULT=false
fi
if [[ -n "${GOOGLE_WORKSPACE_MCP_AUTH_URL:-}" ]] && ! is_default_google_auth_url "${GOOGLE_WORKSPACE_MCP_AUTH_URL}"; then
  GOOGLE_MCP_URLS_WERE_DEFAULT=false
fi
if [[ -n "${GOOGLE_WORKSPACE_MCP_TOKEN_URL:-}" ]] && ! is_default_google_token_url "${GOOGLE_WORKSPACE_MCP_TOKEN_URL}"; then
  GOOGLE_MCP_URLS_WERE_DEFAULT=false
fi
MS365_MCP_PORT="${MS365_MCP_PORT:-6274}"
MS365_MCP_CALLBACK_PORT="${MS365_MCP_CALLBACK_PORT:-3002}"
MS365_MCP_RUNTIME_EXPORT_FILE="${MS365_MCP_RUNTIME_EXPORT_FILE:-$VIVENTIUM_STATE_ROOT/ms365_mcp.runtime.env}"
DEFAULT_MS365_MCP_SCOPE="User.Read Mail.ReadWrite Calendars.ReadWrite Files.ReadWrite.All Sites.Read.All Team.ReadBasic.All Channel.ReadBasic.All Tasks.ReadWrite Contacts.Read Notes.Read offline_access"
if [[ -z "${MS365_MCP_SCOPE:-}" ]]; then
  export MS365_MCP_SCOPE="$DEFAULT_MS365_MCP_SCOPE"
elif [[ "${VIVENTIUM_ALLOW_MINIMAL_MS365_SCOPE:-0}" != "1" ]]; then
  case "${MS365_MCP_SCOPE}" in
    "User.Read"|"User.Read offline_access")
      export MS365_MCP_SCOPE="$DEFAULT_MS365_MCP_SCOPE"
      ;;
  esac
fi
DEFAULT_GOOGLE_WORKSPACE_MCP_SCOPE="openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/chat.messages.readonly https://www.googleapis.com/auth/chat.messages https://www.googleapis.com/auth/chat.spaces https://www.googleapis.com/auth/forms.body https://www.googleapis.com/auth/forms.body.readonly https://www.googleapis.com/auth/forms.responses.readonly https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/presentations.readonly https://www.googleapis.com/auth/tasks https://www.googleapis.com/auth/tasks.readonly https://www.googleapis.com/auth/cse"
export GOOGLE_WORKSPACE_MCP_SCOPE="${GOOGLE_WORKSPACE_MCP_SCOPE:-$DEFAULT_GOOGLE_WORKSPACE_MCP_SCOPE}"
refresh_google_mcp_urls() {
  local default_origin="http://localhost:${GOOGLE_MCP_PORT}"
  if [[ "$GOOGLE_MCP_URLS_WERE_DEFAULT" == "true" ]]; then
    export GOOGLE_WORKSPACE_MCP_URL="${default_origin}/mcp"
    export GOOGLE_WORKSPACE_MCP_AUTH_URL="${default_origin}/authorize"
    export GOOGLE_WORKSPACE_MCP_TOKEN_URL="${default_origin}/token"
    return 0
  fi

  local origin="$default_origin"
  if [[ -n "${GOOGLE_WORKSPACE_MCP_URL:-}" ]]; then
    local parsed_origin
    parsed_origin=$(echo "$GOOGLE_WORKSPACE_MCP_URL" | awk -F/ '{print $1"//"$3}')
    if [[ -n "$parsed_origin" && "$parsed_origin" != "//" ]]; then
      origin="$parsed_origin"
    fi
  fi

  if [[ -z "${GOOGLE_WORKSPACE_MCP_URL:-}" ]]; then
    export GOOGLE_WORKSPACE_MCP_URL="${origin}/mcp"
  fi
  if [[ -z "${GOOGLE_WORKSPACE_MCP_AUTH_URL:-}" ]]; then
    export GOOGLE_WORKSPACE_MCP_AUTH_URL="${origin}/authorize"
  fi
  if [[ -z "${GOOGLE_WORKSPACE_MCP_TOKEN_URL:-}" ]]; then
    export GOOGLE_WORKSPACE_MCP_TOKEN_URL="${origin}/token"
  fi
}
refresh_google_mcp_urls
export MS365_MCP_SERVER_URL="${MS365_MCP_SERVER_URL:-http://localhost:${MS365_MCP_PORT}/mcp}"
export MS365_MCP_AUTH_URL="${MS365_MCP_AUTH_URL:-http://localhost:${MS365_MCP_PORT}/authorize}"
export MS365_MCP_TOKEN_URL="${MS365_MCP_TOKEN_URL:-http://localhost:${MS365_MCP_PORT}/token}"
export MS365_MCP_TRANSPORT="${MS365_MCP_TRANSPORT:-streamable-http}"
export MS365_MCP_REDIRECT_URI="${MS365_MCP_REDIRECT_URI:-${LC_API_URL}/api/mcp/ms-365/oauth/callback}"
export GOOGLE_WORKSPACE_MCP_REDIRECT_URI="${GOOGLE_WORKSPACE_MCP_REDIRECT_URI:-${LC_API_URL}/api/mcp/google_workspace/oauth/callback}"

write_ms365_runtime_exports() {
  local export_file="${MS365_MCP_RUNTIME_EXPORT_FILE:-${VIVENTIUM_STATE_ROOT:-${TMPDIR:-/tmp}/viventium}/ms365_mcp.runtime.env}"
  MS365_MCP_RUNTIME_EXPORT_FILE="$export_file"
  export MS365_MCP_RUNTIME_EXPORT_FILE
  mkdir -p "$(dirname "$export_file")"
  {
    printf 'MS365_MCP_PORT=%s\n' "$MS365_MCP_PORT"
    printf 'MS365_MCP_SERVER_URL=%s\n' "$MS365_MCP_SERVER_URL"
    printf 'MS365_MCP_AUTH_URL=%s\n' "$MS365_MCP_AUTH_URL"
    printf 'MS365_MCP_TOKEN_URL=%s\n' "$MS365_MCP_TOKEN_URL"
  } >"$export_file"

  local runtime_env_file="${VIVENTIUM_ENV_FILE:-}"
  if [[ -n "$runtime_env_file" && -f "$runtime_env_file" ]]; then
    "$PYTHON_BIN" - "$runtime_env_file" \
      "MS365_MCP_PORT=$MS365_MCP_PORT" \
      "MS365_MCP_SERVER_URL=$MS365_MCP_SERVER_URL" \
      "MS365_MCP_AUTH_URL=$MS365_MCP_AUTH_URL" \
      "MS365_MCP_TOKEN_URL=$MS365_MCP_TOKEN_URL" <<'PY'
from pathlib import Path
import sys

runtime_env_path = Path(sys.argv[1])
updates = {}
for arg in sys.argv[2:]:
    key, value = arg.split("=", 1)
    updates[key] = value

lines = runtime_env_path.read_text(encoding="utf-8").splitlines()
seen: set[str] = set()
out: list[str] = []

for line in lines:
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        out.append(line)
        continue

    key, _value = line.split("=", 1)
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

runtime_env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  fi
}

load_ms365_runtime_exports_if_present() {
  local export_file="${MS365_MCP_RUNTIME_EXPORT_FILE:-${VIVENTIUM_STATE_ROOT:-${TMPDIR:-/tmp}/viventium}/ms365_mcp.runtime.env}"
  MS365_MCP_RUNTIME_EXPORT_FILE="$export_file"
  export MS365_MCP_RUNTIME_EXPORT_FILE
  if [[ ! -f "$export_file" ]]; then
    return 1
  fi

  # shellcheck disable=SC1090
  source "$export_file"
  export MS365_MCP_PORT MS365_MCP_SERVER_URL MS365_MCP_AUTH_URL MS365_MCP_TOKEN_URL
  return 0
}

refresh_parallel_runtime_endpoint_overrides() {
  if [[ "$START_MS365_MCP" == "true" ]]; then
    local attempts=0
    while [[ "$attempts" -lt 5 ]]; do
      if load_ms365_runtime_exports_if_present; then
        break
      fi
      sleep 1
      attempts=$((attempts + 1))
    done
  fi
}

# === VIVENTIUM START ===
# Feature: Ensure call session secret is set before scheduler secret derivation.
# NOTE: The public install path should provide this via generated config; the
# direct launcher keeps a safe ephemeral fallback for private developer runs.
# === VIVENTIUM END ===
if [[ -z "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
  export VIVENTIUM_CALL_SESSION_SECRET="$(generate_hex_secret 32)"
  echo -e "${YELLOW}[viventium]${NC} VIVENTIUM_CALL_SESSION_SECRET not set; generated an ephemeral secret for this session"
fi
SCHEDULING_MCP_PORT="${SCHEDULING_MCP_PORT:-$VIVENTIUM_SCHEDULING_MCP_PORT}"
GLASSHIVE_RUNTIME_PORT="${GLASSHIVE_RUNTIME_PORT:-8766}"
GLASSHIVE_MCP_PORT="${GLASSHIVE_MCP_PORT:-8767}"
GLASSHIVE_UI_PORT="${GLASSHIVE_UI_PORT:-8780}"
SCHEDULER_SECRET_GENERATED=false
if [[ -z "${VIVENTIUM_SCHEDULER_SECRET:-}" ]]; then
  if [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
    export VIVENTIUM_SCHEDULER_SECRET="$VIVENTIUM_CALL_SESSION_SECRET"
  elif [[ -n "${VIVENTIUM_TELEGRAM_SECRET:-}" ]]; then
    export VIVENTIUM_SCHEDULER_SECRET="$VIVENTIUM_TELEGRAM_SECRET"
  else
    if command -v openssl >/dev/null 2>&1; then
      export VIVENTIUM_SCHEDULER_SECRET="$(openssl rand -hex 32)"
    else
      export VIVENTIUM_SCHEDULER_SECRET="$("$PYTHON_BIN" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
    fi
    SCHEDULER_SECRET_GENERATED=true
  fi
fi
if [[ -z "${SCHEDULING_MCP_URL:-}" ]]; then
  export SCHEDULING_MCP_URL="http://localhost:${SCHEDULING_MCP_PORT}/mcp"
fi
export SCHEDULER_LIBRECHAT_URL="${SCHEDULER_LIBRECHAT_URL:-${LC_API_URL}}"
if [[ -n "${VIVENTIUM_SCHEDULER_SECRET:-}" && -z "${SCHEDULER_LIBRECHAT_SECRET:-}" ]]; then
  export SCHEDULER_LIBRECHAT_SECRET="$VIVENTIUM_SCHEDULER_SECRET"
fi
# === VIVENTIUM START ===
# Feature: Align scheduler Telegram secret with bridge defaults.
# Purpose: Match telegram.js fallback (call session secret) to avoid dispatch failures.
# === VIVENTIUM END ===
if [[ -z "${SCHEDULER_TELEGRAM_SECRET:-}" ]]; then
  if [[ -n "${VIVENTIUM_TELEGRAM_SECRET:-}" ]]; then
    export SCHEDULER_TELEGRAM_SECRET="$VIVENTIUM_TELEGRAM_SECRET"
  elif [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
    export SCHEDULER_TELEGRAM_SECRET="$VIVENTIUM_CALL_SESSION_SECRET"
  elif [[ -n "${VIVENTIUM_SCHEDULER_SECRET:-}" ]]; then
    export SCHEDULER_TELEGRAM_SECRET="$VIVENTIUM_SCHEDULER_SECRET"
  fi
fi
# === VIVENTIUM START ===
# Feature: Prefer tracked built-in bundle when deriving main agent id.
detect_viventium_main_agent_config_path() {
  local artifacts_root="${VIVENTIUM_ARTIFACTS_DIR:-$VIVENTIUM_BASE_STATE_DIR/artifacts}"
  local latest_path_file="$artifacts_root/agents-sync/LATEST_PATH"
  local latest_dir=""
  local candidate=""

  for candidate in \
    "${LIBRECHAT_AGENTS_BUNDLE_FILE:-}" \
    "$LIBRECHAT_DIR/viventium/source_of_truth/local.viventium-agents.yaml"
  do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
      printf "%s" "$candidate"
      return 0
    fi
  done

  if [[ -f "$latest_path_file" ]]; then
    latest_dir="$(tr -d '\r' < "$latest_path_file" | head -n 1 | xargs)"
    if [[ -n "$latest_dir" && -f "$latest_dir/viventium-agents.yaml" ]]; then
      printf "%s" "$latest_dir/viventium-agents.yaml"
      return 0
    fi
  fi

  for candidate in \
    "$LIBRECHAT_DIR/tmp/viventium-agents.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-260127.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-260127-b.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-clawd.yaml"
  do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
      printf "%s" "$candidate"
      return 0
    fi
  done

  return 1
}

# === VIVENTIUM START ===
# Feature: Derive main agent id for MCP headers if env is missing.
# === VIVENTIUM END ===
if [[ -z "${VIVENTIUM_MAIN_AGENT_ID:-}" ]]; then
  AGENTS_CONFIG_PATH="$(detect_viventium_main_agent_config_path || true)"
  if [[ -f "$AGENTS_CONFIG_PATH" ]]; then
    DERIVED_MAIN_AGENT_ID="$(
      AGENTS_CONFIG_PATH="$AGENTS_CONFIG_PATH" "$PYTHON_BIN" - <<'PY'
import os
import re
from pathlib import Path

path = Path(os.environ.get("AGENTS_CONFIG_PATH", ""))
if not path.exists():
    print("")
    raise SystemExit(0)
text = path.read_text(encoding="utf-8")
match = re.search(r"^\\s*mainAgentId:\\s*(\\S+)\\s*$", text, re.M)
print(match.group(1) if match else "")
PY
    )"
    if [[ -n "$DERIVED_MAIN_AGENT_ID" ]]; then
      export VIVENTIUM_MAIN_AGENT_ID="$DERIVED_MAIN_AGENT_ID"
      log_info "VIVENTIUM_MAIN_AGENT_ID derived from $AGENTS_CONFIG_PATH"
    fi
  fi
fi
if [[ -n "${GOOGLE_CLIENT_ID:-}" && -z "${GOOGLE_OAUTH_CLIENT_ID:-}" ]]; then
  export GOOGLE_OAUTH_CLIENT_ID="$GOOGLE_CLIENT_ID"
fi
if [[ -n "${GOOGLE_CLIENT_SECRET:-}" && -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
  export GOOGLE_OAUTH_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET"
fi

# Viventium defaults
PLAYGROUND_URL_WAS_DEFAULT=false
if [[ -z "${VIVENTIUM_PLAYGROUND_URL:-}" ]]; then
  PLAYGROUND_URL_WAS_DEFAULT=true
  export VIVENTIUM_PLAYGROUND_URL="http://localhost:${VIVENTIUM_PLAYGROUND_PORT}"
fi
# === VIVENTIUM START ===
# Feature: Normalize stale compat-era playground URLs when isolated profile is selected.
# Purpose: Avoid opening the legacy compat port when the modern isolated profile
# should use the current launcher-derived playground port.
if [[ "${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" && "${VIVENTIUM_PLAYGROUND_URL}" == "http://localhost:3000" ]]; then
  PLAYGROUND_URL_WAS_DEFAULT=true
  export VIVENTIUM_PLAYGROUND_URL="http://localhost:${VIVENTIUM_PLAYGROUND_PORT}"
fi
# === VIVENTIUM END ===
export VIVENTIUM_LIBRECHAT_ORIGIN="${VIVENTIUM_LIBRECHAT_ORIGIN:-${LC_API_URL}}"
# === VIVENTIUM START ===
# Feature: Disable per-chunk usage streaming to suppress merge warnings by default.
# === VIVENTIUM END ===
if [[ -z "${VIVENTIUM_DISABLE_STREAM_USAGE:-}" ]]; then
  export VIVENTIUM_DISABLE_STREAM_USAGE="1"
fi
# === VIVENTIUM START ===
# Feature: STT defaults + voice concurrency bypass
# Added: 2026-01-11
# === VIVENTIUM END ===
if [[ -z "${VIVENTIUM_STT_PROVIDER:-}" && -n "${STT_PROVIDER:-}" ]]; then
  export VIVENTIUM_STT_PROVIDER="$STT_PROVIDER"
fi
if [[ -z "${VIVENTIUM_STT_PROVIDER:-}" ]]; then
  export VIVENTIUM_STT_PROVIDER="whisper_local"
fi
if [[ -z "${VIVENTIUM_VOICE_BYPASS_CONCURRENCY:-}" ]]; then
  export VIVENTIUM_VOICE_BYPASS_CONCURRENCY="true"
fi
if [[ -z "${VIVENTIUM_VOICE_GATEWAY_AGENT_NAME:-}" ]]; then
  # Use one stable dispatch name and rely on runtime cleanup to remove leftovers.
  export VIVENTIUM_VOICE_GATEWAY_AGENT_NAME="librechat-voice-gateway"
  echo -e "${YELLOW}[viventium]${NC} VIVENTIUM_VOICE_GATEWAY_AGENT_NAME not set; using ${VIVENTIUM_VOICE_GATEWAY_AGENT_NAME}"
fi
export VIVENTIUM_VOICE_GATEWAY_LOG_LEVEL="${VIVENTIUM_VOICE_GATEWAY_LOG_LEVEL:-INFO}"

# Prefer Cartesia if available and no explicit provider is set.
if [[ -z "${VIVENTIUM_TTS_PROVIDER:-}" ]] && [[ -n "${CARTESIA_API_KEY:-}" ]]; then
  export VIVENTIUM_TTS_PROVIDER="cartesia"
  echo -e "${YELLOW}[viventium]${NC} CARTESIA_API_KEY detected; defaulting VIVENTIUM_TTS_PROVIDER=cartesia"
fi

SKIP_LIVEKIT=false
SKIP_LIBRECHAT=false
SKIP_PLAYGROUND=false
SKIP_VOICE_GATEWAY=false
SKIP_GOOGLE_MCP=false
SKIP_MS365_MCP=false
SKIP_SCHEDULING_MCP=false
SKIP_GLASSHIVE=false
SKIP_RAG_API=false
# === VIVENTIUM START ===
# Feature: Skyvern skip flag wiring.
# === VIVENTIUM END ===
SKIP_SKYVERN=false
SKIP_CODE_INTERPRETER=false
SKIP_FIRECRAWL=false
SKIP_TELEGRAM=false
SKIP_V1_AGENT=false
SKIP_DOCKER=false
SKIP_HEALTH_CHECKS=false
SKIP_V1_SYNC=false
SKIP_VOICE_DEPS=false
SKIP_MCP_VERIFY=false
SKIP_BOOTSTRAP=false
RESTART_SERVICES=false
STOP_ONLY=false
PLAYGROUND_VARIANT="${PLAYGROUND_VARIANT:-modern}"
PLAYGROUND_START_BLOCKED=false
PLAYGROUND_PORT=""

# === VIVENTIUM START ===
# Feature: Sanitize invisible Unicode spaces in CLI args.
# Purpose: Rich-text copy/paste can append NBSP-like chars that look empty but break arg parsing.
normalize_cli_arg() {
  local arg="$1"
  local nbsp=$'\u00A0'
  local narrow_nbsp=$'\u202F'
  local figure_space=$'\u2007'
  arg="${arg//$nbsp/ }"
  arg="${arg//$narrow_nbsp/ }"
  arg="${arg//$figure_space/ }"
  arg="${arg#"${arg%%[![:space:]]*}"}"
  arg="${arg%"${arg##*[![:space:]]}"}"
  printf '%s' "$arg"
}
# === VIVENTIUM END ===

while [[ $# -gt 0 ]]; do
  # === VIVENTIUM START ===
  # Normalize invisible Unicode spacing from copy/paste and ignore empty args.
  current_arg="$(normalize_cli_arg "$1")"
  if [[ -z "$current_arg" ]]; then
    shift
    continue
  fi
  if is_private_overlay_arg "$current_arg"; then
    shift
    continue
  fi
  # === VIVENTIUM END ===
  case "$current_arg" in
    --skip-livekit) SKIP_LIVEKIT=true; shift ;;
    --skip-librechat) SKIP_LIBRECHAT=true; shift ;;
    --skip-playground) SKIP_PLAYGROUND=true; shift ;;
    --modern-playground) PLAYGROUND_VARIANT="modern"; shift ;;
    --classic-playground) PLAYGROUND_VARIANT="classic"; shift ;;
    --skip-voice-gateway) SKIP_VOICE_GATEWAY=true; shift ;;
    --skip-google-mcp) SKIP_GOOGLE_MCP=true; shift ;;
    --skip-ms365-mcp) SKIP_MS365_MCP=true; shift ;;
    --skip-scheduling-mcp) SKIP_SCHEDULING_MCP=true; shift ;;
    --skip-glasshive) SKIP_GLASSHIVE=true; shift ;;
    --skip-rag-api) SKIP_RAG_API=true; shift ;;
    # === VIVENTIUM START ===
    # Feature: Skyvern skip flag handling.
    # === VIVENTIUM END ===
    --skip-skyvern) SKIP_SKYVERN=true; shift ;;
    --skip-code-interpreter) SKIP_CODE_INTERPRETER=true; shift ;;
    --skip-firecrawl) SKIP_FIRECRAWL=true; shift ;;
    --skip-telegram) SKIP_TELEGRAM=true; shift ;;
    --skip-v1-agent) SKIP_V1_AGENT=true; shift ;;
    --skip-docker) SKIP_DOCKER=true; shift ;;
    --skip-health-checks) SKIP_HEALTH_CHECKS=true; shift ;;
    --skip-v1-sync) SKIP_V1_SYNC=true; shift ;;
    --skip-voice-deps) SKIP_VOICE_DEPS=true; shift ;;
    --skip-mcp-verify) SKIP_MCP_VERIFY=true; shift ;;
    --no-bootstrap) SKIP_BOOTSTRAP=true; shift ;;
    --profile=*) shift ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --profile (expected isolated|compat)"
        exit 1
      fi
      shift 2
      ;;
    --fast)
      SKIP_HEALTH_CHECKS=true
      SKIP_V1_SYNC=true
      SKIP_MCP_VERIFY=true
      shift
      ;;
    # === VIVENTIUM START ===
    # Compatibility: accept --start as explicit no-op (default behavior is start).
    # === VIVENTIUM END ===
    --start) shift ;;
    --restart) RESTART_SERVICES=true; shift ;;
    --stop) STOP_ONLY=true; shift ;;
    --help)
      # === VIVENTIUM START ===
      # Cleanup: remove stale VM runtime flag from help (feature no longer wired in this launcher).
      # === VIVENTIUM END ===
      echo "Usage: $0 [--start] [--skip-livekit] [--skip-librechat] [--skip-playground] [--modern-playground] [--classic-playground] [--skip-voice-gateway] [--skip-google-mcp] [--skip-ms365-mcp] [--skip-scheduling-mcp] [--skip-glasshive] [--skip-rag-api] [--skip-skyvern] [--skip-code-interpreter] [--skip-firecrawl] [--skip-telegram] [--skip-v1-agent] [--skip-docker] [--skip-health-checks] [--skip-v1-sync] [--skip-voice-deps] [--skip-mcp-verify] [--no-bootstrap] [--private-overlay] [--profile=<isolated|compat>] [--fast] [--restart] [--stop]"
      echo ""
      echo "Starts the full Viventium LibreChat voice call stack:"
      echo "  - LiveKit Server (Docker/native, profile port)"
      echo "  - LibreChat Backend (profile port) + Frontend (profile port)"
      echo "  - Agents Playground (port from VIVENTIUM_PLAYGROUND_URL; profile default)"
      echo "    - Modern playground is the default UI"
      echo "    - Use --classic-playground to force the legacy agents-playground UI"
      echo "  - Voice Gateway Worker (Python)"
      echo "  - Google Workspace MCP (profile port)"
      echo "  - MS365 MCP (port 6274)"
      echo "  - GlassHive Runtime (8766) + MCP (8767) + UI (8780)"
      echo "  - Local RAG API for conversation recall (profile port, local embeddings runtime)"
      echo "  - Skyvern Browser Agent (Docker, profile ports)"
      echo "  - LibreCodeInterpreter API (profile port)"
      echo "  - Firecrawl (Docker, port 3003)"
      echo "  - SearxNG Search (Docker, port 8082)"
      echo "  - Telegram bridge (LibreChat default, LiveKit legacy)"
      echo "  - --restart stops any running services before starting"
      echo "  - --skip-docker leaves Docker services running (reuse on restart/exit)"
      echo "  - Auto-bootstrap runs by default when required nested repos are missing"
      echo "  - Use --no-bootstrap to require repos to already exist"
      echo "  - --private-overlay also loads a private machine-local overlay env file when present"
      echo "  - --profile sets runtime profile (isolated default, compat preserves legacy ports)"
      echo "  - --fast skips sync/verify/health checks for quicker restarts"
      echo "  - --stop stops any running services and exits"
      echo ""
      echo "Credentials are loaded from the local/private env overlay inputs when present"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Tip: remove invisible whitespace and run the command again."
      exit 1
      ;;
  esac
done

PLAYGROUND_APP_DIR="$PLAYGROUND_DIR"
PLAYGROUND_LABEL="Agents Playground"
if [[ "$PLAYGROUND_VARIANT" == "modern" ]]; then
  PLAYGROUND_APP_DIR="$MODERN_PLAYGROUND_DIR"
  PLAYGROUND_LABEL="Viventium Modern Playground"
fi

# Service enable/disable flags (env overrides)
START_GOOGLE_MCP="${START_GOOGLE_MCP:-true}"
START_MS365_MCP="${START_MS365_MCP:-true}"
START_SCHEDULING_MCP="${START_SCHEDULING_MCP:-true}"
START_GLASSHIVE="${START_GLASSHIVE:-true}"
START_RAG_API="${START_RAG_API:-true}"
# === VIVENTIUM START ===
# Feature: Skyvern service toggle (default on).
# === VIVENTIUM END ===
START_SKYVERN="${START_SKYVERN:-true}"
START_TELEGRAM="${START_TELEGRAM:-true}"
START_TELEGRAM_CODEX="${START_TELEGRAM_CODEX:-false}"
TELEGRAM_BACKEND="${VIVENTIUM_TELEGRAM_BACKEND:-librechat}"
START_CODE_INTERPRETER="${START_CODE_INTERPRETER:-true}"
START_SEARXNG="${START_SEARXNG:-true}"
START_FIRECRAWL="${START_FIRECRAWL:-true}"
if [[ -z "${START_V1_AGENT:-}" ]]; then
  if [[ "$START_TELEGRAM" == "true" && "$TELEGRAM_BACKEND" == "livekit" ]]; then
    START_V1_AGENT=true
  else
    START_V1_AGENT=false
  fi
fi

# Apply CLI skip overrides
[[ "$SKIP_GOOGLE_MCP" == "true" ]] && START_GOOGLE_MCP=false
[[ "$SKIP_MS365_MCP" == "true" ]] && START_MS365_MCP=false
[[ "$SKIP_SCHEDULING_MCP" == "true" ]] && START_SCHEDULING_MCP=false
[[ "$SKIP_GLASSHIVE" == "true" ]] && START_GLASSHIVE=false
[[ "$SKIP_RAG_API" == "true" ]] && START_RAG_API=false
# === VIVENTIUM START ===
# Feature: Apply Skyvern skip override.
# === VIVENTIUM END ===
[[ "$SKIP_SKYVERN" == "true" ]] && START_SKYVERN=false
[[ "$SKIP_CODE_INTERPRETER" == "true" ]] && START_CODE_INTERPRETER=false
[[ "$SKIP_FIRECRAWL" == "true" ]] && START_FIRECRAWL=false
[[ "$SKIP_TELEGRAM" == "true" ]] && START_TELEGRAM=false
[[ "$SKIP_V1_AGENT" == "true" ]] && START_V1_AGENT=false

# === VIVENTIUM START ===
# Graceful fallback: some branches do not include the Scheduling Cortex MCP checkout.
# Do not block full-stack startup on this optional service.
if [[ "$START_SCHEDULING_MCP" == "true" && ! -d "$SCHEDULING_MCP_DIR" ]]; then
  echo -e "${YELLOW}[viventium]${NC} Scheduling Cortex MCP directory not found at $SCHEDULING_MCP_DIR; disabling scheduling MCP for this run"
  START_SCHEDULING_MCP=false
fi
if [[ "$START_GLASSHIVE" == "true" && ! -d "$GLASSHIVE_RUNTIME_DIR" ]]; then
  echo -e "${YELLOW}[viventium]${NC} GlassHive runtime directory not found at $GLASSHIVE_RUNTIME_DIR; disabling GlassHive for this run"
  START_GLASSHIVE=false
fi
# === VIVENTIUM END ===

RESTART_DOCKER_SERVICES="$RESTART_SERVICES"
if [[ "$SKIP_DOCKER" == "true" ]]; then
  RESTART_DOCKER_SERVICES=false
  # Docker-only sidecars should never be pulled or restarted when the caller
  # explicitly asks to reuse/avoid Docker. Leaving them enabled can strand the
  # core local stack in a half-restarted state while optional images download.
  START_CODE_INTERPRETER=false
  START_SKYVERN=false
  START_FIRECRAWL=false
  START_SEARXNG=false
fi

mkdir -p "$LOG_DIR"

CLEANUP_ENABLED=false
LIVEKIT_STARTED_BY_SCRIPT=false
LIBRECHAT_STARTED_BY_SCRIPT=false
PLAYGROUND_STARTED_BY_SCRIPT=false
VOICE_GATEWAY_STARTED_BY_SCRIPT=false
GOOGLE_MCP_STARTED_BY_SCRIPT=false
SCHEDULING_MCP_STARTED_BY_SCRIPT=false
MS365_STARTED_BY_SCRIPT=false
RAG_API_STARTED_BY_SCRIPT=false
MS365_CALLBACK_STARTED_BY_SCRIPT=false
TELEGRAM_STARTED_BY_SCRIPT=false
TELEGRAM_LOCAL_BOT_API_STARTED_BY_SCRIPT=false
V1_AGENT_STARTED_BY_SCRIPT=false
CODE_INTERPRETER_STARTED_BY_SCRIPT=false
SEARXNG_STARTED_BY_SCRIPT=false
FIRECRAWL_STARTED_BY_SCRIPT=false
SKYVERN_STARTED_BY_SCRIPT=false
MONGO_STARTED_BY_SCRIPT=false
MONGO_NATIVE_STARTED_BY_SCRIPT=false
MEILI_NATIVE_STARTED_BY_SCRIPT=false

GOOGLE_MCP_PID=""
SCHEDULING_MCP_PID=""
MS365_MCP_CALLBACK_PID=""
TELEGRAM_BOT_PID=""
TELEGRAM_LOCAL_BOT_API_PID=""
V1_AGENT_PID=""

require_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi

  # === VIVENTIUM START ===
  # Feature: Homebrew bootstrap for first-run machines.
  # Purpose: Keep one-click startup working when brew was never installed.
  maybe_install_homebrew() {
    if command -v brew >/dev/null 2>&1; then
      return 0
    fi

    if [[ "${VIVENTIUM_AUTO_INSTALL_BREW:-true}" != "true" ]]; then
      return 1
    fi

    if [[ "$(uname -s)" != "Darwin" ]]; then
      return 1
    fi

    if ! command -v curl >/dev/null 2>&1; then
      return 1
    fi

    log_warn "Homebrew missing; attempting automatic install for one-click setup"
    NONINTERACTIVE=1 CI=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" >/dev/null 2>&1 || return 1

    if [[ -d "/opt/homebrew/bin" ]]; then
      export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:${PATH}"
    fi
    if [[ -d "/usr/local/bin" ]]; then
      export PATH="/usr/local/bin:/usr/local/sbin:${PATH}"
    fi
    command -v brew >/dev/null 2>&1
  }
  # === VIVENTIUM END ===

  # === VIVENTIUM START ===
  # Feature: One-click node/npm self-repair on fresh macOS machines.
  # Purpose: Avoid manual npm install steps when Homebrew is available.
  maybe_install_node20_with_brew() {
    if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
      return 0
    fi
    if ! command -v brew >/dev/null 2>&1; then
      return 1
    fi

    if [[ "${VIVENTIUM_AUTO_INSTALL_NODE:-true}" != "true" ]]; then
      return 1
    fi

    log_warn "node/npm missing; attempting automatic install via Homebrew (node@20)"
    HOMEBREW_NO_AUTO_UPDATE=1 brew install node@20 >/dev/null 2>&1 || return 1

    local node20_prefix
    node20_prefix="$(brew --prefix node@20 2>/dev/null || true)"
    if [[ -n "$node20_prefix" && -d "$node20_prefix/bin" ]]; then
      export PATH="$node20_prefix/bin:${PATH}"
    fi
    return 0
  }

  # Feature: uv bootstrap for optional Python services.
  maybe_install_uv_with_brew() {
    if command -v uv >/dev/null 2>&1; then
      return 0
    fi
    if ! command -v brew >/dev/null 2>&1; then
      return 1
    fi
    if [[ "${VIVENTIUM_AUTO_INSTALL_UV:-true}" != "true" ]]; then
      return 1
    fi
    log_warn "uv missing; attempting automatic install via Homebrew"
    HOMEBREW_NO_AUTO_UPDATE=1 brew install uv >/dev/null 2>&1 || return 1
    command -v uv >/dev/null 2>&1
  }

  # Feature: docker CLI bootstrap on fresh machines.
  maybe_install_docker_cli_with_brew() {
    if command -v docker >/dev/null 2>&1; then
      return 0
    fi
    if ! command -v brew >/dev/null 2>&1; then
      return 1
    fi
    if [[ "${VIVENTIUM_AUTO_INSTALL_DOCKER:-true}" != "true" ]]; then
      return 1
    fi
    log_warn "docker CLI missing; attempting Docker Desktop install via Homebrew cask"
    HOMEBREW_NO_AUTO_UPDATE=1 brew install --cask docker >/dev/null 2>&1 || return 1
    command -v docker >/dev/null 2>&1
  }
  # === VIVENTIUM END ===

  maybe_install_homebrew || true

  if command -v brew >/dev/null 2>&1; then
    local brew_prefix
    brew_prefix="$(brew --prefix 2>/dev/null || true)"
    if [[ -n "$brew_prefix" && -d "$brew_prefix/bin" ]]; then
      export PATH="$brew_prefix/bin:$brew_prefix/sbin:${PATH}"
    fi

    if [[ "$cmd" == "node" || "$cmd" == "npm" ]]; then
      local node20_prefix
      node20_prefix="$(brew --prefix node@20 2>/dev/null || true)"
      if [[ -n "$node20_prefix" && -d "$node20_prefix/bin" ]]; then
        export PATH="$node20_prefix/bin:${PATH}"
      fi
      if [[ "$cmd" == "node" || "$cmd" == "npm" ]]; then
        maybe_install_node20_with_brew || true
      fi
    elif [[ "$cmd" == "uv" ]]; then
      maybe_install_uv_with_brew || true
    elif [[ "$cmd" == "docker" ]]; then
      maybe_install_docker_cli_with_brew || true
    fi
  fi

  command -v "$cmd" >/dev/null 2>&1 || {
    echo -e "${RED}[viventium]${NC} Missing required command: $cmd"
    exit 1
  }
}

log_info() {
  echo -e "${CYAN}[viventium]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[viventium]${NC} $1"
}

log_error() {
  echo -e "${RED}[viventium]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[viventium]${NC} $1"
}

## === VIVENTIUM START ===
# Feature: Fresh-clone preflight and bootstrap fallback
# Purpose: Fail fast on missing required repos/files and optionally auto-bootstrap before startup
REQUIRED_PATH_ISSUES=()

add_required_path_issue() {
  local label="$1"
  local path="$2"
  local issue="${label}|${path}"
  local existing
  for existing in "${REQUIRED_PATH_ISSUES[@]-}"; do
    if [[ "$existing" == "$issue" ]]; then
      return 0
    fi
  done
  REQUIRED_PATH_ISSUES+=("$issue")
}

collect_required_path_issues() {
  REQUIRED_PATH_ISSUES=()

  # Required nested repos for enabled services.
  if [[ "$SKIP_LIBRECHAT" != "true" && ! -d "$LIBRECHAT_DIR" ]]; then
    add_required_path_issue "LibreChat" "$LIBRECHAT_DIR"
  fi
  if [[ "$SKIP_PLAYGROUND" != "true" && ! -d "$PLAYGROUND_APP_DIR" ]]; then
    add_required_path_issue "$PLAYGROUND_LABEL" "$PLAYGROUND_APP_DIR"
  fi
  if [[ "$START_GOOGLE_MCP" == "true" && ! -d "$GOOGLE_MCP_DIR" ]]; then
    add_required_path_issue "Google Workspace MCP" "$GOOGLE_MCP_DIR"
  fi
  if [[ "$START_MS365_MCP" == "true" && ! -d "$ROOT_DIR/MCPs/ms-365-mcp-server" ]]; then
    add_required_path_issue "MS365 MCP" "$ROOT_DIR/MCPs/ms-365-mcp-server"
  fi

  # Required in-repo service directories/scripts.
  if [[ "$SKIP_VOICE_GATEWAY" != "true" && ! -d "$VOICE_GATEWAY_DIR" ]]; then
    add_required_path_issue "Voice Gateway" "$VOICE_GATEWAY_DIR"
  fi
  if [[ "$START_SCHEDULING_MCP" == "true" && ! -d "$SCHEDULING_MCP_DIR" ]]; then
    add_required_path_issue "Scheduling Cortex MCP" "$SCHEDULING_MCP_DIR"
  fi
  if [[ "$START_V1_AGENT" == "true" && ! -d "$V1_AGENT_DIR" ]]; then
    add_required_path_issue "V1 Agent" "$V1_AGENT_DIR"
  fi
}

run_workspace_bootstrap() {
  local public_bootstrap_script="$VIVENTIUM_CORE_DIR/scripts/viventium/bootstrap_components.py"
  if [[ -f "$public_bootstrap_script" ]]; then
    log_warn "Missing required repositories detected. Fetching pinned public components..."
    "$PYTHON_BIN" "$public_bootstrap_script" --repo-root "$VIVENTIUM_CORE_DIR"
    return 0
  fi

  local bootstrap_script="$VIVENTIUM_CORE_DIR/devops/git/scripts/bootstrap-workspace.sh"
  if [[ ! -f "$bootstrap_script" ]]; then
    log_warn "Bootstrap script missing: $bootstrap_script"
    return 1
  fi

  local bootstrap_args=()
  if ! command -v gh >/dev/null 2>&1; then
    bootstrap_args+=(--no-create)
  elif ! gh auth status -h github.com >/dev/null 2>&1; then
    bootstrap_args+=(--no-create)
  fi

  log_warn "Missing required repositories detected. Running workspace bootstrap..."
  if [[ "${#bootstrap_args[@]}" -gt 0 ]]; then
    log_info "Bootstrap args: ${bootstrap_args[*]}"
  fi

  if [[ "${#bootstrap_args[@]}" -gt 0 ]]; then
    bash "$bootstrap_script" "${bootstrap_args[@]}"
  else
    bash "$bootstrap_script"
  fi
}

print_required_path_failures() {
  local issue
  log_error "Required files/repos are missing for the enabled services:"
  for issue in "${REQUIRED_PATH_ISSUES[@]-}"; do
    local label="${issue%%|*}"
    local path="${issue#*|}"
    echo "  - ${label}: ${path}"
  done
  local current_branch
  current_branch="$(git -C "$VIVENTIUM_CORE_DIR" branch --show-current 2>/dev/null || true)"
  if [[ -z "$current_branch" ]]; then
    current_branch="<branch>"
  fi
  echo ""
  echo "Fix options:"
  if [[ -f "$VIVENTIUM_CORE_DIR/scripts/viventium/bootstrap_components.py" ]]; then
    echo "  1. bin/viventium bootstrap-components"
    echo "  2. Re-run this launcher"
  else
    echo "  1. ./git-helper.sh pull -b ${current_branch}"
    echo "  2. bash devops/git/scripts/bootstrap-workspace.sh"
    echo "  3. Re-run this launcher"
  fi
}

ensure_required_paths_ready() {
  local issue_count
  collect_required_path_issues
  issue_count="${#REQUIRED_PATH_ISSUES[@]}"
  if [[ "$issue_count" -eq 0 ]]; then
    return 0
  fi

  if [[ "$SKIP_BOOTSTRAP" == "true" ]]; then
    print_required_path_failures
    return 1
  fi

  if ! run_workspace_bootstrap; then
    log_warn "Auto-bootstrap failed. Verifying required paths..."
  fi

  collect_required_path_issues
  issue_count="${#REQUIRED_PATH_ISSUES[@]}"
  if [[ "$issue_count" -eq 0 ]]; then
    log_success "Required repos/files are present after bootstrap"
    return 0
  fi

  print_required_path_failures
  return 1
}
## === VIVENTIUM END ===

if [[ "$SCHEDULER_SECRET_GENERATED" == "true" ]]; then
  log_warn "VIVENTIUM_SCHEDULER_SECRET not set; generated an ephemeral secret for this session."
fi

kill_pids() {
  local pids="$1"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  echo "$pids" | xargs kill >/dev/null 2>&1 || true
  sleep 1
  local still_running
  still_running=$(echo "$pids" | xargs ps -p 2>/dev/null | awk 'NR>1 {print $1}' | tr '\n' ' ' || true)
  if [[ -n "$still_running" ]]; then
    echo "$still_running" | xargs kill -9 >/dev/null 2>&1 || true
  fi
}

current_process_group_id() {
  ps -o pgid= "$$" 2>/dev/null | tr -d '[:space:]'
}

read_detached_launch_process_group() {
  if [[ -f "$DETACHED_LAUNCH_PGID_FILE" ]]; then
    tr -d '[:space:]' <"$DETACHED_LAUNCH_PGID_FILE"
  fi
}

record_detached_launch_process_group() {
  local pgid=""
  pgid="$(current_process_group_id)"
  if [[ "$pgid" =~ ^[0-9]+$ ]]; then
    printf '%s\n' "$pgid" >"$DETACHED_LAUNCH_PGID_FILE"
  fi
}

clear_detached_launch_process_group() {
  rm -f "$DETACHED_LAUNCH_PGID_FILE"
}

kill_recorded_detached_launch_process_group() {
  local current_pgid=""
  local recorded_pgid=""
  local pids=""
  current_pgid="$(current_process_group_id)"
  recorded_pgid="$(read_detached_launch_process_group)"
  if [[ ! "$recorded_pgid" =~ ^[0-9]+$ ]]; then
    return 0
  fi
  if [[ -n "$current_pgid" && "$recorded_pgid" == "$current_pgid" ]]; then
    return 0
  fi
  pids="$(ps -Ao pid=,pgid= 2>/dev/null | awk -v target="$recorded_pgid" '$2 == target { print $1 }' | xargs 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log_warn "Stopping detached launch process group $recorded_pgid"
    kill_pids "$pids"
  fi
  clear_detached_launch_process_group
}

is_truthy() {
  local value="${1:-}"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# === VIVENTIUM START ===
# Feature: Smarter process scope detection for restarts.
# Purpose: Match by working directory first, then command, so restarts do not
# misclassify normal Node/Python processes that run from the right checkout but
# use relative entrypoints like `api/server/index.js`.
# === VIVENTIUM END ===
read_pid_cwd() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0

  local cwd=""
  if command -v lsof >/dev/null 2>&1; then
    cwd="$(
      lsof -a -d cwd -p "$pid" -Fn 2>/dev/null \
        | sed -n 's/^n//p' \
        | head -n 1
    )"
  fi

  if [[ -z "$cwd" ]] && command -v pwdx >/dev/null 2>&1; then
    cwd="$(pwdx "$pid" 2>/dev/null | sed 's/^[^:]*: //' | head -n 1 || true)"
  fi

  if [[ -n "$cwd" ]]; then
    printf '%s\n' "$cwd"
  fi
}

normalize_scope_path() {
  local path="${1:-}"
  path="${path%/}"
  if [[ -d "$path" ]]; then
    (
      cd "$path" >/dev/null 2>&1 && pwd -P
    ) || printf '%s\n' "$path"
    return 0
  fi
  printf '%s\n' "$path"
}

path_is_trashed_checkout() {
  local path="${1:-}"
  case "$path" in
    */.Trash/*|*/.Trashes/*)
      return 0
      ;;
  esac
  return 1
}

scope_component_signature() {
  local scope="${1%/}"
  if [[ -z "$scope" ]]; then
    return 0
  fi
  local base_name=""
  local parent_name=""
  base_name="$(basename "$scope" 2>/dev/null || true)"
  parent_name="$(basename "$(dirname "$scope")" 2>/dev/null || true)"
  if [[ -n "$parent_name" && -n "$base_name" ]]; then
    printf '%s/%s\n' "$parent_name" "$base_name"
  fi
}

pid_matches_trashed_scope_variant() {
  local pid="$1"
  local scope="$2"
  [[ -n "$scope" ]] || return 1
  scope="$(normalize_scope_path "$scope")"

  local signature=""
  signature="$(scope_component_signature "$scope")"
  [[ -n "$signature" ]] || return 1

  local cmd=""
  local cwd=""
  local candidate=""
  cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
  cwd="$(read_pid_cwd "$pid")"

  for candidate in "$cwd" "$cmd"; do
    [[ -n "$candidate" ]] || continue
    if path_is_trashed_checkout "$candidate" && [[ "$candidate" == *"/$signature"* ]]; then
      return 0
    fi
  done

  return 1
}

pid_matches_scope() {
  local pid="$1"
  local scope="$2"
  if [[ -z "$scope" ]]; then
    return 0
  fi
  scope="$(normalize_scope_path "$scope")"
  local cwd
  cwd="$(read_pid_cwd "$pid")"
  if [[ -n "$cwd" ]]; then
    case "$cwd" in
      "$scope"|"$scope"/*)
        return 0
        ;;
    esac
  fi
  local cmd
  cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
  if [[ -n "$cmd" ]]; then
    case "$cmd" in
      "$scope"|"$scope"/*|*" $scope"|*" $scope"/*)
        return 0
        ;;
    esac
  fi
  return 1
}

kill_pids_scoped() {
  local pids="$1"
  local scope="$2"
  local ancestor_pids=""
  ancestor_pids="$(expand_with_scope_ancestor_pids "$pids" "$scope")"
  if [[ -n "$ancestor_pids" ]]; then
    pids="$pids $ancestor_pids"
  fi
  local expanded_pids
  expanded_pids="$(expand_with_descendant_pids "$pids")"
  if [[ -n "$expanded_pids" ]]; then
    pids="$expanded_pids"
  fi
  local scoped_pids=()
  local pid
  for pid in $pids; do
    if pid_matches_scope "$pid" "$scope"; then
      scoped_pids+=("$pid")
    elif pid_matches_trashed_scope_variant "$pid" "$scope"; then
      log_warn "Stopping stale trashed PID $pid for scope: $scope"
      scoped_pids+=("$pid")
    else
      log_warn "Skipping PID $pid (outside scope: $scope)"
    fi
  done
  if [[ "${#scoped_pids[@]}" -gt 0 ]]; then
    kill_pids "${scoped_pids[*]}"
  fi
  return 0
}

expand_with_scope_ancestor_pids() {
  local seeds="$1"
  local scope="$2"
  if [[ -z "$seeds" || -z "$scope" ]]; then
    return 0
  fi

  local collected=()
  local seed=""
  local current=""
  local parent=""
  for seed in $seeds; do
    current="$seed"
    while [[ -n "$current" ]]; do
      parent="$(ps -o ppid= -p "$current" 2>/dev/null | tr -d '[:space:]' || true)"
      if [[ -z "$parent" || "$parent" == "0" || "$parent" == "1" ]]; then
        break
      fi
      if ! pid_matches_scope "$parent" "$scope"; then
        break
      fi
      collected+=("$parent")
      current="$parent"
    done
  done

  if [[ "${#collected[@]}" -gt 0 ]]; then
    printf '%s\n' "${collected[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

expand_with_descendant_pids() {
  local seeds="$1"
  if [[ -z "$seeds" ]]; then
    return 0
  fi

  local process_table=""
  process_table="$(ps -Ao pid=,ppid= 2>/dev/null || true)"
  if [[ -z "$process_table" ]]; then
    printf '%s\n' "$seeds" | xargs 2>/dev/null || true
    return 0
  fi

  local all="$seeds"
  local frontier="$seeds"
  local next_frontier=""
  local parent=""
  local children=""
  local child=""

  while [[ -n "$frontier" ]]; do
    next_frontier=""
    for parent in $frontier; do
      children="$(printf '%s\n' "$process_table" | awk -v target="$parent" '$2 == target { print $1 }' || true)"
      for child in $children; do
        if [[ " $all " == *" $child "* ]]; then
          continue
        fi
        all="$all $child"
        next_frontier="$next_frontier $child"
      done
    done
    frontier="$next_frontier"
  done

  printf '%s\n' "$all" | tr ' ' '\n' | sed '/^$/d' | sort -u | xargs 2>/dev/null || true
}

pid_is_excluded() {
  local pid="$1"
  shift || true
  local excluded_pid
  for excluded_pid in "$@"; do
    if [[ -n "$excluded_pid" && "$pid" == "$excluded_pid" ]]; then
      return 0
    fi
  done
  return 1
}

filter_excluded_pids() {
  local pids="$1"
  shift || true
  local filtered=()
  local pid
  for pid in $pids; do
    if pid_is_excluded "$pid" "$@"; then
      continue
    fi
    filtered+=("$pid")
  done
  if [[ "${#filtered[@]}" -gt 0 ]]; then
    printf '%s\n' "${filtered[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

kill_by_pattern() {
  local pattern="$1"
  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log_warn "Stopping processes matching: $pattern"
    kill_pids "$pids"
  fi
}

kill_by_pattern_scoped() {
  local pattern="$1"
  local scope="$2"
  local pids
  pids=$(find_scope_pattern_pids "$pattern" "$scope")
  if [[ -n "$pids" ]]; then
    log_warn "Stopping processes matching: $pattern (scope: $scope)"
    kill_pids "$pids"
  fi
}

kill_by_pattern_scoped_excluding() {
  local pattern="$1"
  local scope="$2"
  shift 2 || true
  local pids
  pids=$(find_scope_pattern_pids "$pattern" "$scope")
  if [[ -z "$pids" ]]; then
    return 0
  fi
  pids=$(filter_excluded_pids "$pids" "$@")
  if [[ -n "$pids" ]]; then
    log_warn "Stopping processes matching: $pattern (scope: $scope)"
    kill_pids "$pids"
  fi
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    tr -d '[:space:]' <"$pid_file"
  fi
}

telegram_pid_is_running() {
  local pid
  pid="$(read_pid_file "$TELEGRAM_BOT_PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! ps -p "$pid" >/dev/null 2>&1; then
    rm -f "$TELEGRAM_BOT_PID_FILE"
    return 1
  fi
  return 0
}

telegram_deferred_pid_is_running() {
  local pid
  pid="$(read_pid_file "$TELEGRAM_BOT_DEFERRED_PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! ps -p "$pid" >/dev/null 2>&1; then
    rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE"
    return 1
  fi
  return 0
}

telegram_deferred_start_pending() {
  if telegram_deferred_pid_is_running; then
    return 0
  fi
  [[ -f "$TELEGRAM_BOT_DEFERRED_MARKER_FILE" ]]
}

telegram_codex_pid_is_running() {
  local pid
  pid="$(read_pid_file "$TELEGRAM_CODEX_PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! ps -p "$pid" >/dev/null 2>&1; then
    rm -f "$TELEGRAM_CODEX_PID_FILE"
    return 1
  fi
  return 0
}

telegram_bot_token_looks_valid() {
  local token="${1:-}"
  local telegram_token_regex='^[0-9]{6,}:[A-Za-z0-9_-]{20,}$'

  [[ -n "$token" ]] || return 1
  [[ "$token" =~ $telegram_token_regex ]]
}

find_scope_runtime_pids() {
  local scope="${1:-}"
  if [[ -z "$scope" || ! -d "$scope" ]]; then
    return 0
  fi

  local collected=()
  local row=""
  local pid=""
  local cmd=""
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    row="${row#"${row%%[![:space:]]*}"}"
    pid="${row%% *}"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    cmd="${row#"$pid"}"
    cmd="${cmd#"${cmd%%[![:space:]]*}"}"
    case "$cmd" in
      "$scope"|"$scope"/*|*" $scope"|*" $scope"/*)
        collected+=("$pid")
        ;;
    esac
  done < <(ps -Ao pid=,command= 2>/dev/null || true)

  if [[ "${#collected[@]}" -gt 0 ]]; then
    printf '%s\n' "${collected[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

find_scope_pattern_pids() {
  local pattern="${1:-}"
  local scope="${2:-}"
  if [[ -z "$pattern" || -z "$scope" ]]; then
    return 0
  fi

  local collected=()
  local pid
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    if pid_matches_scope "$pid" "$scope" || pid_matches_trashed_scope_variant "$pid" "$scope"; then
      collected+=("$pid")
    fi
  done < <(pgrep -f "$pattern" 2>/dev/null || true)

  if [[ "${#collected[@]}" -gt 0 ]]; then
    printf '%s\n' "${collected[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

find_port_listener_pids() {
  local port="${1:-}"
  [[ -n "$port" ]] || return 0
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u | xargs 2>/dev/null || true
}

find_scope_orphan_pids() {
  local scope="${1:-}"
  if [[ -z "$scope" || ! -d "$scope" ]]; then
    return 0
  fi

  local collected=()
  local scope_pids
  scope_pids="$(find_scope_runtime_pids "$scope")"
  if [[ -z "$scope_pids" ]]; then
    return 0
  fi

  local pid=""
  local ppid=""
  for pid in $scope_pids; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
    if [[ "$ppid" == "1" ]]; then
      collected+=("$pid")
    fi
  done

  if [[ "${#collected[@]}" -gt 0 ]]; then
    printf '%s\n' "${collected[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

kill_scope_runtime_processes() {
  local scope="$1"
  local label="${2:-$scope}"
  shift 2 || true
  local pids
  pids=$(find_scope_runtime_pids "$scope")
  if [[ -z "$pids" ]]; then
    return 0
  fi
  pids=$(filter_excluded_pids "$pids" "$@")
  if [[ -n "$pids" ]]; then
    log_warn "Stopping residual processes in $label"
    kill_pids "$pids"
  fi
}

kill_orphaned_scope_runtime_processes() {
  local scope="$1"
  local label="${2:-$scope}"
  shift 2 || true
  local pids
  pids="$(find_scope_orphan_pids "$scope")"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  pids="$(filter_excluded_pids "$pids" "$@")"
  if [[ -n "$pids" ]]; then
    log_warn "Stopping orphaned processes in $label"
    kill_pids_scoped "$pids" "$scope"
  fi
}

find_voice_gateway_runtime_pids() {
  local scope="${1:-$VOICE_GATEWAY_DIR}"
  if [[ -z "$scope" ]]; then
    return 0
  fi

  local collected=()
  local pid
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    local cmd
    cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
    case "$cmd" in
      *"worker.py "*|*"job_proc_lazy_main"*|*"multiprocessing.spawn"*|*"multiprocessing.resource_tracker"*)
        collected+=("$pid")
        ;;
    esac
  done < <(find_scope_runtime_pids "$scope")

  if [[ "${#collected[@]}" -gt 0 ]]; then
    printf '%s\n' "${collected[@]}" | sort -u | xargs 2>/dev/null || true
  fi
}

kill_port_listeners() {
  local port="$1"
  local scope="${2:-}"
  local pids=""

  if ! viventium_port_listener_active "$port"; then
    return 0
  fi

  if [[ -z "$scope" ]]; then
    log_warn "Port $port is in use but no safe scope was provided; skipping direct port-based stop"
    return 0
  fi

  pids="$(find_port_listener_pids "$port")"
  if [[ -z "$pids" ]]; then
    log_warn "Port $port is in use but no scoped runtime processes were found under $scope"
    return 0
  fi

  local scoped_port_pids=()
  local pid=""
  for pid in $pids; do
    if pid_matches_scope "$pid" "$scope"; then
      scoped_port_pids+=("$pid")
    elif pid_matches_trashed_scope_variant "$pid" "$scope"; then
      log_warn "Stopping stale trashed PID $pid for scope: $scope"
      scoped_port_pids+=("$pid")
    else
      log_warn "Skipping PID $pid (outside scope: $scope)"
    fi
  done

  if [[ "${#scoped_port_pids[@]}" -eq 0 ]]; then
    log_warn "Port $port is in use but no scoped runtime processes were found under $scope"
    return 0
  fi

  log_warn "Stopping scoped processes that may own port $port"
  kill_pids "${scoped_port_pids[*]}"
}

port_has_listener() {
  local port="$1"
  viventium_port_listener_active "$port"
}

stop_pid_file_scoped() {
  local pid_file="$1"
  local scope="$2"
  if [[ -z "$pid_file" || ! -f "$pid_file" ]]; then
    return 0
  fi
  local pid
  pid=$(cat "$pid_file" 2>/dev/null || true)
  if [[ "$pid" =~ ^[0-9]+$ ]]; then
    if ps -p "$pid" >/dev/null 2>&1; then
      if pid_matches_scope "$pid" "$scope"; then
        log_warn "Stopping process from $pid_file"
        kill_pids "$pid"
      else
        log_warn "Skipping PID $pid (outside scope: $scope)"
      fi
    fi
  fi
  rm -f "$pid_file"
}

stop_detached_librechat_api_watchdog() {
  stop_pid_file_scoped "$LIBRECHAT_API_WATCHDOG_PID_FILE" "$VIVENTIUM_CORE_DIR"
}

cleanup_code_interpreter_exec_containers() {
  local reason="${1:-}"
  local status_filter="${2:-}"
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi

  local api_container
  api_container=$(docker ps -q --filter "name=^/code-interpreter-api$" 2>/dev/null | head -1 || true)
  if [[ -n "$api_container" ]]; then
    local stack_label
    stack_label=$(docker inspect -f '{{ index .Config.Labels "viventium.stack" }}' "$api_container" 2>/dev/null || true)
    if [[ "$stack_label" != "viventium_v0_4" ]]; then
      return 0
    fi
  fi

  local docker_filters=(--filter "label=com.code-interpreter.managed=true")
  if [[ -n "$status_filter" ]]; then
    docker_filters+=(--filter "status=$status_filter")
  fi

  local exec_containers
  exec_containers=$(docker ps -aq "${docker_filters[@]}" 2>/dev/null || true)
  if [[ -n "$exec_containers" ]]; then
    if [[ -n "$reason" ]]; then
      log_warn "Removing code interpreter exec containers (${reason})"
    else
      log_warn "Removing code interpreter exec containers"
    fi
    docker rm -f $exec_containers >/dev/null 2>&1 || true
  fi
}

cleanup_orphaned_code_interpreter_exec_containers() {
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi
  if docker ps -q --filter "name=^/code-interpreter-api$" 2>/dev/null | head -1 | grep -q .; then
    return 0
  fi
  cleanup_code_interpreter_exec_containers "orphan cleanup"
}

remove_named_container_if_present() {
  local container_name="${1:-}"
  if [[ -z "$container_name" ]]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi

  local container_ids
  container_ids=$(docker ps -aq --filter "name=^/${container_name}$" 2>/dev/null || true)
  if [[ -n "$container_ids" ]]; then
    docker rm -f $container_ids >/dev/null 2>&1 || true
  fi
}

remove_compose_project_containers() {
  local project_name="${1:-}"
  if [[ -z "$project_name" ]]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi

  local container_ids
  container_ids=$(docker ps -aq --filter "label=com.docker.compose.project=${project_name}" 2>/dev/null || true)
  if [[ -n "$container_ids" ]]; then
    docker rm -f $container_ids >/dev/null 2>&1 || true
  fi
}

remove_compose_service_containers() {
  local project_name="${1:-}"
  shift || true
  if [[ -z "$project_name" || "$#" -eq 0 ]]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi

  local service_name
  for service_name in "$@"; do
    [[ -z "$service_name" ]] && continue
    local container_ids
    container_ids=$(
      docker ps -aq \
        --filter "label=com.docker.compose.project=${project_name}" \
        --filter "label=com.docker.compose.service=${service_name}" \
        2>/dev/null || true
    )
    if [[ -n "$container_ids" ]]; then
      docker rm -f $container_ids >/dev/null 2>&1 || true
    fi
  done
}

resolve_python_bin() {
  # Prefer modern interpreters so voice-gateway deps (for example numpy>=2.1) resolve.
  local candidates=("$PYTHON_BIN" python3.12 python3.11 python3.10 python3 python)
  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      return 0
    fi
  done
  return 1
}

resolve_voice_python_bin() {
  local candidate=""
  local version=""
  local candidates=(python3.12 python3.11 python3.10 "$PYTHON_BIN" python3 python)
  for candidate in "${candidates[@]}"; do
    if [[ -z "$candidate" ]]; then
      continue
    fi
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    version="$("$candidate" - <<'PY' 2>/dev/null || true
import sys
print(f"{sys.version_info[0]}.{sys.version_info[1]}")
PY
)"
    if [[ "$version" =~ ^3\.(1[0-9]|[2-9][0-9])$ ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

default_stt_thread_count() {
  local detected_cpu_count=""
  detected_cpu_count="$(sysctl -n hw.ncpu 2>/dev/null || printf '4')"
  if ! [[ "$detected_cpu_count" =~ ^[0-9]+$ ]]; then
    detected_cpu_count=4
  fi

  local stt_thread_default="$detected_cpu_count"
  if [[ "$(uname -m)" == "x86_64" ]]; then
    stt_thread_default=$(( detected_cpu_count / 2 ))
    if (( stt_thread_default < 2 )); then
      stt_thread_default=2
    elif (( stt_thread_default > 4 )); then
      stt_thread_default=4
    fi
  else
    if (( stt_thread_default < 2 )); then
      stt_thread_default=2
    elif (( stt_thread_default > 8 )); then
      stt_thread_default=8
    fi
  fi

  printf '%s\n' "$stt_thread_default"
}

default_stt_model() {
  local provider="${1:-${VIVENTIUM_STT_PROVIDER:-whisper_local}}"
  provider="$(printf '%s' "$provider" | tr '[:upper:]' '[:lower:]')"

  if [[ "$provider" == "whisper_local" || "$provider" == "pywhispercpp" ]]; then
    if [[ "$(uname -m)" == "x86_64" ]]; then
      # Intel Macs need a lighter local whisper.cpp default so first-call
      # initialization stays reliable on thinner hardware.
      printf '%s\n' "small"
    else
      printf '%s\n' "large-v3-turbo"
    fi
    return 0
  fi

  printf '%s\n' "large-v3-turbo"
}

default_voice_initialize_process_timeout() {
  local provider="${1:-${VIVENTIUM_STT_PROVIDER:-whisper_local}}"
  provider="$(printf '%s' "$provider" | tr '[:upper:]' '[:lower:]')"
  if [[ "$provider" == "whisper_local" || "$provider" == "pywhispercpp" ]]; then
    if [[ "$(uname -m)" == "x86_64" ]]; then
      printf '%s\n' "120"
    else
      printf '%s\n' "45"
    fi
    return 0
  fi

  printf '%s\n' "20"
}

default_voice_idle_processes() {
  local provider="${1:-${VIVENTIUM_STT_PROVIDER:-whisper_local}}"
  provider="$(printf '%s' "$provider" | tr '[:upper:]' '[:lower:]')"
  if [[ "$provider" == "whisper_local" || "$provider" == "pywhispercpp" ]]; then
    if [[ "$(uname -m)" == "x86_64" ]]; then
      # Intel Macs are more likely to thrash when an extra idle worker preloads local whisper
      # while the first call is also building LibreChat/frontend caches. Favor one stable active
      # worker over speculative prewarm concurrency on these machines.
      printf '%s\n' "0"
      return 0
    fi
    printf '%s\n' "1"
    return 0
  fi

  printf '%s\n' "0"
}

default_voice_worker_load_threshold() {
  local provider="${1:-${VIVENTIUM_STT_PROVIDER:-whisper_local}}"
  provider="$(printf '%s' "$provider" | tr '[:upper:]' '[:lower:]')"
  if [[ "$provider" == "whisper_local" || "$provider" == "pywhispercpp" ]]; then
    # === VIVENTIUM START ===
    # Feature: Intel-safe LiveKit worker availability for local whisper.
    # Purpose: clean Intel Macs can still be under heavy first-run CPU load while LibreChat
    # finishes dependency install/build work. A slightly looser threshold keeps the worker
    # available long enough to accept the first real call instead of flapping unavailable.
    if [[ "$(uname -m)" == "x86_64" ]]; then
      printf '%s\n' "0.999"
    else
      printf '%s\n' "0.995"
    fi
    # === VIVENTIUM END ===
    return 0
  fi

  printf '%s\n' "0.7"
}

host_supports_local_chatterbox_mlx() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi

  local arch_name
  arch_name="$(uname -m)"
  [[ "$arch_name" == "arm64" || "$arch_name" == "aarch64" ]]
}

ensure_librechat_yaml() {
  # === VIVENTIUM START ===
  # Purpose: Ensure LibreChat config exists for zero-setup bootstrap.
  # Local git-tracked source of truth wins and is synced into librechat.yaml
  # before runtime rendering so local model/config edits happen in one place.
  # === VIVENTIUM END ===
  local target="$LIBRECHAT_DIR/librechat.yaml"
  local source_of_truth="$LIBRECHAT_LOCAL_SOURCE_OF_TRUTH"

  # === VIVENTIUM START ===
  # Keep local runtime config aligned with the git-tracked source of truth.
  if [[ -f "$source_of_truth" ]]; then
    if [[ ! -f "$target" ]] || ! cmp -s "$source_of_truth" "$target"; then
      mkdir -p "$(dirname "$target")"
      cp "$source_of_truth" "$target" || {
        log_error "Failed to sync LibreChat config from $source_of_truth"
        return 1
      }
    fi
    return 0
  fi

  # Seed the git-tracked local source of truth from the working config when
  # older clones only have LibreChat/librechat.yaml.
  if [[ -f "$target" ]]; then
    mkdir -p "$(dirname "$source_of_truth")"
    cp "$target" "$source_of_truth" || {
      log_error "Failed to seed local LibreChat source of truth at $source_of_truth"
      return 1
    }
    return 0
  fi
  # === VIVENTIUM END ===

  local fallback=""
  if [[ -f "$LIBRECHAT_DIR/viventium/deployment/configs/librechat.yaml" ]]; then
    fallback="$LIBRECHAT_DIR/viventium/deployment/configs/librechat.yaml"
  elif [[ -f "$LIBRECHAT_DIR/librechat.example.yaml" ]]; then
    fallback="$LIBRECHAT_DIR/librechat.example.yaml"
  fi

  if [[ -z "$fallback" ]]; then
    log_warn "LibreChat config missing and no fallback found"
    return 1
  fi

  log_warn "LibreChat config missing; copying from $(basename "$fallback")"
  cp "$fallback" "$target" || {
    log_error "Failed to copy LibreChat config from $fallback"
    return 1
  }
  # === VIVENTIUM START ===
  mkdir -p "$(dirname "$source_of_truth")"
  cp "$target" "$source_of_truth" || {
    log_error "Failed to seed local LibreChat source of truth from $target"
    return 1
  }
  # === VIVENTIUM END ===
  return 0
}

render_librechat_config() {
  local source="$LIBRECHAT_DIR/librechat.yaml"
  local target="$LOG_ROOT/librechat.generated.yaml"

  if [[ ! -f "$source" ]]; then
    log_warn "LibreChat config not found: $source"
    return 1
  fi

  SOURCE="$source" TARGET="$target" "$PYTHON_BIN" - <<'PY'
import os

source = os.environ["SOURCE"]
target = os.environ["TARGET"]

replacements = {
    "${SCHEDULING_MCP_URL}": os.getenv("SCHEDULING_MCP_URL", ""),
    "${GLASSHIVE_MCP_URL}": os.getenv("GLASSHIVE_MCP_URL", ""),
    "${VIVENTIUM_MAIN_AGENT_ID}": os.getenv("VIVENTIUM_MAIN_AGENT_ID", ""),
    "${MS365_MCP_SERVER_URL}": os.getenv("MS365_MCP_SERVER_URL", ""),
    "${MS365_MCP_AUTH_URL}": os.getenv("MS365_MCP_AUTH_URL", ""),
    "${MS365_MCP_TOKEN_URL}": os.getenv("MS365_MCP_TOKEN_URL", ""),
    "${MS365_MCP_REDIRECT_URI}": os.getenv("MS365_MCP_REDIRECT_URI", ""),
    "${MS365_MCP_CLIENT_ID}": os.getenv("MS365_MCP_CLIENT_ID", ""),
    "${MS365_MCP_CLIENT_SECRET}": os.getenv("MS365_MCP_CLIENT_SECRET", ""),
    "${MS365_MCP_SCOPE}": os.getenv("MS365_MCP_SCOPE", ""),
    "${GOOGLE_WORKSPACE_MCP_URL}": os.getenv("GOOGLE_WORKSPACE_MCP_URL", ""),
    "${GOOGLE_WORKSPACE_MCP_AUTH_URL}": os.getenv("GOOGLE_WORKSPACE_MCP_AUTH_URL", ""),
    "${GOOGLE_WORKSPACE_MCP_TOKEN_URL}": os.getenv("GOOGLE_WORKSPACE_MCP_TOKEN_URL", ""),
    "${GOOGLE_WORKSPACE_MCP_REDIRECT_URI}": os.getenv("GOOGLE_WORKSPACE_MCP_REDIRECT_URI", ""),
    "${GOOGLE_OAUTH_CLIENT_ID}": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
    "${GOOGLE_OAUTH_CLIENT_SECRET}": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
    "${GOOGLE_WORKSPACE_MCP_SCOPE}": os.getenv("GOOGLE_WORKSPACE_MCP_SCOPE", ""),
    # Private-overlay sync: webSearch + service vars (2026-02-07)
    "${SEARXNG_INSTANCE_URL}": os.getenv("SEARXNG_INSTANCE_URL", ""),
    "${SERPER_API_KEY}": os.getenv("SERPER_API_KEY", ""),
    "${FIRECRAWL_API_KEY}": os.getenv("FIRECRAWL_API_KEY", ""),
    "${FIRECRAWL_API_URL}": os.getenv("FIRECRAWL_API_URL", ""),
    "${FIRECRAWL_VERSION}": os.getenv("FIRECRAWL_VERSION", "v2"),
    "${COHERE_API_KEY}": os.getenv("COHERE_API_KEY", ""),
    "${SKYVERN_API_KEY}": os.getenv("SKYVERN_API_KEY", ""),
    "${SKYVERN_BASE_URL}": os.getenv("SKYVERN_BASE_URL", ""),
    "${SKYVERN_APP_URL}": os.getenv("SKYVERN_APP_URL", os.getenv("SKYVERN_BASE_URL", "")),
}

# === VIVENTIUM START ===
# Keep web search values as ${ENV_VAR} references in generated config.
# LibreChat's webSearch auth loader expects env-var placeholders (not literal values).
preserve_env_refs = {
    "${SEARXNG_INSTANCE_URL}",
    "${SERPER_API_KEY}",
    "${FIRECRAWL_API_KEY}",
    "${FIRECRAWL_API_URL}",
    "${FIRECRAWL_VERSION}",
    "${COHERE_API_KEY}",
}
# === VIVENTIUM END ===

with open(source, "r", encoding="utf-8") as handle:
    data = handle.read()

for key, value in replacements.items():
    if key in preserve_env_refs:
        continue
    data = data.replace(key, value)

with open(target, "w", encoding="utf-8") as handle:
    handle.write(data)
PY

  export CONFIG_PATH="$target"
  log_info "LibreChat config generated at $target"
  return 0
}

upsert_env_kv() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file
  local line=""
  local updated=0
  mkdir -p "$(dirname "$file")"
  if [[ ! -f "$file" ]]; then
    : >"$file"
    chmod 600 "$file" >/dev/null 2>&1 || true
  fi
  tmp_file="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      printf '%s=%s\n' "$key" "$value" >>"$tmp_file"
      updated=1
    else
      printf '%s\n' "$line" >>"$tmp_file"
    fi
  done <"$file"
  if [[ "$updated" -eq 0 ]]; then
    printf '%s=%s\n' "$key" "$value" >>"$tmp_file"
  fi
  mv "$tmp_file" "$file"
}

remove_env_kv() {
  local file="$1"
  local key="$2"
  local tmp_file
  local line=""
  mkdir -p "$(dirname "$file")"
  if [[ ! -f "$file" ]]; then
    : >"$file"
    chmod 600 "$file" >/dev/null 2>&1 || true
  fi
  tmp_file="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      continue
    fi
    printf '%s\n' "$line" >>"$tmp_file"
  done <"$file"
  mv "$tmp_file" "$file"
}

should_skip_canonical_librechat_import_key() {
  local key="$1"
  case "$key" in
    HOST|PORT|MONGO_URI|DOMAIN_CLIENT|DOMAIN_SERVER|CLIENT_URL|RAG_API_URL|SEARCH|NO_INDEX|MEILI_*|JWT_SECRET|JWT_REFRESH_SECRET|CREDS_KEY|CREDS_IV|SKYVERN_BASE_URL|SKYVERN_APP_URL|VIVENTIUM_PLAYGROUND_URL|VIVENTIUM_LIBRECHAT_ORIGIN|GOOGLE_WORKSPACE_MCP_URL|GOOGLE_WORKSPACE_MCP_AUTH_URL|GOOGLE_WORKSPACE_MCP_TOKEN_URL|GOOGLE_WORKSPACE_MCP_REDIRECT_URI|MS365_MCP_SERVER_URL|MS365_MCP_AUTH_URL|MS365_MCP_TOKEN_URL|MS365_MCP_REDIRECT_URI|SCHEDULING_MCP_URL|SCHEDULER_LIBRECHAT_URL|SCHEDULER_LIBRECHAT_SECRET|SCHEDULER_TELEGRAM_SECRET)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

import_missing_env_from_file() {
  local source_env_file="$1"
  local target_env_file="${2:-}"
  if [[ ! -f "$source_env_file" ]]; then
    return 1
  fi

  local imported_count=0
  local line=""
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

      if should_skip_canonical_librechat_import_key "$key"; then
        continue
      fi
      if [[ -n "${!key:-}" ]]; then
        continue
      fi
      if [[ -z "$value" ]]; then
        continue
      fi

      export "$key"="$value"
      if [[ -n "$target_env_file" ]]; then
        upsert_env_kv "$target_env_file" "$key" "$value"
      fi
      imported_count=$((imported_count + 1))
    fi
  done < "$source_env_file"

  if [[ "$imported_count" -gt 0 ]]; then
    log_info "Imported $imported_count missing LibreChat env vars from canonical source"
  fi
  return 0
}

read_env_kv() {
  local file="$1"
  local key="$2"
  local line=""
  local value=""
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      value="${line#*=}"
      value="${value%%#*}"
      value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      if [[ -z "$value" ]]; then
        return 1
      fi
      printf "%s" "$value"
      return 0
    fi
  done <"$file"
  return 1
}

# === VIVENTIUM START ===
# Feature: Prefer LibreChat-local Google OAuth credentials for isolated runtime.
# Purpose: Keep isolated local Google Workspace MCP aligned with the same
# LibreChat-local OAuth app registration used in the source-of-truth stack,
# instead of stale repo-root fallback Google client IDs/secrets.
# === VIVENTIUM END ===
load_google_oauth_from_librechat_env() {
  local env_file="$LIBRECHAT_CANONICAL_ENV_FILE"
  if [[ ! -f "$env_file" ]]; then
    return 1
  fi

  local client_id
  local client_secret
  client_id=$(read_env_kv "$env_file" "GOOGLE_OAUTH_CLIENT_ID" || true)
  client_secret=$(read_env_kv "$env_file" "GOOGLE_OAUTH_CLIENT_SECRET" || true)
  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    return 1
  fi

  if [[ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" && "${GOOGLE_OAUTH_CLIENT_ID}" != "$client_id" ]]; then
    log_warn "Google OAuth client ID drift detected; using LibreChat source-of-truth credentials for isolated runtime"
  fi

  export GOOGLE_OAUTH_CLIENT_ID="$client_id"
  export GOOGLE_OAUTH_CLIENT_SECRET="$client_secret"
  return 0
}

hostname_from_urlish() {
  local value="${1:-}"
  value="${value#*://}"
  value="${value%%/*}"
  value="${value%%:*}"
  value="${value#[}"
  value="${value%]}"
  printf '%s\n' "$value"
}

merge_allowed_hosts_csv() {
  local existing_csv="${1:-}"
  shift || true

  local -a merged=()
  local candidate=""
  local item=""
  if [[ -n "$existing_csv" ]]; then
    IFS=',' read -r -a merged <<<"$existing_csv"
  fi

  if (($#)); then
    for candidate in "$@"; do
      candidate="$(hostname_from_urlish "$candidate")"
      [[ -n "$candidate" ]] || continue
      local seen="false"
      if ((${#merged[@]})); then
        for item in "${merged[@]}"; do
          if [[ "$item" == "$candidate" ]]; then
            seen="true"
            break
          fi
        done
      fi
      if [[ "$seen" != "true" ]]; then
        merged+=("$candidate")
      fi
    done
  fi

  local output=""
  if ((${#merged[@]})); then
    for item in "${merged[@]}"; do
      [[ -n "$item" ]] || continue
      if [[ -n "$output" ]]; then
        output+=","
      fi
      output+="$item"
    done
  fi
  printf '%s\n' "$output"
}

ensure_librechat_env() {
  local env_file="$LIBRECHAT_RUNTIME_ENV_FILE"
  local default_mongo_uri="mongodb://127.0.0.1:${VIVENTIUM_LOCAL_MONGO_PORT}/${VIVENTIUM_LOCAL_MONGO_DB}"
  local local_rag_api_url="http://localhost:${VIVENTIUM_RAG_API_PORT}"
  local rag_api_url="${RAG_API_URL:-}"
  local meili_host="${MEILI_HOST:-http://127.0.0.1:${VIVENTIUM_LOCAL_MEILI_PORT}}"
  local meili_master_key="$(resolve_local_meili_master_key)"
  local search_enabled="${SEARCH:-true}"
  local meili_no_analytics="${MEILI_NO_ANALYTICS:-true}"
  local meili_sync_threshold="${MEILI_SYNC_THRESHOLD:-0}"
  local allow_email_login="${ALLOW_EMAIL_LOGIN:-true}"
  local allow_registration="${ALLOW_REGISTRATION:-true}"
  local allow_social_login="${ALLOW_SOCIAL_LOGIN:-false}"
  local allow_social_registration="${ALLOW_SOCIAL_REGISTRATION:-false}"
  local allow_unverified_email_login="${ALLOW_UNVERIFIED_EMAIL_LOGIN:-true}"
  local registration_approval="${VIVENTIUM_REGISTRATION_APPROVAL:-false}"
  local effective_client_url="${VIVENTIUM_PUBLIC_CLIENT_URL:-$LC_FRONTEND_URL}"
  local effective_server_url="${VIVENTIUM_PUBLIC_SERVER_URL:-$LC_API_URL}"
  # === VIVENTIUM START ===
  # Feature: Persist the compiled conversation-recall embeddings contract into LibreChat/.env.
  # Purpose:
  # - rag.yml only injects LibreChat/.env into the RAG container.
  # - Without these keys, query-time embeddings silently fall back to OpenAI defaults even when
  #   the compiled local profile selected Ollama, which breaks recall at runtime.
  # Added: 2026-04-09
  # === VIVENTIUM END ===
  local embeddings_provider="${EMBEDDINGS_PROVIDER:-${VIVENTIUM_RAG_EMBEDDINGS_PROVIDER:-}}"
  local embeddings_model="${EMBEDDINGS_MODEL:-${VIVENTIUM_RAG_EMBEDDINGS_MODEL:-}}"
  local embeddings_profile="${VIVENTIUM_RAG_EMBEDDINGS_PROFILE:-}"
  local ollama_base_url="${OLLAMA_BASE_URL:-}"
  local vite_allowed_hosts_existing="${VITE_ALLOWED_HOSTS:-}"
  local vite_allowed_hosts=""
  vite_allowed_hosts="$(merge_allowed_hosts_csv \
    "$vite_allowed_hosts_existing" \
    "$effective_client_url" \
    "${VIVENTIUM_PUBLIC_CLIENT_URL:-}" \
    "${VIVENTIUM_PUBLIC_SERVER_URL:-}" \
    "${VIVENTIUM_PUBLIC_PLAYGROUND_URL:-}" \
    "${VIVENTIUM_PUBLIC_LIVEKIT_URL:-}")"
  # === VIVENTIUM START ===
  local default_openai_models="$DEFAULT_VIVENTIUM_OPENAI_MODELS"
  local default_assistants_models="$DEFAULT_VIVENTIUM_ASSISTANTS_MODELS"
  if [[ "${VIVENTIUM_OPENAI_AUTH_MODE:-}" == "connected_account" ]]; then
    default_openai_models="${CONNECTED_ACCOUNT_VIVENTIUM_OPENAI_MODELS:-$default_openai_models}"
    default_assistants_models="${CONNECTED_ACCOUNT_VIVENTIUM_ASSISTANTS_MODELS:-$default_assistants_models}"
  fi
  local curated_openai_models="${VIVENTIUM_OPENAI_MODELS:-${OPENAI_MODELS:-$default_openai_models}}"
  local curated_assistants_models="${VIVENTIUM_ASSISTANTS_MODELS:-${ASSISTANTS_MODELS:-$default_assistants_models}}"
  # === VIVENTIUM END ===
  if [[ ! -f "$env_file" ]]; then
    cat >"$env_file" <<EOF
# Auto-generated by viventium-librechat-start.sh for first-run local setup.
HOST=localhost
PORT=${LC_API_PORT}
MONGO_URI=${default_mongo_uri}
DOMAIN_CLIENT=${effective_client_url}
DOMAIN_SERVER=${effective_server_url}
CLIENT_URL=${effective_client_url}
RAG_API_URL=${rag_api_url}
SEARCH=${search_enabled}
MEILI_NO_ANALYTICS=${meili_no_analytics}
MEILI_HOST=${meili_host}
MEILI_MASTER_KEY=${meili_master_key}
MEILI_SYNC_THRESHOLD=${meili_sync_threshold}
NO_INDEX=true
ALLOW_EMAIL_LOGIN=${allow_email_login}
ALLOW_REGISTRATION=${allow_registration}
ALLOW_SOCIAL_LOGIN=${allow_social_login}
ALLOW_SOCIAL_REGISTRATION=${allow_social_registration}
ALLOW_UNVERIFIED_EMAIL_LOGIN=${allow_unverified_email_login}
VIVENTIUM_REGISTRATION_APPROVAL=${registration_approval}
EOF
    chmod 600 "$env_file" >/dev/null 2>&1 || true
    log_warn "LibreChat env missing; created $env_file with local defaults"
  fi

  local mongo_uri="${MONGO_URI:-}"
  if [[ -z "$mongo_uri" ]]; then
    mongo_uri="$(read_env_kv "$env_file" "MONGO_URI" || true)"
  fi
  if [[ -z "$mongo_uri" ]]; then
    mongo_uri="$default_mongo_uri"
  fi

  if [[ -z "$rag_api_url" ]]; then
    rag_api_url="$(read_env_kv "$env_file" "RAG_API_URL" || true)"
  fi
  if [[ -z "$embeddings_provider" ]]; then
    embeddings_provider="$(read_env_kv "$env_file" "EMBEDDINGS_PROVIDER" || true)"
  fi
  if [[ -z "$embeddings_model" ]]; then
    embeddings_model="$(read_env_kv "$env_file" "EMBEDDINGS_MODEL" || true)"
  fi
  if [[ -z "$embeddings_profile" ]]; then
    embeddings_profile="$(read_env_kv "$env_file" "VIVENTIUM_RAG_EMBEDDINGS_PROFILE" || true)"
  fi
  if [[ -z "$ollama_base_url" ]]; then
    ollama_base_url="$(read_env_kv "$env_file" "OLLAMA_BASE_URL" || true)"
  fi
  if [[ -n "$rag_api_url" ]]; then
    case "$rag_api_url" in
      "$local_rag_api_url"|http://127.0.0.1:${VIVENTIUM_RAG_API_PORT}|http://localhost:${VIVENTIUM_RAG_API_PORT}/|http://127.0.0.1:${VIVENTIUM_RAG_API_PORT}/)
        ;;
      *)
        log_warn "Non-local RAG_API_URL detected for isolated local run (${rag_api_url}); disabling conversation recall sync"
        rag_api_url=""
        ;;
    esac
  fi
  if [[ -z "$rag_api_url" || "$rag_api_url" == "$local_rag_api_url" ]]; then
    if port_in_use "$VIVENTIUM_RAG_API_PORT"; then
      rag_api_url="$local_rag_api_url"
    elif [[ "${START_RAG_API:-false}" == "true" && "${SKIP_LIBRECHAT:-false}" != "true" ]]; then
      rag_api_url="$local_rag_api_url"
      log_info "Local RAG API is enabled for this run; keeping conversation recall sync configured while the service warms"
    else
      rag_api_url=""
      log_warn "Local RAG API not detected on port ${VIVENTIUM_RAG_API_PORT}; disabling conversation recall sync for this run"
    fi
  fi

  local jwt_secret="${JWT_SECRET:-}"
  if [[ -z "$jwt_secret" ]]; then
    jwt_secret="$(read_env_kv "$env_file" "JWT_SECRET" || true)"
  fi
  if [[ -z "$jwt_secret" ]] || is_librechat_default_secret "JWT_SECRET" "$jwt_secret"; then
    jwt_secret="$(generate_hex_secret 32)"
  fi

  local jwt_refresh_secret="${JWT_REFRESH_SECRET:-}"
  if [[ -z "$jwt_refresh_secret" ]]; then
    jwt_refresh_secret="$(read_env_kv "$env_file" "JWT_REFRESH_SECRET" || true)"
  fi
  if [[ -z "$jwt_refresh_secret" ]] || is_librechat_default_secret "JWT_REFRESH_SECRET" "$jwt_refresh_secret"; then
    jwt_refresh_secret="$(generate_hex_secret 32)"
  fi

  local creds_key="${CREDS_KEY:-}"
  if [[ -z "$creds_key" ]]; then
    creds_key="$(read_env_kv "$env_file" "CREDS_KEY" || true)"
  fi
  if [[ -z "$creds_key" ]] || is_librechat_default_secret "CREDS_KEY" "$creds_key"; then
    creds_key="$(generate_hex_secret 32)"
  fi

  local creds_iv="${CREDS_IV:-}"
  if [[ -z "$creds_iv" ]]; then
    creds_iv="$(read_env_kv "$env_file" "CREDS_IV" || true)"
  fi
  if [[ -z "$creds_iv" ]] || is_librechat_default_secret "CREDS_IV" "$creds_iv"; then
    creds_iv="$(generate_hex_secret 16)"
  fi

  upsert_env_kv "$env_file" "MONGO_URI" "$mongo_uri"
  upsert_env_kv "$env_file" "PORT" "$LC_API_PORT"
  # === VIVENTIUM START ===
  # Keep the browser-facing origins aligned with the resolved topology for this run.
  upsert_env_kv "$env_file" "DOMAIN_CLIENT" "$effective_client_url"
  upsert_env_kv "$env_file" "DOMAIN_SERVER" "$effective_server_url"
  upsert_env_kv "$env_file" "CLIENT_URL" "$effective_client_url"
  upsert_env_kv "$env_file" "VIVENTIUM_FRONTEND_PROXY_TARGET" "$LC_API_URL"
  upsert_env_kv "$env_file" "VITE_ALLOWED_HOSTS" "$vite_allowed_hosts"
  # === VIVENTIUM END ===
  upsert_env_kv "$env_file" "RAG_API_URL" "$rag_api_url"
  upsert_env_kv "$env_file" "SEARCH" "$search_enabled"
  upsert_env_kv "$env_file" "MEILI_NO_ANALYTICS" "$meili_no_analytics"
  upsert_env_kv "$env_file" "MEILI_HOST" "$meili_host"
  upsert_env_kv "$env_file" "MEILI_MASTER_KEY" "$meili_master_key"
  upsert_env_kv "$env_file" "MEILI_SYNC_THRESHOLD" "$meili_sync_threshold"
  upsert_env_kv "$env_file" "ALLOW_EMAIL_LOGIN" "$allow_email_login"
  upsert_env_kv "$env_file" "ALLOW_REGISTRATION" "$allow_registration"
  upsert_env_kv "$env_file" "ALLOW_SOCIAL_LOGIN" "$allow_social_login"
  upsert_env_kv "$env_file" "ALLOW_SOCIAL_REGISTRATION" "$allow_social_registration"
  upsert_env_kv "$env_file" "ALLOW_UNVERIFIED_EMAIL_LOGIN" "$allow_unverified_email_login"
  upsert_env_kv "$env_file" "VIVENTIUM_REGISTRATION_APPROVAL" "$registration_approval"
  upsert_env_kv "$env_file" "SKYVERN_BASE_URL" "$SKYVERN_BASE_URL"
  upsert_env_kv "$env_file" "SKYVERN_APP_URL" "$SKYVERN_APP_URL"
  upsert_env_kv "$env_file" "JWT_SECRET" "$jwt_secret"
  upsert_env_kv "$env_file" "JWT_REFRESH_SECRET" "$jwt_refresh_secret"
  upsert_env_kv "$env_file" "CREDS_KEY" "$creds_key"
  upsert_env_kv "$env_file" "CREDS_IV" "$creds_iv"
  # === VIVENTIUM START ===
  upsert_env_kv "$env_file" "OPENAI_MODELS" "$curated_openai_models"
  upsert_env_kv "$env_file" "ASSISTANTS_MODELS" "$curated_assistants_models"
  if [[ -n "$embeddings_provider" ]]; then
    upsert_env_kv "$env_file" "EMBEDDINGS_PROVIDER" "$embeddings_provider"
    upsert_env_kv "$env_file" "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER" "$embeddings_provider"
  fi
  if [[ -n "$embeddings_model" ]]; then
    upsert_env_kv "$env_file" "EMBEDDINGS_MODEL" "$embeddings_model"
    upsert_env_kv "$env_file" "VIVENTIUM_RAG_EMBEDDINGS_MODEL" "$embeddings_model"
  fi
  if [[ -n "$embeddings_profile" ]]; then
    upsert_env_kv "$env_file" "VIVENTIUM_RAG_EMBEDDINGS_PROFILE" "$embeddings_profile"
  fi
  if [[ "$embeddings_provider" == "ollama" && -n "$ollama_base_url" ]]; then
    upsert_env_kv "$env_file" "OLLAMA_BASE_URL" "$ollama_base_url"
  else
    remove_env_kv "$env_file" "OLLAMA_BASE_URL"
  fi
  remove_env_kv "$env_file" "CHECK_BALANCE"
  remove_env_kv "$env_file" "START_BALANCE"
  unset CHECK_BALANCE START_BALANCE
  if [[ "${VIVENTIUM_GOOGLE_PROVIDER_ENABLED:-false}" != "true" ]]; then
    remove_env_kv "$env_file" "GOOGLE_API_KEY"
    unset GOOGLE_API_KEY
  fi
  # === VIVENTIUM END ===
  chmod 600 "$env_file" >/dev/null 2>&1 || true

  export MONGO_URI="$mongo_uri"
  export PORT="$LC_API_PORT"
  export DOMAIN_CLIENT="$effective_client_url"
  export DOMAIN_SERVER="$effective_server_url"
  export CLIENT_URL="$effective_client_url"
  export VIVENTIUM_FRONTEND_PROXY_TARGET="$LC_API_URL"
  export VITE_ALLOWED_HOSTS="$vite_allowed_hosts"
  export RAG_API_URL="$rag_api_url"
  export SEARCH="$search_enabled"
  export MEILI_NO_ANALYTICS="$meili_no_analytics"
  export MEILI_HOST="$meili_host"
  export MEILI_MASTER_KEY="$meili_master_key"
  export MEILI_SYNC_THRESHOLD="$meili_sync_threshold"
  export ALLOW_EMAIL_LOGIN="$allow_email_login"
  export ALLOW_REGISTRATION="$allow_registration"
  export ALLOW_SOCIAL_LOGIN="$allow_social_login"
  export ALLOW_SOCIAL_REGISTRATION="$allow_social_registration"
  export ALLOW_UNVERIFIED_EMAIL_LOGIN="$allow_unverified_email_login"
  export VIVENTIUM_REGISTRATION_APPROVAL="$registration_approval"
  export JWT_SECRET="$jwt_secret"
  export JWT_REFRESH_SECRET="$jwt_refresh_secret"
  export CREDS_KEY="$creds_key"
  export CREDS_IV="$creds_iv"
  # === VIVENTIUM START ===
  export OPENAI_MODELS="$curated_openai_models"
  export ASSISTANTS_MODELS="$curated_assistants_models"
  if [[ -n "$embeddings_provider" ]]; then
    export EMBEDDINGS_PROVIDER="$embeddings_provider"
    export VIVENTIUM_RAG_EMBEDDINGS_PROVIDER="$embeddings_provider"
  fi
  if [[ -n "$embeddings_model" ]]; then
    export EMBEDDINGS_MODEL="$embeddings_model"
    export VIVENTIUM_RAG_EMBEDDINGS_MODEL="$embeddings_model"
  fi
  if [[ -n "$embeddings_profile" ]]; then
    export VIVENTIUM_RAG_EMBEDDINGS_PROFILE="$embeddings_profile"
  fi
  if [[ "$embeddings_provider" == "ollama" && -n "$ollama_base_url" ]]; then
    export OLLAMA_BASE_URL="$ollama_base_url"
  else
    unset OLLAMA_BASE_URL
  fi
  # === VIVENTIUM END ===

  local canonical_env_source=""
  canonical_env_source="$(
    first_existing_path \
      "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/librechat/librechat.env" \
      "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/LibreChat/.env" \
      "$LIBRECHAT_CANONICAL_ENV_FILE" || true
  )"
  if [[ -n "$canonical_env_source" && "$canonical_env_source" != "$env_file" ]]; then
    local passthrough_keys=(
      AZURE_AI_FOUNDRY_API_KEY
      AZURE_OPENAI_API_INSTANCE_NAME
      AZURE_OPENAI_API_KEY
      COHERE_API_KEY
      DEPLOYMENT_NAME
      FIRECRAWL_API_KEY
      FIRECRAWL_API_URL
      FIRECRAWL_VERSION
      GLASSHIVE_MCP_URL
      GOOGLE_OAUTH_CLIENT_ID
      GOOGLE_OAUTH_CLIENT_SECRET
      GROQ_API_KEY
      INSTANCE_NAME
      MS365_MCP_CLIENT_ID
      MS365_MCP_CLIENT_SECRET
      MS365_MCP_SCOPE
      OPENROUTER_API_KEY
      PERPLEXITY_API_KEY
      SERPER_API_KEY
      VIVENTIUM_FOUNDRY_ANTHROPIC_REVERSE_PROXY
      VIVENTIUM_ANTHROPIC_MODE
      XAI_API_KEY
    )
    local passthrough_key=""
    local passthrough_value=""
    local imported_count=0
    for passthrough_key in "${passthrough_keys[@]}"; do
      if [[ -n "${!passthrough_key:-}" ]]; then
        continue
      fi
      passthrough_value="$(read_env_kv "$canonical_env_source" "$passthrough_key" || true)"
      if [[ -z "$passthrough_value" ]]; then
        continue
      fi
      export "$passthrough_key"="$passthrough_value"
      upsert_env_kv "$env_file" "$passthrough_key" "$passthrough_value"
      imported_count=$((imported_count + 1))
    done
    if [[ "$imported_count" -gt 0 ]]; then
      log_info "Imported $imported_count canonical LibreChat env vars from $canonical_env_source"
    fi
  fi

  local librechat_code_baseurl="${LIBRECHAT_CODE_BASEURL:-http://localhost:${CODE_INTERPRETER_PORT}}"
  local librechat_code_api_key="${LIBRECHAT_CODE_API_KEY:-${CODE_API_KEY:-viventium-local-code-api-key}}"
  local searxng_instance_url="${SEARXNG_INSTANCE_URL:-http://localhost:${SEARXNG_PORT}}"
  local searxng_base_url="${SEARXNG_BASE_URL:-${searxng_instance_url%/}/}"
  local firecrawl_base_url="${FIRECRAWL_BASE_URL:-http://localhost:${FIRECRAWL_PORT}}"
  local firecrawl_api_key="${FIRECRAWL_API_KEY:-viventium-local-firecrawl-api-key}"
  local firecrawl_api_url="${FIRECRAWL_API_URL:-${firecrawl_base_url%/}}"
  local firecrawl_version="${FIRECRAWL_VERSION:-v2}"
  local glasshive_mcp_url="${GLASSHIVE_MCP_URL:-http://127.0.0.1:8767/mcp}"

  upsert_env_kv "$env_file" "LIBRECHAT_CODE_BASEURL" "$librechat_code_baseurl"
  upsert_env_kv "$env_file" "LIBRECHAT_CODE_API_KEY" "$librechat_code_api_key"
  upsert_env_kv "$env_file" "CODE_API_KEY" "$librechat_code_api_key"
  upsert_env_kv "$env_file" "SEARXNG_INSTANCE_URL" "$searxng_instance_url"
  upsert_env_kv "$env_file" "SEARXNG_BASE_URL" "$searxng_base_url"
  upsert_env_kv "$env_file" "FIRECRAWL_BASE_URL" "$firecrawl_base_url"
  upsert_env_kv "$env_file" "FIRECRAWL_API_KEY" "$firecrawl_api_key"
  upsert_env_kv "$env_file" "FIRECRAWL_API_URL" "$firecrawl_api_url"
  upsert_env_kv "$env_file" "FIRECRAWL_VERSION" "$firecrawl_version"
  upsert_env_kv "$env_file" "GLASSHIVE_MCP_URL" "$glasshive_mcp_url"

  export LIBRECHAT_CODE_BASEURL="$librechat_code_baseurl"
  export LIBRECHAT_CODE_API_KEY="$librechat_code_api_key"
  export CODE_API_KEY="$librechat_code_api_key"
  export SEARXNG_INSTANCE_URL="$searxng_instance_url"
  export SEARXNG_BASE_URL="$searxng_base_url"
  export FIRECRAWL_BASE_URL="$firecrawl_base_url"
  export FIRECRAWL_API_KEY="$firecrawl_api_key"
  export FIRECRAWL_API_URL="$firecrawl_api_url"
  export FIRECRAWL_VERSION="$firecrawl_version"
  export GLASSHIVE_MCP_URL="$glasshive_mcp_url"
  return 0
}

detect_viventium_agents_bundle() {
  local candidate=""
  for candidate in \
    "${LIBRECHAT_AGENTS_BUNDLE_FILE:-}" \
    "$LIBRECHAT_DIR/viventium/source_of_truth/local.viventium-agents.yaml" \
    "$LIBRECHAT_DIR/tmp/viventium-agents.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-260127.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-260127-b.yaml" \
    "$LIBRECHAT_DIR/scripts/viventium-agents-clawd.yaml"
  do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
      printf "%s" "$candidate"
      return 0
    fi
  done
  return 1
}

ensure_viventium_agents_seeded() {
  local bundle_path="${1:-}"
  if [[ -z "$bundle_path" ]]; then
    bundle_path="$(detect_viventium_agents_bundle || true)"
  fi
  if [[ -z "$bundle_path" || ! -f "$bundle_path" ]]; then
    log_warn "Viventium agent bundle not found; skipping built-in agent seeding"
    return 1
  fi

  local seed_script="$LIBRECHAT_DIR/scripts/viventium-seed-agents.js"
  if [[ ! -f "$seed_script" ]]; then
    log_warn "Viventium agent seed script not found; skipping built-in agent seeding"
    return 1
  fi

  local seed_log="$LOG_DIR/librechat_agent_seed.log"
  log_info "Ensuring built-in Viventium agents are present from $(basename "$bundle_path")"
  if (
    cd "$LIBRECHAT_DIR" &&
      ensure_librechat_server_packages_ready &&
      node "$seed_script" --bundle="$bundle_path" --public
  ) >"$seed_log" 2>&1; then
    log_success "Built-in Viventium agents ready"
    return 0
  fi

  log_error "Built-in Viventium agent seeding failed"
  tail -40 "$seed_log" 2>/dev/null || true
  return 1
}

reconcile_viventium_user_defaults() {
  local reconcile_script="$LIBRECHAT_DIR/scripts/viventium-reconcile-user-defaults.js"
  if [[ ! -f "$reconcile_script" ]]; then
    log_warn "Viventium user-default reconciliation script not found; skipping local user default reconciliation"
    return 1
  fi

  local reconcile_log="$LOG_DIR/librechat_user_defaults.log"
  log_info "Reconciling installer-managed Viventium user defaults"
  if (
    cd "$LIBRECHAT_DIR" &&
      ensure_librechat_server_packages_ready &&
      node "$reconcile_script"
  ) >"$reconcile_log" 2>&1; then
    log_success "Viventium user defaults reconciled"
    return 0
  fi

  log_warn "Viventium user default reconciliation had issues"
  tail -40 "$reconcile_log" 2>/dev/null || true
  return 1
}

ensure_code_interpreter_env() {
  local env_file="$CODE_INTERPRETER_DIR/.env"
  local env_example="$CODE_INTERPRETER_DIR/.env.example"
  if [[ -f "$env_file" ]]; then
    return 0
  fi
  local code_api_key="${LIBRECHAT_CODE_API_KEY:-${CODE_API_KEY:-viventium-local-code-api-key}}"
  local code_master_key="${LIBRECHAT_CODE_MASTER_API_KEY:-$code_api_key}"
  local code_api_port="${CODE_INTERPRETER_PORT:-8000}"
  if [[ -f "$env_example" ]]; then
    cp "$env_example" "$env_file" || {
      log_error "Failed to create Code Interpreter env file at $env_file"
      return 1
    }
  else
    log_warn "Code Interpreter env template missing: $env_example"
    cat >"$env_file" <<EOF
# Auto-generated by viventium-librechat-start.sh for local Viventium installs.
API_HOST=0.0.0.0
API_PORT=${code_api_port}
API_DEBUG=false
API_RELOAD=false
API_KEY=${code_api_key}
MASTER_API_KEY=${code_master_key}
API_KEY_HEADER=x-api-key
RATE_LIMIT_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET=code-interpreter-files
MINIO_REGION=us-east-1
DOCKER_IMAGE_REGISTRY=${DOCKER_IMAGE_REGISTRY:-ghcr.io/usnavy13/librecodeinterpreter}
DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG:-latest}
DOCKER_TIMEOUT=60
DOCKER_NETWORK_MODE=none
DOCKER_READ_ONLY=true
CODE_INTERPRETER_USER=${CODE_INTERPRETER_USER:-1000:988}
PYTHON_EXTRA_PIP_PACKAGES=${PYTHON_EXTRA_PIP_PACKAGES:-}
MAX_EXECUTION_TIME=60
MAX_MEMORY_MB=512
MAX_CPUS=1
MAX_PIDS=512
MAX_OPEN_FILES=1024
MAX_FILE_SIZE_MB=10
MAX_TOTAL_FILE_SIZE_MB=50
MAX_FILES_PER_SESSION=50
MAX_OUTPUT_FILES=10
MAX_FILENAME_LENGTH=255
MAX_CONCURRENT_EXECUTIONS=2
MAX_SESSIONS_PER_ENTITY=100
SESSION_TTL_HOURS=24
SESSION_CLEANUP_INTERVAL_MINUTES=60
SESSION_ID_LENGTH=32
ENABLE_ORPHAN_MINIO_CLEANUP=true
CONTAINER_POOL_ENABLED=true
CONTAINER_POOL_WARMUP_ON_STARTUP=false
CONTAINER_POOL_PY=1
CONTAINER_POOL_JS=0
REPL_ENABLED=true
STATE_PERSISTENCE_ENABLED=true
STATE_MAX_SIZE_MB=25
STATE_ARCHIVE_ENABLED=false
STATE_ARCHIVE_TTL_DAYS=7
ENABLE_NETWORK_ISOLATION=true
ENABLE_FILESYSTEM_ISOLATION=true
ENABLE_WAN_ACCESS=false
LOG_LEVEL=INFO
LOG_FORMAT=json
ENABLE_ACCESS_LOGS=true
ENABLE_SECURITY_LOGS=true
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=5
ENABLE_CORS=false
ENABLE_DOCS=false
EOF
  fi

  upsert_env_kv "$env_file" "API_KEY" "$code_api_key"
  upsert_env_kv "$env_file" "MASTER_API_KEY" "$code_master_key"
  upsert_env_kv "$env_file" "DOCKER_IMAGE_REGISTRY" "${DOCKER_IMAGE_REGISTRY:-ghcr.io/usnavy13/librecodeinterpreter}"
  upsert_env_kv "$env_file" "DOCKER_IMAGE_TAG" "${DOCKER_IMAGE_TAG:-latest}"
  upsert_env_kv "$env_file" "API_PORT" "$code_api_port"
  chmod 600 "$env_file" >/dev/null 2>&1 || true

  export LIBRECHAT_CODE_API_KEY="${LIBRECHAT_CODE_API_KEY:-$code_api_key}"
  export CODE_API_KEY="${CODE_API_KEY:-$code_api_key}"
  if [[ -f "$env_example" ]]; then
    log_warn "Code Interpreter env missing; created $env_file from .env.example"
  else
    log_warn "Code Interpreter env missing; created $env_file from built-in local defaults"
  fi
  return 0
}

ensure_skyvern_env() {
  local env_file="$SKYVERN_ENV_FILE"
  local default_llm_key="${VIVENTIUM_SKYVERN_LLM_KEY:-openai/gpt-5.4}"
  local bridge_api_base="http://host.docker.internal:${VIVENTIUM_LC_API_PORT}/api/viventium/skyvern/openai/v1"

  mkdir -p "$(dirname "$env_file")"
  if [[ ! -f "$env_file" ]]; then
    cat >"$env_file" <<EOF
# Auto-generated by viventium-librechat-start.sh for first-run local setup.
ENABLE_OPENAI=false
ENABLE_ANTHROPIC=false
ENABLE_OPENAI_COMPATIBLE=true
OPENAI_COMPATIBLE_MODEL_KEY=OPENAI_COMPATIBLE
OPENAI_COMPATIBLE_MODEL_NAME=${default_llm_key}
OPENAI_COMPATIBLE_SUPPORTS_VISION=true
OPENAI_COMPATIBLE_API_BASE=${bridge_api_base}
OPENAI_COMPATIBLE_API_KEY=${SKYVERN_API_KEY:-}
LLM_KEY=OPENAI_COMPATIBLE
LLM_CONFIG_TEMPERATURE=1
SKYVERN_API_PORT=${SKYVERN_API_PORT}
SKYVERN_UI_PORT=${SKYVERN_UI_PORT}
EOF
    chmod 600 "$env_file" >/dev/null 2>&1 || true
    log_warn "Skyvern env missing; created $env_file with local defaults"
    return 0
  fi

  if grep -q '^# Auto-generated by viventium-librechat-start.sh' "$env_file" &&
    grep -q '^LLM_KEY=OPENAI_GPT4O$' "$env_file"; then
    upsert_env_kv "$env_file" "ENABLE_OPENAI" "false"
    upsert_env_kv "$env_file" "ENABLE_ANTHROPIC" "false"
    upsert_env_kv "$env_file" "ENABLE_OPENAI_COMPATIBLE" "true"
    upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_MODEL_KEY" "OPENAI_COMPATIBLE"
    upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_MODEL_NAME" "$default_llm_key"
    upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_SUPPORTS_VISION" "true"
    upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_API_BASE" "$bridge_api_base"
    upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_API_KEY" "${SKYVERN_API_KEY:-}"
    upsert_env_kv "$env_file" "LLM_KEY" "OPENAI_COMPATIBLE"
    upsert_env_kv "$env_file" "LLM_CONFIG_TEMPERATURE" "1"
    upsert_env_kv "$env_file" "SKYVERN_API_PORT" "${SKYVERN_API_PORT}"
    upsert_env_kv "$env_file" "SKYVERN_UI_PORT" "${SKYVERN_UI_PORT}"
    log_warn "Skyvern env migrated to LibreChat bridge defaults in $env_file"
  fi

  upsert_env_kv "$env_file" "ENABLE_OPENAI" "false"
  upsert_env_kv "$env_file" "ENABLE_ANTHROPIC" "false"
  upsert_env_kv "$env_file" "ENABLE_OPENAI_COMPATIBLE" "true"
  upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_MODEL_KEY" "OPENAI_COMPATIBLE"
  upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_MODEL_NAME" "$default_llm_key"
  upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_SUPPORTS_VISION" "true"
  upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_API_BASE" "$bridge_api_base"
  upsert_env_kv "$env_file" "OPENAI_COMPATIBLE_API_KEY" "${SKYVERN_API_KEY:-}"
  upsert_env_kv "$env_file" "LLM_KEY" "OPENAI_COMPATIBLE"
  upsert_env_kv "$env_file" "SKYVERN_API_PORT" "${SKYVERN_API_PORT}"
  upsert_env_kv "$env_file" "SKYVERN_UI_PORT" "${SKYVERN_UI_PORT}"
  if ! grep -q '^LLM_CONFIG_TEMPERATURE=' "$env_file"; then
    upsert_env_kv "$env_file" "LLM_CONFIG_TEMPERATURE" "1"
  fi

  chmod 600 "$env_file" >/dev/null 2>&1 || true
  return 0
}

## === VIVENTIUM START ===
# Feature: LibreChat dependency auto-heal after pulls.
# Purpose: Prevent blank 3090/3080 startup when lockfile changes or critical modules are missing.
clean_librechat_dependency_tree() {
  (
    cd "$LIBRECHAT_DIR" || exit 1
    local rel=""
    for rel in \
      node_modules \
      client/node_modules \
      packages/api/node_modules \
      packages/client/node_modules \
      packages/data-provider/node_modules \
      packages/data-schemas/node_modules
    do
      local target="$LIBRECHAT_DIR/$rel"
      [[ -e "$target" || -L "$target" ]] || continue
      chmod -R u+w "$target" >/dev/null 2>&1 || true
      "${PYTHON_BIN:-python3}" - "$target" <<'PY' || exit 1
import os
import shutil
import stat
import sys
from pathlib import Path

target = Path(sys.argv[1])
if not target.exists() and not target.is_symlink():
    raise SystemExit(0)

def onerror(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass
    func(path)

if target.is_symlink() or target.is_file():
    target.unlink(missing_ok=True)
else:
    shutil.rmtree(target, onerror=onerror)
PY
    done
  )
}

run_librechat_dependency_install() {
  if [[ -f "package-lock.json" ]]; then
    npm ci
  else
    npm install
  fi
}

LIBRECHAT_DEPS_INSTALLED_THIS_RUN=false
LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=false
LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN=false
LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN=false

default_librechat_health_retries() {
  if [[ "${LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN:-false}" == "true" || "${LIBRECHAT_PACKAGES_REBUILT_THIS_RUN:-false}" == "true" ]]; then
    echo 900
    return 0
  fi
  if [[ "${LIBRECHAT_DEPS_INSTALLED_THIS_RUN:-false}" == "true" ]]; then
    echo 300
    return 0
  fi
  echo 120
}

ensure_librechat_node_dependencies() {
  if [[ ! -d "$LIBRECHAT_DIR" ]]; then
    log_error "LibreChat directory not found: $LIBRECHAT_DIR"
    return 1
  fi

  local deps_reason=""
  local deps_installed=false

  pushd "$LIBRECHAT_DIR" >/dev/null || return 1

  ensure_validated_node20_runtime || {
    popd >/dev/null || true
    return 1
  }

  if [[ ! -d "node_modules" ]]; then
    deps_reason="node_modules missing"
  elif [[ -f "package-lock.json" ]]; then
    if [[ ! -f "node_modules/.package-lock.json" || "package-lock.json" -nt "node_modules/.package-lock.json" ]]; then
      deps_reason="package-lock changed"
    fi
  fi

  if [[ -z "$deps_reason" ]]; then
    if ! node -e "require.resolve('@google/genai')" >/dev/null 2>&1; then
      deps_reason="@google/genai missing"
    fi
  fi

  if [[ -n "$deps_reason" ]]; then
    echo -e "${YELLOW}[viventium]${NC} Installing LibreChat dependencies (${deps_reason})..."
    if ! run_librechat_dependency_install; then
      echo -e "${YELLOW}[viventium]${NC} LibreChat dependency install failed; cleaning dependency trees and retrying once..."
      clean_librechat_dependency_tree || {
        popd >/dev/null || true
        return 1
      }
      run_librechat_dependency_install || {
        popd >/dev/null || true
        return 1
      }
    fi
    deps_installed=true
  fi

  if ! node -e "require.resolve('@google/genai')" >/dev/null 2>&1; then
    echo -e "${RED}[viventium]${NC} LibreChat dependency check failed: @google/genai not found"
    popd >/dev/null || true
    return 1
  fi

  popd >/dev/null || return 1

  if [[ "$deps_installed" == "true" ]]; then
    LIBRECHAT_DEPS_INSTALLED_THIS_RUN=true
  fi

  return 0
}
## === VIVENTIUM END ===

## === VIVENTIUM START ===
# Feature: Build-aware first-run LibreChat package helpers.
# Purpose: fresh installs need API package dist outputs before user-default reconciliation
# and agent seeding can run, while the direct startup path should not rebuild the client
# package twice during the same cold boot.
find_librechat_source_newer_than_dist() {
  local dist_file="${1:-}"
  shift || true

  if [[ -z "$dist_file" || ! -f "$dist_file" ]]; then
    return 0
  fi

  local candidate=""
  local newer_source=""
  for candidate in "$@"; do
    if [[ -f "$candidate" && "$candidate" -nt "$dist_file" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    if [[ -d "$candidate" ]]; then
      newer_source="$(find "$candidate" -type f -newer "$dist_file" 2>/dev/null | head -n 1)"
      if [[ -n "$newer_source" ]]; then
        printf '%s\n' "$newer_source"
        return 0
      fi
    fi
  done

  return 1
}

should_rebuild_librechat_server_packages() {
  if [[ "${VIVENTIUM_FORCE_PACKAGE_REBUILD:-0}" == "1" ]]; then
    return 0
  fi

  local markers=(
    "$LIBRECHAT_DIR/packages/data-provider/dist/index.js"
    "$LIBRECHAT_DIR/packages/data-schemas/dist/index.cjs"
    "$LIBRECHAT_DIR/packages/api/dist/index.js"
  )

  local marker
  for marker in "${markers[@]}"; do
    if [[ ! -f "$marker" ]]; then
      return 0
    fi
  done

  if find_librechat_source_newer_than_dist \
    "${markers[0]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/data-provider/src" \
    "$LIBRECHAT_DIR/packages/data-provider/react-query" \
    "$LIBRECHAT_DIR/packages/data-provider/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-provider/server-rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-provider/package.json" \
    >/dev/null; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "${markers[1]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/data-schemas/src" \
    "$LIBRECHAT_DIR/packages/data-schemas/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-schemas/package.json" \
    >/dev/null; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "${markers[2]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/api/src" \
    "$LIBRECHAT_DIR/packages/api/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/api/package.json" \
    >/dev/null; then
    return 0
  fi

  return 1
}

should_rebuild_librechat_client_package() {
  if [[ "${VIVENTIUM_FORCE_PACKAGE_REBUILD:-0}" == "1" ]]; then
    return 0
  fi

  local marker="$LIBRECHAT_DIR/packages/client/dist/index.js"
  if [[ ! -f "$marker" ]]; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "$marker" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/client/src" \
    "$LIBRECHAT_DIR/packages/client/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/client/package.json" \
    >/dev/null; then
    return 0
  fi

  return 1
}

ensure_librechat_server_packages_ready() {
  if [[ "${LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN:-false}" == "true" ]]; then
    return 0
  fi

  if should_rebuild_librechat_server_packages; then
    echo "[viventium] Building LibreChat server packages for installer-managed runtime tasks..."
    npm run build:data-provider
    npm run build:data-schemas
    npm run build:api
    LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=true
  fi

  LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN=true
  return 0
}
## === VIVENTIUM END ===

should_rebuild_librechat_packages() {
  if should_rebuild_librechat_server_packages; then
    return 0
  fi

  should_rebuild_librechat_client_package
}

resolve_mongo_connection() {
  local uri="${MONGO_URI:-mongodb://127.0.0.1:${VIVENTIUM_LOCAL_MONGO_PORT}/${VIVENTIUM_LOCAL_MONGO_DB}}"
  local host="127.0.0.1"
  local port="$VIVENTIUM_LOCAL_MONGO_PORT"
  local local_target=false

  if [[ "$uri" =~ ^mongodb\+srv:// ]]; then
    MONGO_URI="$uri"
    MONGO_HOST="$host"
    MONGO_PORT="$port"
    MONGO_IS_LOCAL=false
    return 0
  fi

  local authority="${uri#mongodb://}"
  authority="${authority%%/*}"
  authority="${authority##*@}"
  local first_host="${authority%%,*}"
  if [[ -n "$first_host" ]]; then
    if [[ "$first_host" == *:* ]]; then
      host="${first_host%%:*}"
      port="${first_host##*:}"
    else
      host="$first_host"
    fi
  fi

  host="${host#[}"
  host="${host%]}"
  if [[ -z "$host" ]]; then
    host="127.0.0.1"
  fi
  if ! [[ "$port" =~ ^[0-9]+$ ]]; then
    port="$VIVENTIUM_LOCAL_MONGO_PORT"
  fi

  case "$host" in
    localhost|127.0.0.1|0.0.0.0|::1)
      local_target=true
      ;;
  esac

  export MONGO_URI="$uri"
  MONGO_HOST="$host"
  MONGO_PORT="$port"
  MONGO_IS_LOCAL="$local_target"
}

mongo_ping() {
  local uri="$1"
  if [[ "${MONGO_IS_LOCAL:-false}" == "true" ]] && [[ -n "${MONGO_PORT:-}" ]]; then
    if VIVENTIUM_PORT_CHECK_HOST="$MONGO_HOST" viventium_port_listener_active "$MONGO_PORT"; then
      return 0
    fi
  fi

  if command -v mongosh >/dev/null 2>&1; then
    local timeout_seconds="${VIVENTIUM_MONGOSH_PING_TIMEOUT_SECONDS:-3}"
    "$PYTHON_BIN" - "$timeout_seconds" "$uri" <<'PY' >/dev/null 2>&1
import subprocess
import sys

try:
    timeout_seconds = max(0.5, float(sys.argv[1]))
except Exception:
    timeout_seconds = 3.0
uri = sys.argv[2]

try:
    completed = subprocess.run(
        ["mongosh", uri, "--eval", "db.runCommand({ping:1})", "--quiet"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout_seconds,
    )
except subprocess.TimeoutExpired:
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
    return $?
  fi

  if docker_daemon_ready; then
    local container_id
    container_id=$(docker ps -q --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
    if [[ -n "$container_id" ]]; then
      docker exec "$MONGO_CONTAINER_NAME" mongosh --eval "db.runCommand({ping:1})" --quiet >/dev/null 2>&1 && return 0
    fi
  fi

  if port_in_use "$MONGO_PORT"; then
    return 0
  fi
  return 1
}

start_local_mongodb_container() {
  if [[ "$MONGO_IS_LOCAL" == "true" ]] && command -v mongod >/dev/null 2>&1; then
    if [[ -n "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-}" || "${VIVENTIUM_RUNTIME_PROFILE:-}" == "isolated" ]]; then
      log_info "Native mongod available for the local ${VIVENTIUM_RUNTIME_PROFILE:-isolated} runtime; skipping Docker Mongo bootstrap"
      return 1
    fi
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for local MongoDB auto-start)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "local MongoDB auto-start"; then
    return 1
  fi

  local existing
  existing=$(docker ps -aq --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
  if [[ -n "$existing" ]]; then
    local running
    running=$(docker inspect -f '{{.State.Running}}' "$existing" 2>/dev/null || true)
    if [[ "$running" == "true" ]]; then
      log_success "MongoDB container already running on ${MONGO_HOST}:${MONGO_PORT}"
      return 0
    fi
    log_info "Starting existing MongoDB container..."
    if ! docker start "$MONGO_CONTAINER_NAME" >/dev/null; then
      log_error "Failed to start existing MongoDB container: $MONGO_CONTAINER_NAME"
      return 1
    fi
    MONGO_STARTED_BY_SCRIPT=true
    return 0
  fi

  if ! docker image inspect "$MONGO_IMAGE" >/dev/null 2>&1; then
    if command -v mongod >/dev/null 2>&1; then
      log_warn "Mongo image $MONGO_IMAGE is not cached locally; preferring native mongod fallback for this run"
      return 1
    fi
  fi

  local publish_arg="127.0.0.1:${MONGO_PORT}:27017"
  local mongo_mount="${MONGO_VOLUME_NAME}:/data/db"
  if [[ "$MONGO_HOST" == "0.0.0.0" ]]; then
    publish_arg="${MONGO_PORT}:27017"
  fi
  if [[ -n "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-}" ]]; then
    mkdir -p "$VIVENTIUM_LOCAL_MONGO_DATA_PATH"
    mongo_mount="${VIVENTIUM_LOCAL_MONGO_DATA_PATH}:/data/db"
  fi

  log_info "Starting local MongoDB (Docker) on ${MONGO_HOST}:${MONGO_PORT}..."
  if ! docker run -d \
    --name "$MONGO_CONTAINER_NAME" \
    --label "viventium.stack=viventium_v0_4" \
    --label "viventium.service=mongodb" \
    -p "$publish_arg" \
    -v "$mongo_mount" \
    "$MONGO_IMAGE" \
    --bind_ip_all >/dev/null; then
    log_error "Failed to create MongoDB container ($MONGO_CONTAINER_NAME)"
    return 1
  fi
  MONGO_STARTED_BY_SCRIPT=true
  return 0
}

start_local_mongodb_native() {
  if ! command -v mongod >/dev/null 2>&1; then
    log_error "mongod not found (native MongoDB fallback unavailable)"
    return 1
  fi

  if port_in_use "$MONGO_PORT"; then
    log_success "MongoDB already listening on ${MONGO_HOST}:${MONGO_PORT}"
    return 0
  fi

  mkdir -p "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-$VIVENTIUM_STATE_ROOT/mongo-data}"
  rm -f "$MONGO_NATIVE_PID_FILE"

  local bind_args=("--bind_ip" "$MONGO_HOST")
  if [[ "$MONGO_HOST" == "0.0.0.0" ]]; then
    bind_args=("--bind_ip_all")
  fi

  log_warn "Docker Mongo startup failed; trying native mongod fallback on ${MONGO_HOST}:${MONGO_PORT}"
  : > "$MONGO_NATIVE_LOG_FILE"
  nohup mongod \
    --dbpath "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-$VIVENTIUM_STATE_ROOT/mongo-data}" \
    --logpath "$MONGO_NATIVE_LOG_FILE" \
    --logappend \
    --port "$MONGO_PORT" \
    "${bind_args[@]}" >/dev/null 2>&1 < /dev/null &
  local mongo_native_pid=$!
  echo "$mongo_native_pid" > "$MONGO_NATIVE_PID_FILE"

  if ! kill -0 "$mongo_native_pid" >/dev/null 2>&1; then
    log_error "Failed to start native mongod fallback"
    return 1
  fi

  MONGO_NATIVE_STARTED_BY_SCRIPT=true
  return 0
}

ensure_mongodb_ready() {
  resolve_mongo_connection

  if mongo_ping "$MONGO_URI"; then
    log_success "MongoDB ready at ${MONGO_HOST}:${MONGO_PORT}"
    return 0
  fi

  if [[ "$MONGO_IS_LOCAL" != "true" ]]; then
    log_error "MongoDB is not reachable at MONGO_URI=$MONGO_URI"
    log_error "MONGO_URI points to a non-local host, so auto-start is disabled"
    return 1
  fi

  if [[ "$SKIP_DOCKER" == "true" ]]; then
    log_error "MongoDB not reachable and --skip-docker is enabled"
    return 1
  fi

  if ! start_local_mongodb_container; then
    if ! start_local_mongodb_native; then
      return 1
    fi
  fi

  local retries=45
  for _ in $(seq 1 "$retries"); do
    if mongo_ping "$MONGO_URI"; then
      log_success "MongoDB ready at ${MONGO_HOST}:${MONGO_PORT}"
      return 0
    fi
    sleep 1
  done

  log_error "MongoDB did not become ready in time at ${MONGO_HOST}:${MONGO_PORT}"
  if command -v docker >/dev/null 2>&1; then
    docker logs --tail 40 "$MONGO_CONTAINER_NAME" 2>/dev/null || true
  fi
  if [[ -f "$MONGO_NATIVE_LOG_FILE" ]]; then
    tail -40 "$MONGO_NATIVE_LOG_FILE" 2>/dev/null || true
  fi
  return 1
}

resolve_meili_connection() {
  local meili_host="${MEILI_HOST:-http://127.0.0.1:${VIVENTIUM_LOCAL_MEILI_PORT}}"
  local host="127.0.0.1"
  local port="$VIVENTIUM_LOCAL_MEILI_PORT"
  local local_target=false

  if [[ "$meili_host" =~ ^https?:// ]]; then
    local authority="${meili_host#*://}"
    authority="${authority%%/*}"
    local first_host="${authority##*@}"
    if [[ -n "$first_host" ]]; then
      if [[ "$first_host" == *:* ]]; then
        host="${first_host%%:*}"
        port="${first_host##*:}"
      else
        host="$first_host"
      fi
    fi
  fi

  host="${host#[}"
  host="${host%]}"
  if [[ -z "$host" ]]; then
    host="127.0.0.1"
  fi
  if ! [[ "$port" =~ ^[0-9]+$ ]]; then
    port="$VIVENTIUM_LOCAL_MEILI_PORT"
  fi

  case "$host" in
    localhost|127.0.0.1|0.0.0.0|::1)
      local_target=true
      ;;
  esac

  export MEILI_HOST="$meili_host"
  MEILI_BIND_HOST="$host"
  MEILI_PORT="$port"
  MEILI_IS_LOCAL="$local_target"
}

meili_http_ping() {
  local host_url="${1:-${MEILI_HOST:-}}"
  if [[ -z "$host_url" ]]; then
    return 1
  fi
  curl -fsS --max-time 3 "${host_url%/}/health" >/dev/null 2>&1
}

meili_http_auth_ping() {
  local host_url="${1:-${MEILI_HOST:-}}"
  if [[ -z "$host_url" || -z "${MEILI_MASTER_KEY:-}" ]]; then
    return 1
  fi
  curl -fsS --max-time 3 \
    -H "Authorization: Bearer ${MEILI_MASTER_KEY}" \
    -H "X-Meili-API-Key: ${MEILI_MASTER_KEY}" \
    "${host_url%/}/indexes?limit=1" >/dev/null 2>&1
}

restart_viventium_owned_meilisearch_listener() {
  local restarted=false
  local existing=""
  local native_pid=""

  if command -v docker >/dev/null 2>&1; then
    existing=$(docker ps -aq --filter "name=^/${MEILI_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
    if [[ -n "$existing" ]]; then
      log_warn "Configured Meilisearch key does not match the Viventium-owned local listener; recycling the local container"
      docker rm -f "$existing" >/dev/null 2>&1 || true
      restarted=true
    fi
  fi

  if [[ -f "$MEILI_NATIVE_PID_FILE" ]]; then
    native_pid="$(tr -d '[:space:]' <"$MEILI_NATIVE_PID_FILE" 2>/dev/null || true)"
    if [[ "$native_pid" =~ ^[0-9]+$ ]] && kill -0 "$native_pid" >/dev/null 2>&1; then
      log_warn "Configured Meilisearch key does not match the Viventium-owned local listener; recycling the native process"
      kill "$native_pid" >/dev/null 2>&1 || true
      sleep 1
      kill -9 "$native_pid" >/dev/null 2>&1 || true
      restarted=true
    fi
    rm -f "$MEILI_NATIVE_PID_FILE"
  fi

  [[ "$restarted" == "true" ]]
}

start_local_meilisearch_container() {
  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for local Meilisearch auto-start)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "local Meilisearch auto-start"; then
    return 1
  fi

  local existing
  existing=$(docker ps -aq --filter "name=^/${MEILI_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
  if [[ -n "$existing" ]]; then
    local running
    running=$(docker inspect -f '{{.State.Running}}' "$existing" 2>/dev/null || true)
    if [[ "$running" == "true" ]]; then
      log_success "Meilisearch container already running on ${MEILI_BIND_HOST}:${MEILI_PORT}"
      return 0
    fi
    log_info "Starting existing Meilisearch container..."
    if ! docker start "$MEILI_CONTAINER_NAME" >/dev/null; then
      log_error "Failed to start existing Meilisearch container: $MEILI_CONTAINER_NAME"
      return 1
    fi
    return 0
  fi

  if ! docker image inspect "$MEILI_IMAGE" >/dev/null 2>&1; then
    if command -v meilisearch >/dev/null 2>&1; then
      log_warn "Meilisearch image $MEILI_IMAGE is not cached locally; preferring native meilisearch fallback for this run"
      return 1
    fi
  fi

  local publish_arg="127.0.0.1:${MEILI_PORT}:7700"
  local meili_mount="${MEILI_VOLUME_NAME}:/meili_data"
  if [[ "$MEILI_BIND_HOST" == "0.0.0.0" ]]; then
    publish_arg="${MEILI_PORT}:7700"
  fi
  if [[ -n "${VIVENTIUM_LOCAL_MEILI_DATA_PATH:-}" ]]; then
    mkdir -p "$VIVENTIUM_LOCAL_MEILI_DATA_PATH"
    meili_mount="${VIVENTIUM_LOCAL_MEILI_DATA_PATH}:/meili_data"
  fi

  log_info "Starting local Meilisearch (Docker) on ${MEILI_BIND_HOST}:${MEILI_PORT}..."
  if ! docker run -d \
    --name "$MEILI_CONTAINER_NAME" \
    --label "viventium.stack=viventium_v0_4" \
    --label "viventium.service=meilisearch" \
    -p "$publish_arg" \
    -v "$meili_mount" \
    -e "MEILI_MASTER_KEY=${MEILI_MASTER_KEY}" \
    -e "MEILI_NO_ANALYTICS=${MEILI_NO_ANALYTICS}" \
    "$MEILI_IMAGE" >/dev/null; then
    log_error "Failed to create Meilisearch container ($MEILI_CONTAINER_NAME)"
    return 1
  fi
  return 0
}

start_local_meilisearch_native() {
  if ! command -v meilisearch >/dev/null 2>&1; then
    log_error "meilisearch not found (native Meilisearch fallback unavailable)"
    return 1
  fi

  if meili_http_auth_ping "$MEILI_HOST"; then
    log_success "Meilisearch already listening at ${MEILI_BIND_HOST}:${MEILI_PORT}"
    return 0
  fi
  if meili_http_ping "$MEILI_HOST"; then
    log_warn "Meilisearch is already listening at ${MEILI_BIND_HOST}:${MEILI_PORT} but does not accept the configured Viventium key"
    return 1
  fi

  mkdir -p "${VIVENTIUM_LOCAL_MEILI_DATA_PATH:-$VIVENTIUM_STATE_ROOT/meili-data}"
  rm -f "$MEILI_NATIVE_PID_FILE"

  local meili_args=(
    --db-path "${VIVENTIUM_LOCAL_MEILI_DATA_PATH:-$VIVENTIUM_STATE_ROOT/meili-data}"
    --http-addr "${MEILI_BIND_HOST}:${MEILI_PORT}"
    --master-key "${MEILI_MASTER_KEY}"
  )
  if is_truthy "${MEILI_NO_ANALYTICS:-true}"; then
    meili_args+=(--no-analytics)
  fi

  log_warn "Docker Meilisearch startup failed; trying native meilisearch fallback on ${MEILI_BIND_HOST}:${MEILI_PORT}"
  : > "$MEILI_NATIVE_LOG_FILE"
  nohup meilisearch "${meili_args[@]}" >"$MEILI_NATIVE_LOG_FILE" 2>&1 < /dev/null &
  local meili_native_pid=$!
  echo "$meili_native_pid" > "$MEILI_NATIVE_PID_FILE"

  if ! kill -0 "$meili_native_pid" >/dev/null 2>&1; then
    log_error "Failed to start native meilisearch fallback"
    return 1
  fi

  MEILI_NATIVE_STARTED_BY_SCRIPT=true
  return 0
}

ensure_meilisearch_ready() {
  if ! is_truthy "${SEARCH:-false}"; then
    return 0
  fi

  resolve_meili_connection

  if meili_http_auth_ping "$MEILI_HOST"; then
    log_success "Meilisearch ready at ${MEILI_BIND_HOST}:${MEILI_PORT}"
    return 0
  fi

  if meili_http_ping "$MEILI_HOST"; then
    if [[ "$MEILI_IS_LOCAL" == "true" ]] && restart_viventium_owned_meilisearch_listener; then
      log_info "Restarting local Meilisearch with the configured Viventium key..."
    else
      log_error "Meilisearch is reachable at ${MEILI_BIND_HOST}:${MEILI_PORT} but does not accept the configured Viventium key"
      log_error "Stop the conflicting listener or restart the Viventium-owned Meilisearch process with the current runtime secrets"
      return 1
    fi
  fi

  if [[ "$MEILI_IS_LOCAL" != "true" ]]; then
    log_error "Meilisearch is not reachable at MEILI_HOST=$MEILI_HOST"
    log_error "MEILI_HOST points to a non-local host, so auto-start is disabled"
    return 1
  fi

  if [[ "$SKIP_DOCKER" == "true" ]]; then
    log_error "Meilisearch not reachable and --skip-docker is enabled"
    return 1
  fi

  if ! start_local_meilisearch_container; then
    if ! start_local_meilisearch_native; then
      return 1
    fi
  fi

  local retries=45
  for _ in $(seq 1 "$retries"); do
    if meili_http_auth_ping "$MEILI_HOST"; then
      log_success "Meilisearch ready at ${MEILI_BIND_HOST}:${MEILI_PORT}"
      return 0
    fi
    sleep 1
  done

  log_error "Meilisearch did not become ready in time at ${MEILI_BIND_HOST}:${MEILI_PORT}"
  if command -v docker >/dev/null 2>&1; then
    docker logs --tail 40 "$MEILI_CONTAINER_NAME" 2>/dev/null || true
  fi
  if [[ -f "$MEILI_NATIVE_LOG_FILE" ]]; then
    tail -40 "$MEILI_NATIVE_LOG_FILE" 2>/dev/null || true
  fi
  return 1
}

get_playground_port() {
  local port="${VIVENTIUM_PLAYGROUND_PORT}"
  local candidate="${VIVENTIUM_PLAYGROUND_URL##*:}"
  candidate="${candidate%%/*}"
  if [[ "$candidate" =~ ^[0-9]+$ ]]; then
    port="$candidate"
  fi
  echo "$port"
}

get_client_port() {
  echo "$LC_FRONTEND_PORT"
}

get_api_port() {
  echo "$LC_API_PORT"
}

get_livekit_port() {
  local candidate="${LIVEKIT_URL##*:}"
  candidate="${candidate%%/*}"
  if [[ "$candidate" =~ ^[0-9]+$ ]]; then
    echo "$candidate"
  else
    echo "7888"
  fi
}

remote_call_mode_enabled() {
  case "${VIVENTIUM_REMOTE_CALL_MODE:-disabled}" in
    "" | auto | disabled | off | false | 0)
      return 1
      ;;
  esac
  return 0
}

json_state_value() {
  local json_payload="$1"
  local key="$2"
  JSON_STATE_PAYLOAD="$json_payload" "$PYTHON_BIN" - "$key" <<'PY'
import json
import os
import sys

key = sys.argv[1]
try:
    data = json.loads(os.environ.get("JSON_STATE_PAYLOAD", "") or "{}")
except Exception:
    data = {}
print(str(data.get(key, "")).strip())
PY
}

clear_remote_call_runtime_exports() {
  unset VIVENTIUM_PUBLIC_CLIENT_URL
  unset VIVENTIUM_PUBLIC_SERVER_URL
  unset VIVENTIUM_PUBLIC_PLAYGROUND_URL
  unset VIVENTIUM_PUBLIC_LIVEKIT_URL
  unset LIVEKIT_NODE_IP
  unset LIVEKIT_TURN_DOMAIN
  unset LIVEKIT_TURN_TLS_PORT
  unset LIVEKIT_TURN_CERT_FILE
  unset LIVEKIT_TURN_KEY_FILE
}

persist_remote_call_failure_state_if_needed() {
  local provider="${1:-public_https_edge}"
  local message="${2:-}"
  if [[ -z "$message" ]]; then
    message="Remote access setup failed before the helper could persist an error state."
  fi
  REMOTE_CALL_STATE_FILE="$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" \
  REMOTE_CALL_PROVIDER="$provider" \
  REMOTE_CALL_FAILURE_MESSAGE="$message" \
  "$PYTHON_BIN" - <<'PY'
import json
import os
import time
from pathlib import Path

state_file = Path(os.environ.get("REMOTE_CALL_STATE_FILE", "") or "")
if not str(state_file):
    raise SystemExit(0)

provider = str(os.environ.get("REMOTE_CALL_PROVIDER") or "public_https_edge").strip() or "public_https_edge"
message = str(os.environ.get("REMOTE_CALL_FAILURE_MESSAGE") or "").strip()
if not message:
    message = "Remote access setup failed before the helper could persist an error state."

existing = {}
try:
    if state_file.exists():
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            existing = loaded
except Exception:
    existing = {}

if str(existing.get("provider") or "").strip() == provider and str(existing.get("last_error") or "").strip():
    raise SystemExit(0)

state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text(
    json.dumps(
        {
            "provider": provider,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_error": message,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
}

remote_call_mapping_state_supports_refresh() {
  if [[ ! -f "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" ]]; then
    return 1
  fi
  "$PYTHON_BIN" - "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

if not isinstance(data, dict):
    raise SystemExit(1)

if str(data.get("provider") or "").strip() != "public_https_edge":
    raise SystemExit(1)

if str(data.get("last_error") or "").strip():
    raise SystemExit(1)

router = data.get("router") or {}
mappings = router.get("mappings") or []
raise SystemExit(0 if isinstance(mappings, list) and len(mappings) > 0 else 1)
PY
}

prepare_remote_call_access() {
  if ! remote_call_mode_enabled; then
    return 0
  fi
  if [[ ! -f "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" ]]; then
    return 0
  fi

  local prewarm_timeout="${VIVENTIUM_REMOTE_CALL_PREWARM_TIMEOUT_SECONDS:-60}"
  local client_port
  local api_port
  local playground_port=""
  local livekit_port=""
  local livekit_tcp_port=""
  local livekit_udp_port=""
  local voice_enabled="false"
  local remote_provider
  local auto_install_args=()
  local helper_args=()
  local state_json=""
  local public_client_url=""
  local public_api_url=""
  local public_playground_url=""
  local public_livekit_url=""
  local livekit_node_ip=""
  local livekit_turn_domain=""
  local livekit_turn_tls_port=""
  local livekit_turn_cert_file=""
  local livekit_turn_key_file=""
  local trust_note=""

  remote_provider="${VIVENTIUM_REMOTE_CALL_MODE:-cloudflare_quick_tunnel}"
  client_port="$(get_client_port)"
  api_port="$(get_api_port)"
  if is_truthy "${VIVENTIUM_VOICE_ENABLED:-false}"; then
    voice_enabled="true"
  fi
  if [[ "$voice_enabled" == "true" && "$SKIP_PLAYGROUND" != "true" ]]; then
    playground_port="$(get_playground_port)"
  fi
  if [[ "$voice_enabled" == "true" && "$SKIP_LIVEKIT" != "true" ]]; then
    livekit_port="$(get_livekit_port)"
    livekit_tcp_port="${LIVEKIT_TCP_PORT:-}"
    livekit_udp_port="${LIVEKIT_UDP_PORT:-}"
  fi
  if [[ "$remote_provider" == "cloudflare_quick_tunnel" && ( -z "$playground_port" || -z "$livekit_port" ) ]]; then
    log_warn "cloudflare_quick_tunnel only supports the voice playground surfaces; skipping remote access setup because voice is not active for this run"
    return 0
  fi

  if [[ "${VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL:-true}" == "true" ]]; then
    auto_install_args+=(--auto-install)
  fi

  helper_args=(
    start
    --state-file "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE"
    --log-dir "$VIVENTIUM_CALL_TUNNEL_LOG_DIR"
    --provider "$remote_provider"
    --timeout-seconds "$prewarm_timeout"
    --client-port "$client_port"
    --api-port "$api_port"
  )
  if [[ -n "$playground_port" ]]; then
    helper_args+=(--playground-port "$playground_port")
  fi
  if [[ -n "$livekit_port" ]]; then
    helper_args+=(--livekit-port "$livekit_port")
  fi
  if [[ -n "$livekit_tcp_port" ]]; then
    helper_args+=(--livekit-tcp-port "$livekit_tcp_port")
  fi
  if [[ -n "$livekit_udp_port" ]]; then
    helper_args+=(--livekit-udp-port "$livekit_udp_port")
  fi
  if [[ -n "${VIVENTIUM_PUBLIC_CLIENT_URL:-}" ]]; then
    helper_args+=(--public-client-origin "$VIVENTIUM_PUBLIC_CLIENT_URL")
  fi
  if [[ -n "${VIVENTIUM_PUBLIC_SERVER_URL:-}" ]]; then
    helper_args+=(--public-api-origin "$VIVENTIUM_PUBLIC_SERVER_URL")
  fi
  if [[ -n "${VIVENTIUM_PUBLIC_PLAYGROUND_URL:-}" ]]; then
    helper_args+=(--public-playground-origin "$VIVENTIUM_PUBLIC_PLAYGROUND_URL")
  fi
  if [[ -n "${VIVENTIUM_PUBLIC_LIVEKIT_URL:-}" ]]; then
    helper_args+=(--public-livekit-url "$VIVENTIUM_PUBLIC_LIVEKIT_URL")
  fi
  if [[ -n "${LIVEKIT_NODE_IP:-}" ]]; then
    helper_args+=(--livekit-node-ip "$LIVEKIT_NODE_IP")
  fi
  if [[ -n "${VIVENTIUM_REMOTE_CALL_CADDY_DATA_DIR:-}" ]]; then
    helper_args+=(--caddy-data-dir "$VIVENTIUM_REMOTE_CALL_CADDY_DATA_DIR")
  fi

  log_info "Preparing secure remote access topology"
  if ! state_json="$("$PYTHON_BIN" "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" \
    "${helper_args[@]}" \
    "${auto_install_args[@]}" 2>&1)"; then
    local failure_message="${state_json//$'\r'/ }"
    failure_message="${failure_message//$'\n'/ }"
    persist_remote_call_failure_state_if_needed "$remote_provider" "$failure_message"
    clear_remote_call_runtime_exports
    log_warn "Remote access setup failed; local startup will continue without it: $failure_message"
    return 0
  fi

  public_client_url="$(json_state_value "$state_json" "public_client_url")"
  public_api_url="$(json_state_value "$state_json" "public_api_url")"
  public_playground_url="$(json_state_value "$state_json" "public_playground_url")"
  public_livekit_url="$(json_state_value "$state_json" "public_livekit_url")"
  livekit_node_ip="$(json_state_value "$state_json" "livekit_node_ip")"
  livekit_turn_domain="$(json_state_value "$state_json" "livekit_turn_domain")"
  livekit_turn_tls_port="$(json_state_value "$state_json" "livekit_turn_tls_port")"
  livekit_turn_cert_file="$(json_state_value "$state_json" "livekit_turn_cert_file")"
  livekit_turn_key_file="$(json_state_value "$state_json" "livekit_turn_key_file")"
  trust_note="$(json_state_value "$state_json" "trust_note")"

  if [[ -n "$public_client_url" ]]; then
    export VIVENTIUM_PUBLIC_CLIENT_URL="$public_client_url"
  fi
  if [[ -n "$public_api_url" ]]; then
    export VIVENTIUM_PUBLIC_SERVER_URL="$public_api_url"
  fi
  if [[ -n "$public_playground_url" ]]; then
    export VIVENTIUM_PUBLIC_PLAYGROUND_URL="$public_playground_url"
  fi
  if [[ -n "$public_livekit_url" ]]; then
    export VIVENTIUM_PUBLIC_LIVEKIT_URL="$public_livekit_url"
  fi
  if [[ -n "$livekit_node_ip" ]]; then
    export LIVEKIT_NODE_IP="$livekit_node_ip"
  fi
  if [[ -n "$livekit_turn_domain" ]]; then
    export LIVEKIT_TURN_DOMAIN="$livekit_turn_domain"
  fi
  if [[ -n "$livekit_turn_tls_port" ]]; then
    export LIVEKIT_TURN_TLS_PORT="$livekit_turn_tls_port"
  fi
  if [[ -n "$livekit_turn_cert_file" ]]; then
    export LIVEKIT_TURN_CERT_FILE="$livekit_turn_cert_file"
  fi
  if [[ -n "$livekit_turn_key_file" ]]; then
    export LIVEKIT_TURN_KEY_FILE="$livekit_turn_key_file"
  fi
  if [[ -n "$trust_note" ]]; then
    log_warn "$trust_note"
  fi
}

prewarm_remote_call_access() {
  if [[ "${VIVENTIUM_REMOTE_CALL_PREWARM:-true}" != "true" ]]; then
    return 0
  fi
  if ! remote_call_mode_enabled; then
    return 0
  fi
  if [[ ! -f "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" ]]; then
    return 0
  fi

  local state_json=""
  local command_status=0
  local client_url=""
  local api_url=""
  local playground_url=""
  local livekit_url=""
  state_json="$("$PYTHON_BIN" "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" status \
    --state-file "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" 2>&1)" || command_status=$?

  client_url="$(json_state_value "$state_json" "public_client_url")"
  api_url="$(json_state_value "$state_json" "public_api_url")"
  playground_url="$(json_state_value "$state_json" "public_playground_url")"
  livekit_url="$(json_state_value "$state_json" "public_livekit_url")"
  local remote_error=""
  remote_error="$(json_state_value "$state_json" "last_error")"

  if [[ "$command_status" -ne 0 ]]; then
    if [[ -n "$remote_error" ]]; then
      log_warn "Remote access is still inactive for this run: $remote_error"
    else
      log_warn "Remote access verification failed - browser links may need a retry: $state_json"
    fi
    return 0
  fi

  if [[ -n "$client_url" || -n "$api_url" || -n "$playground_url" || -n "$livekit_url" ]]; then
    log_success "Remote access ready${client_url:+ (app: $client_url)}${api_url:+, api: $api_url}${playground_url:+, playground: $playground_url}${livekit_url:+, livekit: $livekit_url}"
  else
    log_success "Remote access ready"
  fi
}

remote_call_public_edge_mode() {
  case "${VIVENTIUM_REMOTE_CALL_MODE:-disabled}" in
    public_https_edge | custom_domain)
      return 0
      ;;
  esac
  return 1
}

remote_call_mapping_refresh_pid_is_running() {
  local pid
  pid="$(read_pid_file "$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! ps -p "$pid" >/dev/null 2>&1; then
    rm -f "$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE"
    return 1
  fi
  return 0
}

start_remote_call_mapping_refresh_worker() {
  if ! remote_call_public_edge_mode; then
    return 0
  fi
  if [[ ! -f "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" || ! -f "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" ]]; then
    return 0
  fi
  if ! remote_call_mapping_state_supports_refresh; then
    return 0
  fi
  if remote_call_mapping_refresh_pid_is_running; then
    return 0
  fi

  local refresh_seconds="${VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_SECONDS:-3600}"
  if ! [[ "$refresh_seconds" =~ ^[0-9]+$ ]] || [[ "$refresh_seconds" -lt 300 ]]; then
    refresh_seconds=3600
  fi

  mkdir -p "$(dirname "$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE")"
  (
    while true; do
      sleep "$refresh_seconds"
      "$PYTHON_BIN" "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" refresh-mappings \
        --state-file "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" \
        >/dev/null 2>>"$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE" || true
    done
  ) &
  echo "$!" >"$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE"
  log_info "Started remote access mapping refresh worker (pid: $!, interval: ${refresh_seconds}s)"
}

stop_remote_call_mapping_refresh_worker() {
  stop_pid_file_scoped "$VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE" "$VIVENTIUM_CORE_DIR"
}

stop_remote_call_tunnels() {
  stop_remote_call_mapping_refresh_worker
  if [[ ! -f "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" ]]; then
    return 0
  fi
  if [[ ! -f "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" ]]; then
    rm -f "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE"
    return 0
  fi
  "$PYTHON_BIN" "$VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT" stop \
    --state-file "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE" \
    >/dev/null 2>&1 || true
}

stop_telegram_local_bot_api() {
  local pid
  pid="$(read_pid_file "$TELEGRAM_LOCAL_BOT_API_PID_FILE")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" >/dev/null 2>&1; then
    log_warn "Stopping Telegram local Bot API server (PID: $pid)"
    kill "$pid" 2>/dev/null || true
    local tries=0
    while [[ "$tries" -lt 10 ]] && ps -p "$pid" >/dev/null 2>&1; do
      sleep 0.5
      tries=$((tries + 1))
    done
    if ps -p "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$TELEGRAM_LOCAL_BOT_API_PID_FILE"
  TELEGRAM_LOCAL_BOT_API_STARTED_BY_SCRIPT=false
  TELEGRAM_LOCAL_BOT_API_PID=""
}

stop_running_services() {
  local reason="${1:-Restart requested - stopping running services}"
  local done_msg="${2:-Restart cleanup complete}"
  local stop_excluded_pids=("$$" "${BASHPID:-}" "$PPID")
  log_warn "$reason"
  stop_detached_librechat_api_watchdog

  # LibreChat backend/frontend
  if [[ "$SKIP_LIBRECHAT" != "true" ]]; then
    kill_port_listeners "$LC_API_PORT" "$LIBRECHAT_DIR"
    kill_port_listeners "$LC_FRONTEND_PORT" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "node.*api/server" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm run backend:dev" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm exec nodemon api/server/index.js" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "cross-env NODE_ENV=development npx nodemon api/server/index.js" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "node .*nodemon api/server/index.js" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "vite.*frontend" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm run dev --host" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "cross-env NODE_ENV=development vite" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm ci" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm install" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "npm run build" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "node .*rollup" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped "rollup -c --silent --bundleConfigAsCjs" "$LIBRECHAT_DIR"
    kill_by_pattern_scoped_excluding "viventium-start.sh" "$LIBRECHAT_DIR" "${stop_excluded_pids[@]}"
    kill_by_pattern_scoped "cross-env NODE_ENV=production vite build" "$LIBRECHAT_DIR"
    # Drain any remaining LibreChat runtime children rooted in the workspace.
    kill_scope_runtime_processes "$LIBRECHAT_DIR" "$LIBRECHAT_DIR"
    kill_orphaned_scope_runtime_processes "$LIBRECHAT_DIR" "$LIBRECHAT_DIR"
  fi

  # Agents Playground
  if [[ "$SKIP_PLAYGROUND" != "true" ]]; then
    local playground_port
    playground_port=$(get_playground_port)
    local playground_dirs=("$PLAYGROUND_DIR" "$MODERN_PLAYGROUND_DIR")
    local playground_dir
    for playground_dir in "${playground_dirs[@]}"; do
      if [[ -n "$playground_dir" && -d "$playground_dir" ]]; then
        kill_port_listeners "$playground_port" "$playground_dir"
        kill_by_pattern_scoped "next dev" "$playground_dir"
        # Drain any remaining Next.js or helper children rooted in the playground cwd.
        kill_scope_runtime_processes "$playground_dir" "$playground_dir"
        kill_orphaned_scope_runtime_processes "$playground_dir" "$playground_dir"
      fi
    done
  fi

  # Voice Gateway worker
  if [[ "$SKIP_VOICE_GATEWAY" != "true" ]]; then
    kill_by_pattern_scoped "voice-gateway/worker.py" "$VOICE_GATEWAY_DIR"
    kill_by_pattern_scoped "worker.py dev" "$VOICE_GATEWAY_DIR"
    kill_by_pattern_scoped "worker.py start" "$VOICE_GATEWAY_DIR"
    kill_by_pattern_scoped "job_proc_lazy_main" "$VOICE_GATEWAY_DIR"
    local voice_gateway_runtime_pids
    voice_gateway_runtime_pids=$(find_voice_gateway_runtime_pids "$VOICE_GATEWAY_DIR")
    if [[ -n "$voice_gateway_runtime_pids" ]]; then
      log_warn "Stopping voice gateway runtime processes in $VOICE_GATEWAY_DIR"
      kill_pids "$voice_gateway_runtime_pids"
    fi
  fi

  # V1 agent
  if [[ -d "$V1_AGENT_DIR" ]]; then
    kill_by_pattern_scoped "frontal_cortex.agent start" "$V1_AGENT_DIR"
  fi

  # Telegram bot
  local telegram_dir
  if [[ -d "$TELEGRAM_DIR_PRIMARY" ]]; then
    telegram_dir="$TELEGRAM_DIR_PRIMARY"
  elif [[ -d "$TELEGRAM_DIR_FALLBACK" ]]; then
    telegram_dir="$TELEGRAM_DIR_FALLBACK"
  else
    telegram_dir=""
  fi
  local telegram_pid
  telegram_pid="$(read_pid_file "$TELEGRAM_BOT_PID_FILE")"
  if [[ -n "$telegram_pid" ]]; then
    kill_pids "$telegram_pid"
    rm -f "$TELEGRAM_BOT_PID_FILE"
  fi
  stop_telegram_local_bot_api
  local telegram_deferred_pid
  telegram_deferred_pid="$(read_pid_file "$TELEGRAM_BOT_DEFERRED_PID_FILE")"
  if [[ -n "$telegram_deferred_pid" ]]; then
    kill_pids "$telegram_deferred_pid"
    rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE"
  fi
  rm -f "$TELEGRAM_BOT_DEFERRED_MARKER_FILE"
  kill_by_pattern_scoped "TelegramVivBot.*bot.py" "$ROOT_DIR"
  if [[ -n "$telegram_dir" ]]; then
    kill_by_pattern_scoped "uv run python bot.py" "$telegram_dir"
  fi

  local telegram_codex_pid
  telegram_codex_pid="$(read_pid_file "$TELEGRAM_CODEX_PID_FILE")"
  if [[ -n "$telegram_codex_pid" ]]; then
    kill_pids "$telegram_codex_pid"
    rm -f "$TELEGRAM_CODEX_PID_FILE"
  fi
  if [[ -d "$TELEGRAM_CODEX_DIR" ]]; then
    kill_by_pattern_scoped "telegram-codex" "$TELEGRAM_CODEX_DIR"
    kill_by_pattern_scoped "uv run telegram-codex" "$TELEGRAM_CODEX_DIR"
  fi

  kill_by_pattern_scoped_excluding "viventium-librechat-start.sh" "$ROOT_DIR" "${stop_excluded_pids[@]}"
  local helper_script_scope="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}/helper-scripts"
  if [[ -d "$helper_script_scope" ]]; then
    kill_by_pattern_scoped_excluding "viventium-librechat-start.sh" "$helper_script_scope" "${stop_excluded_pids[@]}"
  fi
  kill_recorded_detached_launch_process_group

  stop_remote_call_tunnels

  # === VIVENTIUM START ===
  # Feature: Ensure Scheduling Cortex MCP restarts with fresh env on stack restart.
  # === VIVENTIUM END ===
  if [[ -d "$SCHEDULING_MCP_DIR" || -f "$SCHEDULING_MCP_PID_FILE" ]]; then
    stop_pid_file_scoped "$SCHEDULING_MCP_PID_FILE" "$SCHEDULING_MCP_DIR"
    kill_port_listeners "$SCHEDULING_MCP_PORT" "$SCHEDULING_MCP_DIR"
    kill_by_pattern_scoped "uv run python -m scheduling_cortex.server" "$SCHEDULING_MCP_DIR"
  fi

  if [[ -d "$GLASSHIVE_RUNTIME_DIR" || -f "$GLASSHIVE_RUNTIME_PID_FILE" || -f "$GLASSHIVE_MCP_PID_FILE" ]]; then
    stop_pid_file_scoped "$GLASSHIVE_RUNTIME_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
    stop_pid_file_scoped "$GLASSHIVE_MCP_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
    stop_pid_file_scoped "$GLASSHIVE_UI_PID_FILE" "$GLASSHIVE_UI_DIR"
    kill_port_listeners "$GLASSHIVE_RUNTIME_PORT" "$GLASSHIVE_RUNTIME_DIR"
    kill_port_listeners "$GLASSHIVE_MCP_PORT" "$GLASSHIVE_RUNTIME_DIR"
    kill_port_listeners "$GLASSHIVE_UI_PORT" "$GLASSHIVE_UI_DIR"
    kill_by_pattern_scoped "uv run uvicorn workers_projects_runtime.api:app" "$GLASSHIVE_RUNTIME_DIR"
    kill_by_pattern_scoped "uv run python -m workers_projects_runtime.mcp_server" "$GLASSHIVE_RUNTIME_DIR"
    kill_by_pattern_scoped "uv run uvicorn glass_drive_ui.server:app" "$GLASSHIVE_UI_DIR"
  fi

  # === VIVENTIUM START ===
  # Feature: Stop Skyvern stack on restart/stop when enabled.
  # === VIVENTIUM END ===
  if [[ "$START_SKYVERN" == "true" && "$SKIP_DOCKER" != "true" ]]; then
    local skyvern_script="$ROOT_DIR/viventium-skyvern-start.sh"
    if [[ -x "$skyvern_script" ]]; then
      "$skyvern_script" stop >/dev/null 2>&1 || true
    fi
    if docker_daemon_ready; then
      local skyvern_project_containers
      skyvern_project_containers=$(docker ps -aq --filter "label=com.docker.compose.project=skyvern" 2>/dev/null || true)
      if [[ -n "$skyvern_project_containers" ]]; then
        docker rm -f $skyvern_project_containers >/dev/null 2>&1 || true
      fi
    fi
  fi

  # Google Workspace MCP
  if [[ -d "$GOOGLE_MCP_DIR" || -f "$GOOGLE_MCP_PID_FILE" ]]; then
    stop_pid_file_scoped "$GOOGLE_MCP_PID_FILE" "$GOOGLE_MCP_DIR"
    kill_port_listeners "$GOOGLE_MCP_PORT" "$GOOGLE_MCP_DIR"
    kill_by_pattern_scoped "uv run python -u main.py --transport streamable-http" "$GOOGLE_MCP_DIR"
    kill_by_pattern_scoped "start_server.sh" "$GOOGLE_MCP_DIR"
  fi

  # MS365 OAuth callback + MCP container
  if [[ -d "$V1_AGENT_DIR" || -n "${MS365_MCP_CALLBACK_PORT:-}" ]]; then
    kill_port_listeners "$MS365_MCP_CALLBACK_PORT" "$VIVENTIUM_CORE_DIR"
  fi
  if command -v docker >/dev/null 2>&1; then
    if docker_daemon_ready; then
      if [[ -d "$CODE_INTERPRETER_DIR" ]]; then
          local ci_compose_file="$CODE_INTERPRETER_DIR/docker-compose.ghcr.yml"
          if [[ ! -f "$ci_compose_file" ]]; then
            ci_compose_file="$CODE_INTERPRETER_DIR/docker-compose.yml"
          fi
          if [[ -f "$ci_compose_file" ]]; then
            (
              cd "$CODE_INTERPRETER_DIR"
              docker compose -f "$ci_compose_file" down >/dev/null 2>&1 || true
            )
          fi

          local ci_project_containers
          ci_project_containers=$(docker ps -aq --filter "label=com.docker.compose.project=librecodeinterpreter" 2>/dev/null || true)
          if [[ -n "$ci_project_containers" ]]; then
            docker rm -f $ci_project_containers >/dev/null 2>&1 || true
          fi

          local ci_containers
          ci_containers=$(
            docker ps -aq \
              --filter "label=viventium.stack=viventium_v0_4" \
              --filter "label=viventium.component=code-interpreter" \
              2>/dev/null || true
          )
          if [[ -n "$ci_containers" ]]; then
            docker rm -f $ci_containers >/dev/null 2>&1 || true
          fi
          cleanup_code_interpreter_exec_containers "restart"
      fi

      local ms365_compose="$ROOT_DIR/docker/ms365-mcp/docker-compose.yml"
      if [[ -f "$ms365_compose" ]]; then
        docker compose -f "$ms365_compose" down >/dev/null 2>&1 || true
      fi
      remove_named_container_if_present "viventium_ms365_mcp"
      remove_compose_project_containers "ms365-mcp"

      local rag_compose="$LIBRECHAT_DIR/rag.yml"
      if [[ -f "$rag_compose" ]]; then
        (
          cd "$LIBRECHAT_DIR"
          RAG_PORT="$VIVENTIUM_RAG_API_PORT" docker compose -f "$rag_compose" down >/dev/null 2>&1 || true
        )
      fi
      remove_compose_service_containers "librechat" "rag_api" "vectordb"

      # VIVENTIUM START: Use v0.4 SearxNG compose.
      local searxng_compose="$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/searxng/docker-compose.yml"
      # VIVENTIUM END
      if [[ -f "$searxng_compose" ]]; then
        docker compose -f "$searxng_compose" down >/dev/null 2>&1 || true
      fi
      remove_compose_project_containers "searxng"

      # VIVENTIUM START: Use v0.4 Firecrawl compose.
      local firecrawl_compose="$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/firecrawl/docker-compose.yml"
      # VIVENTIUM END
      if [[ -f "$firecrawl_compose" ]]; then
        docker compose -f "$firecrawl_compose" down >/dev/null 2>&1 || true
      fi
      remove_compose_project_containers "firecrawl"

      local mongo_container
      mongo_container=$(docker ps -aq --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
      if [[ -n "$mongo_container" ]]; then
        local mongo_service_label
        mongo_service_label=$(docker inspect -f '{{ index .Config.Labels "viventium.service" }}' "$mongo_container" 2>/dev/null || true)
        if [[ "$mongo_service_label" == "mongodb" ]]; then
          docker rm -f "$mongo_container" >/dev/null 2>&1 || true
        fi
      fi

      local meili_container
      meili_container=$(docker ps -aq --filter "name=^/${MEILI_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
      if [[ -n "$meili_container" ]]; then
        local meili_service_label
        meili_service_label=$(docker inspect -f '{{ index .Config.Labels "viventium.service" }}' "$meili_container" 2>/dev/null || true)
        if [[ "$meili_service_label" == "meilisearch" ]]; then
          docker rm -f "$meili_container" >/dev/null 2>&1 || true
        fi
      fi

      local livekit_containers
      livekit_containers=$(
        docker ps -q \
          --filter "label=viventium.stack=viventium_v0_4" \
          --filter "label=viventium.service=livekit" \
          2>/dev/null || true
      )
      if [[ -z "$livekit_containers" ]]; then
        livekit_containers=$(docker ps -q --filter "name=^/viventium-livekit-" 2>/dev/null || true)
      fi
      if [[ -n "$livekit_containers" ]]; then
        docker rm -f $livekit_containers >/dev/null 2>&1 || true
      fi
    else
      log_warn "Docker is not running; skipping container cleanup"
    fi
  fi

  log_success "$done_msg"
}

cleanup_stale_containers() {
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker_daemon_ready; then
    return 0
  fi
  local stale
  stale=$(docker ps -aq --filter "label=viventium.stack=viventium_v0_4" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$stale" ]]; then
    log_warn "Removing stale Viventium containers"
    docker rm $stale >/dev/null 2>&1 || true
  fi
  local livekit_stale
  livekit_stale=$(docker ps -aq --filter "name=^/viventium-livekit-" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$livekit_stale" ]]; then
    docker rm $livekit_stale >/dev/null 2>&1 || true
  fi
  local ms365_stale
  ms365_stale=$(docker ps -aq --filter "name=^/viventium_ms365_mcp$" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$ms365_stale" ]]; then
    docker rm $ms365_stale >/dev/null 2>&1 || true
  fi
  local rag_stale
  rag_stale=$(docker ps -aq --filter "label=com.docker.compose.project=librechat" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$rag_stale" ]]; then
    docker rm $rag_stale >/dev/null 2>&1 || true
  fi
  local mongo_stale
  mongo_stale=$(docker ps -aq --filter "name=^/${MONGO_CONTAINER_NAME}$" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$mongo_stale" ]]; then
    docker rm "$mongo_stale" >/dev/null 2>&1 || true
  fi
  local meili_stale
  meili_stale=$(docker ps -aq --filter "name=^/${MEILI_CONTAINER_NAME}$" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$meili_stale" ]]; then
    docker rm "$meili_stale" >/dev/null 2>&1 || true
  fi
  local ci_project_stale
  ci_project_stale=$(docker ps -aq --filter "label=com.docker.compose.project=librecodeinterpreter" --filter "status=exited" 2>/dev/null || true)
  if [[ -n "$ci_project_stale" ]]; then
    docker rm $ci_project_stale >/dev/null 2>&1 || true
  fi
  cleanup_code_interpreter_exec_containers "stale cleanup" "exited"
}

if [[ "$STOP_ONLY" == "true" ]]; then
  CLEANUP_ENABLED=false
  stop_running_services "Stop requested - stopping running services" "Stop cleanup complete"
  cleanup_stale_containers
  echo -e "${GREEN}[viventium]${NC} Launcher-managed services stopped; native shutdown may still continue."
  exit 0
fi

if ! resolve_python_bin; then
  log_error "Python interpreter not found (python3/python)"
  exit 1
fi

if [[ "$START_TELEGRAM" == "true" && "$TELEGRAM_BACKEND" == "livekit" && "$START_V1_AGENT" != "true" ]]; then
  log_warn "Telegram enabled with LiveKit backend but V1 agent disabled; Telegram messages will not be handled"
fi

port_in_use() {
  local port="$1"
  port_has_listener "$port"
}

find_free_port() {
  local start_port="$1"
  shift || true
  local reserved=("$@")
  local port="$start_port"
  while true; do
    local skip=false
    local reserved_port
    if [[ "${#reserved[@]}" -gt 0 ]]; then
      for reserved_port in "${reserved[@]}"; do
        if [[ -n "$reserved_port" && "$port" -eq "$reserved_port" ]]; then
          skip=true
          break
        fi
      done
    fi
    if [[ "$skip" == "false" ]] && ! port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
  done
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local retries="${3:-30}"
  if ! [[ "$retries" =~ ^[0-9]+$ ]] || [[ "$retries" -lt 1 ]]; then
    retries=30
  fi
  for _ in $(seq 1 "$retries"); do
    if curl -s --max-time 3 "$url" >/dev/null 2>&1; then
      log_success "$label ready"
      return 0
    fi
    sleep 1
  done
  log_warn "$label did not respond in time"
  return 1
}

librechat_api_healthy() {
  curl -fsS --max-time 3 "${LC_API_URL}/health" >/dev/null 2>&1
}

telegram_local_bot_api_enabled() {
  is_truthy "${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED:-false}"
}

telegram_local_bot_api_host() {
  printf '%s\n' "${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST:-127.0.0.1}"
}

telegram_local_bot_api_port() {
  printf '%s\n' "${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT:-8084}"
}

resolve_telegram_local_bot_api_binary() {
  local configured="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH:-}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  if command -v telegram-bot-api >/dev/null 2>&1; then
    command -v telegram-bot-api
    return 0
  fi
  return 1
}

telegram_local_bot_api_pid_is_running() {
  local pid
  pid="$(read_pid_file "$TELEGRAM_LOCAL_BOT_API_PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ps -p "$pid" >/dev/null 2>&1; then
    TELEGRAM_LOCAL_BOT_API_PID="$pid"
    return 0
  fi
  rm -f "$TELEGRAM_LOCAL_BOT_API_PID_FILE"
  return 1
}

telegram_local_bot_api_ready() {
  local port
  port="$(telegram_local_bot_api_port)"
  VIVENTIUM_PORT_CHECK_HOST="$(telegram_local_bot_api_host)" viventium_port_listener_active "$port"
}

telegram_bot_token_fingerprint() {
  if [[ -z "${BOT_TOKEN:-}" ]]; then
    return 1
  fi
  printf '%s' "$BOT_TOKEN" | shasum -a 256 | awk '{print $1}'
}

ensure_telegram_local_bot_api_hosted_logout() {
  if ! telegram_local_bot_api_enabled; then
    return 0
  fi
  if [[ -z "${BOT_TOKEN:-}" ]]; then
    log_error "Telegram local Bot API mode requires BOT_TOKEN before logout handoff"
    return 1
  fi

  mkdir -p "$TELEGRAM_LOCAL_BOT_API_STATE_DIR"
  local token_fingerprint=""
  token_fingerprint="$(telegram_bot_token_fingerprint)" || true
  if [[ -n "$token_fingerprint" ]] && [[ -f "$TELEGRAM_LOCAL_BOT_API_HOSTED_LOGOUT_MARKER_FILE" ]]; then
    local saved_fingerprint=""
    saved_fingerprint="$(tr -d '\r\n' <"$TELEGRAM_LOCAL_BOT_API_HOSTED_LOGOUT_MARKER_FILE" 2>/dev/null || true)"
    if [[ -n "$saved_fingerprint" && "$saved_fingerprint" == "$token_fingerprint" ]]; then
      return 0
    fi
  fi

  local logout_response=""
  logout_response="$(curl -fsS --max-time 10 -X POST "https://api.telegram.org/bot${BOT_TOKEN}/logOut" 2>/dev/null || true)"
  if [[ "$logout_response" == *'"ok":true'* ]]; then
    printf '%s\n' "$token_fingerprint" >"$TELEGRAM_LOCAL_BOT_API_HOSTED_LOGOUT_MARKER_FILE"
    log_success "Telegram hosted Bot API session logged out for local-server mode"
    return 0
  fi

  log_error "Failed to log out Telegram hosted Bot API session before local-server mode"
  return 1
}

start_telegram_local_bot_api() {
  if ! telegram_local_bot_api_enabled; then
    return 0
  fi

  local local_host=""
  local local_port=""
  local local_binary=""
  local local_api_id="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID:-}"
  local local_api_hash="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH:-}"
  local_host="$(telegram_local_bot_api_host)"
  local_port="$(telegram_local_bot_api_port)"

  if [[ -z "$local_api_id" || -z "$local_api_hash" ]]; then
    log_error "Telegram local Bot API is enabled but api_id/api_hash are missing"
    return 1
  fi

  if ! local_binary="$(resolve_telegram_local_bot_api_binary)"; then
    log_error "Telegram local Bot API is enabled but the telegram-bot-api binary is unavailable"
    return 1
  fi
  if [[ ! -x "$local_binary" ]]; then
    log_error "Telegram local Bot API binary is not executable: $local_binary"
    return 1
  fi

  if telegram_local_bot_api_pid_is_running; then
    log_success "Telegram local Bot API already running (PID: $TELEGRAM_LOCAL_BOT_API_PID)"
    return 0
  fi

  if telegram_local_bot_api_ready; then
    log_error "Telegram local Bot API port ${local_port} is already occupied by another process"
    return 1
  fi

  if ! ensure_telegram_local_bot_api_hosted_logout; then
    return 1
  fi

  mkdir -p "$TELEGRAM_LOCAL_BOT_API_WORK_DIR" "$TELEGRAM_LOCAL_BOT_API_TEMP_DIR"
  log_info "Starting Telegram local Bot API server on ${local_host}:${local_port}..."
  "$local_binary" \
    --local \
    --api-id="$local_api_id" \
    --api-hash="$local_api_hash" \
    --http-ip-address="$local_host" \
    --http-port="$local_port" \
    --dir="$TELEGRAM_LOCAL_BOT_API_WORK_DIR" \
    --temp-dir="$TELEGRAM_LOCAL_BOT_API_TEMP_DIR" \
    >"$TELEGRAM_LOCAL_BOT_API_LOG_FILE" 2>&1 &
  TELEGRAM_LOCAL_BOT_API_PID=$!
  TELEGRAM_LOCAL_BOT_API_STARTED_BY_SCRIPT=true
  printf '%s\n' "$TELEGRAM_LOCAL_BOT_API_PID" >"$TELEGRAM_LOCAL_BOT_API_PID_FILE"

  local start_tries=0
  while [[ "$start_tries" -lt 15 ]]; do
    if telegram_local_bot_api_ready; then
      log_success "Telegram local Bot API server started (PID: $TELEGRAM_LOCAL_BOT_API_PID)"
      return 0
    fi
    if ! ps -p "$TELEGRAM_LOCAL_BOT_API_PID" >/dev/null 2>&1; then
      rm -f "$TELEGRAM_LOCAL_BOT_API_PID_FILE"
      log_error "Telegram local Bot API server failed to start (see $TELEGRAM_LOCAL_BOT_API_LOG_FILE)"
      tail -30 "$TELEGRAM_LOCAL_BOT_API_LOG_FILE" 2>/dev/null || true
      return 1
    fi
    sleep 1
    start_tries=$((start_tries + 1))
  done

  if telegram_local_bot_api_ready; then
    log_success "Telegram local Bot API server started (PID: $TELEGRAM_LOCAL_BOT_API_PID)"
    return 0
  fi

  log_error "Telegram local Bot API server did not listen on ${local_host}:${local_port} in time"
  return 1
}

restart_detached_librechat_backend() {
  if [[ "$SKIP_LIBRECHAT" == "true" || ! -d "$LIBRECHAT_DIR" ]]; then
    return 0
  fi

  log_warn "Detached LibreChat API watchdog restarting backend"
  kill_port_listeners "$LC_API_PORT" "$LIBRECHAT_DIR"
  kill_by_pattern_scoped "node.*api/server" "$LIBRECHAT_DIR"
  kill_by_pattern_scoped "npm run backend:dev" "$LIBRECHAT_DIR"
  kill_by_pattern_scoped "npm exec nodemon api/server/index.js" "$LIBRECHAT_DIR"
  kill_by_pattern_scoped "cross-env NODE_ENV=development npx nodemon api/server/index.js" "$LIBRECHAT_DIR"
  kill_by_pattern_scoped "node .*nodemon api/server/index.js" "$LIBRECHAT_DIR"

  local port_release_tries=0
  while [[ "$port_release_tries" -lt 10 ]] && port_has_listener "$LC_API_PORT"; do
    sleep 0.5
    port_release_tries=$((port_release_tries + 1))
  done
  if port_has_listener "$LC_API_PORT"; then
    log_warn "Detached LibreChat API watchdog is restarting backend before port ${LC_API_PORT} fully released"
  fi

  (
    trap - INT TERM EXIT HUP
    cd "$LIBRECHAT_DIR"
    if [[ "${USE_LIBRECHAT_WRAPPER:-false}" == "true" && -x "./viventium-start.sh" ]]; then
      exec ./viventium-start.sh --backend-only
    fi
    exec npm run backend:dev
  ) >>"$LIBRECHAT_API_WATCHDOG_LOG_FILE" 2>&1 &
}

start_detached_librechat_api_watchdog() {
  if [[ "$SKIP_LIBRECHAT" == "true" || ! -d "$LIBRECHAT_DIR" ]]; then
    return 0
  fi

  stop_detached_librechat_api_watchdog
  mkdir -p "$(dirname "$LIBRECHAT_API_WATCHDOG_LOG_FILE")"

  local interval_s="${LIBRECHAT_API_WATCHDOG_INTERVAL_S:-5}"
  local failure_threshold="${LIBRECHAT_API_WATCHDOG_FAILURE_THRESHOLD:-3}"
  local initial_retries="${LIBRECHAT_API_WATCHDOG_INITIAL_RETRIES:-1800}"
  local recovery_retries="${LIBRECHAT_API_WATCHDOG_RECOVERY_RETRIES:-120}"

  (
    trap 'exit 0' INT TERM HUP
    if ! wait_for_http "${LC_API_URL}/health" "Detached LibreChat API watchdog initial probe" "$initial_retries"; then
      log_warn "Detached LibreChat API watchdog never observed initial API health; exiting"
      exit 0
    fi

    local consecutive_failures=0
    local failed_recoveries=0
    while true; do
      sleep "$interval_s"
      if librechat_api_healthy; then
        consecutive_failures=0
        failed_recoveries=0
        continue
      fi

      consecutive_failures=$((consecutive_failures + 1))
      if [[ "$consecutive_failures" -lt "$failure_threshold" ]]; then
        continue
      fi

      log_warn "Detached LibreChat API watchdog detected ${consecutive_failures} failed health checks"
      restart_detached_librechat_backend
      if wait_for_http "${LC_API_URL}/health" "LibreChat API after detached backend restart" "$recovery_retries"; then
        consecutive_failures=0
        failed_recoveries=0
        continue
      fi
      failed_recoveries=$((failed_recoveries + 1))
      log_warn "Detached LibreChat API watchdog restart did not restore API health in time (failed recoveries: ${failed_recoveries})"
      if [[ "$failed_recoveries" -ge 3 ]]; then
        log_warn "Detached LibreChat API watchdog has failed ${failed_recoveries} recoveries; manual investigation is required if this persists"
      fi
      consecutive_failures="$failure_threshold"
    done
  ) >>"$LIBRECHAT_API_WATCHDOG_LOG_FILE" 2>&1 &

  printf '%s\n' "$!" >"$LIBRECHAT_API_WATCHDOG_PID_FILE"
  log_info "Started detached LibreChat API watchdog (pid: $!, interval: ${interval_s}s)"
}

start_native_livekit_fallback() {
  local livekit_bin="$1"
  local app_support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
  local native_state_dir="${app_support_dir}/state/native"
  local native_log_dir="${app_support_dir}/logs/native"
  local native_profile_state_dir="${app_support_dir}/state/runtime/${VIVENTIUM_RUNTIME_PROFILE}"
  local native_cfg_dir="${native_profile_state_dir}/livekit"
  local native_cfg_file="${native_cfg_dir}/livekit.yaml"
  local native_pid_file="${native_state_dir}/livekit.pid"
  local native_meta_file="${native_state_dir}/livekit.runtime.env"
  local native_log_file="${native_log_dir}/livekit.log"
  local livekit_pid=""

  mkdir -p "$native_state_dir" "$native_log_dir" "$native_profile_state_dir" "$native_cfg_dir"

  write_livekit_config "$native_cfg_file" "${LIVEKIT_TURN_CERT_FILE:-}" "${LIVEKIT_TURN_KEY_FILE:-}"

  cat > "$native_meta_file" <<EOF
LIVEKIT_NODE_IP=${LIVEKIT_NODE_IP}
LIVEKIT_HTTP_PORT=${LIVEKIT_HTTP_PORT}
LIVEKIT_TCP_PORT=${LIVEKIT_TCP_PORT}
LIVEKIT_UDP_PORT=${LIVEKIT_UDP_PORT}
LIVEKIT_TURN_DOMAIN=${LIVEKIT_TURN_DOMAIN:-}
LIVEKIT_TURN_TLS_PORT=${LIVEKIT_TURN_TLS_PORT:-}
LIVEKIT_TURN_CERT_FILE=${LIVEKIT_TURN_CERT_FILE:-}
LIVEKIT_TURN_KEY_FILE=${LIVEKIT_TURN_KEY_FILE:-}
EOF

  echo -e "${YELLOW}[viventium]${NC} LiveKit image is not available locally; using native LiveKit binary ${livekit_bin} for this run"
  nohup "$livekit_bin" \
    --config "$native_cfg_file" \
    --node-ip "$LIVEKIT_NODE_IP" \
    >"$native_log_file" 2>&1 &
  livekit_pid="$!"
  printf '%s\n' "$livekit_pid" >"$native_pid_file"
  LIVEKIT_STARTED_BY_SCRIPT=true

  if ! wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
    log_error "Native LiveKit fallback did not respond at ${LIVEKIT_API_HOST}; check ${native_log_file}"
    return 1
  fi

  log_success "Started native LiveKit fallback (${livekit_bin})"
  return 0
}

write_livekit_config() {
  local config_file="$1"
  local turn_cert_file="$2"
  local turn_key_file="$3"

  cat > "$config_file" <<EOF
port: ${LIVEKIT_HTTP_PORT}
rtc:
  tcp_port: ${LIVEKIT_TCP_PORT}
  udp_port: ${LIVEKIT_UDP_PORT}
EOF

  if [[ -n "${LIVEKIT_TURN_DOMAIN:-}" && -n "${LIVEKIT_TURN_TLS_PORT:-}" && -n "$turn_cert_file" && -n "$turn_key_file" ]]; then
    cat >> "$config_file" <<EOF
turn:
  enabled: true
  domain: "${LIVEKIT_TURN_DOMAIN}"
  tls_port: ${LIVEKIT_TURN_TLS_PORT}
  cert_file: "${turn_cert_file}"
  key_file: "${turn_key_file}"
EOF
  fi

  cat >> "$config_file" <<EOF
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
EOF
}

PARALLEL_OPTIONAL_START_PIDS=()
PARALLEL_OPTIONAL_START_WARNINGS=()
GOOGLE_MCP_STARTED_PRE_LIBRECHAT=false
MS365_MCP_STARTED_PRE_LIBRECHAT=false
OPTIONAL_DOCKER_RECOVERY_PID=""

detached_start_requested() {
  [[ "${VIVENTIUM_DETACHED_START:-false}" == "1" || "${VIVENTIUM_DETACHED_START:-false}" == "true" ]]
}

if detached_start_requested; then
  record_detached_launch_process_group
  # Detached helper launches must let local child services outlive this shell.
  # Ignoring SIGHUP here propagates to background jobs so user-facing processes
  # (LibreChat, playground, voice, Telegram, MCPs) are not torn down when the
  # detached launcher exits.
  trap '' HUP
else
  clear_detached_launch_process_group
fi

queue_parallel_optional_start() {
  local warning_message="$1"
  shift
  (
    if ! "$@"; then
      log_warn "$warning_message"
      exit 1
    fi
  ) &
  PARALLEL_OPTIONAL_START_PIDS+=("$!")
  PARALLEL_OPTIONAL_START_WARNINGS+=("$warning_message")
}

wait_for_parallel_optional_starts() {
  local pid=""
  local idx=0
  local wait_status=0

  if [[ "${#PARALLEL_OPTIONAL_START_PIDS[@]}" -eq 0 ]]; then
    return 0
  fi

  for pid in "${PARALLEL_OPTIONAL_START_PIDS[@]}"; do
    if ! wait "$pid"; then
      wait_status=1
    fi
    idx=$((idx + 1))
  done

  PARALLEL_OPTIONAL_START_PIDS=()
  PARALLEL_OPTIONAL_START_WARNINGS=()
  return "$wait_status"
}

optional_docker_services_still_pending() {
  if [[ "$START_CODE_INTERPRETER" == "true" ]] && ! code_interpreter_health; then
    return 0
  fi
  if [[ "$START_MS365_MCP" == "true" ]] && ! ms365_http_ping "$MS365_MCP_SERVER_URL"; then
    return 0
  fi
  if [[ "$START_RAG_API" == "true" && "$SKIP_LIBRECHAT" != "true" ]] && ! rag_api_http_ping "$VIVENTIUM_RAG_API_PORT"; then
    return 0
  fi
  if [[ "$START_FIRECRAWL" == "true" ]] && ! firecrawl_http_ping; then
    return 0
  fi
  if [[ "$START_SEARXNG" == "true" ]] && ! searxng_http_ping; then
    return 0
  fi
  return 1
}

start_optional_docker_recovery_worker() {
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    return 0
  fi
  if ! docker_backed_services_requested; then
    return 0
  fi
  if ! optional_docker_services_still_pending; then
    return 0
  fi
  if [[ -n "$OPTIONAL_DOCKER_RECOVERY_PID" ]] && kill -0 "$OPTIONAL_DOCKER_RECOVERY_PID" >/dev/null 2>&1; then
    return 0
  fi

  local retries="${VIVENTIUM_OPTIONAL_DOCKER_LATE_RECOVERY_RETRIES:-180}"
  if ! [[ "$retries" =~ ^[0-9]+$ ]] || [[ "$retries" -lt 1 ]]; then
    retries=180
  fi
  local poll_seconds="${VIVENTIUM_OPTIONAL_DOCKER_LATE_RECOVERY_POLL_SECONDS:-5}"
  if ! [[ "$poll_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    poll_seconds=5
  fi

  log_warn "Docker-backed optional services are still warming; background recovery will keep retrying after startup"
  (
    local attempt=0
    while [[ "$attempt" -lt "$retries" ]]; do
      if ! optional_docker_services_still_pending; then
        log_success "Late Docker recovery finished; optional sidecars are now healthy"
        exit 0
      fi

      if ! docker_daemon_ready; then
        request_docker_desktop_launch \
          "Docker daemon not reachable; continuing optional service recovery in the background" || true
        sleep "$poll_seconds"
        attempt=$((attempt + 1))
        continue
      fi

      if [[ "$START_CODE_INTERPRETER" == "true" ]] && ! code_interpreter_health; then
        start_code_interpreter || true
      fi
      if [[ "$START_MS365_MCP" == "true" ]] && ! ms365_http_ping "$MS365_MCP_SERVER_URL"; then
        start_ms365_mcp || true
      fi
      if [[ "$START_RAG_API" == "true" && "$SKIP_LIBRECHAT" != "true" ]] && ! rag_api_http_ping "$VIVENTIUM_RAG_API_PORT"; then
        start_rag_api || true
      fi
      if [[ "$START_FIRECRAWL" == "true" ]] && ! firecrawl_http_ping; then
        start_firecrawl || true
      fi
      if [[ "$START_SEARXNG" == "true" ]] && ! searxng_http_ping; then
        start_searxng || true
      fi

      if ! optional_docker_services_still_pending; then
        log_success "Late Docker recovery finished; optional sidecars are now healthy"
        exit 0
      fi

      sleep "$poll_seconds"
      attempt=$((attempt + 1))
    done

    if optional_docker_services_still_pending; then
      log_warn "Late Docker recovery timed out; some Docker-backed optional services still need attention"
      exit 1
    fi
  ) &
  OPTIONAL_DOCKER_RECOVERY_PID=$!
}

json_get() {
  local file="$1"
  local key="$2"
  "$PYTHON_BIN" - <<PY
import json
try:
    with open("$file", "r") as handle:
        data = json.load(handle)
    print(data.get("$key") or "")
except Exception:
    print("")
PY
}

load_ms365_credentials_from_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  local client_id
  local tenant_id
  local client_secret
  local business_email
  client_id=$(json_get "$file" "MS365_MCP_CLIENT_ID")
  tenant_id=$(json_get "$file" "MS365_MCP_TENANT_ID")
  client_secret=$(json_get "$file" "MS365_MCP_CLIENT_SECRET")
  business_email=$(json_get "$file" "MS365_BUSINESS_EMAIL")
  if [[ -n "$client_id" && -n "$tenant_id" ]]; then
    MS365_MCP_CLIENT_ID="$client_id"
    MS365_MCP_TENANT_ID="$tenant_id"
    if [[ -n "$client_secret" ]]; then
      MS365_MCP_CLIENT_SECRET="$client_secret"
    fi
    if [[ -n "$business_email" ]]; then
      MS365_BUSINESS_EMAIL="$business_email"
    fi
    return 0
  fi
  return 1
}

# === VIVENTIUM START ===
# Feature: Prefer LibreChat-local MS365 credentials for isolated runtime.
# Purpose: Keep the isolated Viventium stack anchored to the LibreChat source of
# truth instead of stale repo-root or v1 fallback credentials from older setups.
# === VIVENTIUM END ===
load_ms365_credentials_from_librechat_env() {
  local env_file="$LIBRECHAT_CANONICAL_ENV_FILE"
  if [[ ! -f "$env_file" ]]; then
    return 1
  fi

  local client_id
  local tenant_id
  local client_secret
  local business_email
  client_id=$(read_env_kv "$env_file" "MS365_MCP_CLIENT_ID" || true)
  tenant_id=$(read_env_kv "$env_file" "MS365_MCP_TENANT_ID" || true)
  client_secret=$(read_env_kv "$env_file" "MS365_MCP_CLIENT_SECRET" || true)
  business_email=$(read_env_kv "$env_file" "MS365_BUSINESS_EMAIL" || true)
  if [[ -z "$client_id" || -z "$tenant_id" ]]; then
    return 1
  fi

  if [[ -n "${MS365_MCP_CLIENT_ID:-}" && "${MS365_MCP_CLIENT_ID}" != "$client_id" ]]; then
    log_warn "MS365 client ID drift detected; using LibreChat source-of-truth credentials for isolated runtime"
  fi
  if [[ -n "${MS365_MCP_TENANT_ID:-}" && "${MS365_MCP_TENANT_ID}" != "$tenant_id" ]]; then
    log_warn "MS365 tenant drift detected; using LibreChat source-of-truth credentials for isolated runtime"
  fi

  MS365_MCP_CLIENT_ID="$client_id"
  MS365_MCP_TENANT_ID="$tenant_id"
  if [[ -n "$client_secret" ]]; then
    MS365_MCP_CLIENT_SECRET="$client_secret"
  fi
  if [[ -n "$business_email" ]]; then
    MS365_BUSINESS_EMAIL="$business_email"
  fi
  return 0
}

load_ms365_credentials() {
  local memory_dir="$LEGACY_V0_3_DIR/viventium_v1/storage/memory"
  if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
    if load_ms365_credentials_from_librechat_env; then
      return 0
    fi
  fi
  if [[ -n "${MS365_MCP_CLIENT_ID:-}" && -n "${MS365_MCP_TENANT_ID:-}" ]]; then
    return 0
  fi
  if [[ -n "${VIVENTIUM_USER_ID:-}" && -f "$memory_dir/$VIVENTIUM_USER_ID/ms365_credentials.json" ]]; then
    if load_ms365_credentials_from_file "$memory_dir/$VIVENTIUM_USER_ID/ms365_credentials.json"; then
      return 0
    fi
  fi
  if [[ -d "$memory_dir" ]]; then
    for user_dir in "$memory_dir"/*; do
      if [[ -f "$user_dir/ms365_credentials.json" ]]; then
        if load_ms365_credentials_from_file "$user_dir/ms365_credentials.json"; then
          return 0
        fi
      fi
    done
  fi
  if [[ -f "$VIVENTIUM_CORE_DIR/ms365_mcp.env" ]]; then
    # shellcheck disable=SC1090
    source "$VIVENTIUM_CORE_DIR/ms365_mcp.env"
    if [[ -n "${MS365_MCP_CLIENT_ID:-}" && -n "${MS365_MCP_TENANT_ID:-}" ]]; then
      return 0
    fi
  fi
  return 1
}

ms365_http_ping() {
  local url="$1"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$url" \
    -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' || true)
  if [[ "$status" = "200" || "$status" = "401" ]]; then
    return 0
  fi
  return 1
}

# === VIVENTIUM START ===
# Feature: MS365 MCP restart ownership enforcement.
# Purpose: Reclaim the shipped MS365 MCP port from foreign listeners instead of
# silently reusing another workspace's server and credentials.
# === VIVENTIUM END ===
ms365_port_listener_is_viventium_owned() {
  local port="${1:-$MS365_MCP_PORT}"

  if command -v docker >/dev/null 2>&1 && docker_daemon_ready; then
    if docker ps -q --filter "name=^/viventium_ms365_mcp$" 2>/dev/null | head -1 | grep -q .; then
      return 0
    fi
  fi

  local pids
  pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    return 1
  fi

  local pid
  for pid in $pids; do
    if pid_matches_scope "$pid" "$ROOT_DIR/MCPs/ms-365-mcp-server"; then
      return 0
    fi
    if pid_matches_scope "$pid" "$LEGACY_V0_3_DIR"; then
      return 0
    fi
    if pid_matches_scope "$pid" "$VIVENTIUM_CORE_DIR"; then
      return 0
    fi
  done

  return 1
}

searxng_http_ping() {
  local base_url="${SEARXNG_INSTANCE_URL:-http://localhost:${SEARXNG_PORT}}"
  base_url="${base_url%/}"
  # A real search request can be slow on cold start while upstream engines warm.
  # Use the root page as the readiness check so local installs do not treat a
  # healthy SearXNG container as failed just because the first query is slow.
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${base_url}/" || true)
  [[ "$status" =~ ^(2|3)[0-9][0-9]$ ]]
}

firecrawl_http_ping() {
  local base_url="${FIRECRAWL_BASE_URL:-${FIRECRAWL_API_URL:-}}"
  base_url="${base_url%/}"
  if [[ -z "$base_url" ]]; then
    return 1
  fi
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" "${base_url}/health" || true)
  if [[ "$status" = "200" ]]; then
    return 0
  fi

  # Firecrawl local image responds on `/` with an API banner in some versions.
  if curl -s --max-time 3 "${base_url}/" | grep -q "Firecrawl API"; then
    return 0
  fi

  if docker_daemon_ready; then
    if docker ps -q --filter "name=^/viventium_firecrawl_api$" 2>/dev/null | head -1 | grep -q .; then
      return 0
    fi
  fi

  if port_in_use "$FIRECRAWL_PORT"; then
    return 1
  fi
  return 1
}

# === VIVENTIUM START ===
# Feature: Skyvern API readiness probe compatibility.
# Purpose: Support Skyvern builds that expose /docs or /openapi.json instead of /api/v1/health.
skyvern_http_ping() {
  local endpoint
  local status
  local endpoints=(
    "/api/v1/health"
    "/docs"
    "/openapi.json"
  )
  for endpoint in "${endpoints[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${SKYVERN_API_PORT}${endpoint}" || true)
    if [[ "$status" =~ ^2 ]]; then
      return 0
    fi
  done
  return 1
}
# === VIVENTIUM END ===

verify_google_workspace_tools() {
  local response
  response=$(curl -s -X POST "http://localhost:${GOOGLE_MCP_PORT}/mcp" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null || echo "")
  if [[ -z "$response" ]]; then
    return 1
  fi
  if echo "$response" | grep -q '"tools"'; then
    return 0
  fi
  return 1
}

google_mcp_health_ping() {
  curl -s --max-time 2 "http://localhost:${GOOGLE_MCP_PORT}/health" >/dev/null 2>&1
}

google_mcp_ready() {
  if google_mcp_health_ping; then
    return 0
  fi
  if [[ "$SKIP_MCP_VERIFY" == "true" ]]; then
    return 1
  fi
  verify_google_workspace_tools
}

# === VIVENTIUM START ===
# Feature: Reconcile local Google OAuth state across Google MCP restarts.
# Purpose: FastMCP's Google OAuth proxy persists OAuth clients but not refresh
# tokens by default, so stale LibreChat-side Google token docs must be cleared
# when no matching local Google MCP refresh-token state exists.
google_workspace_refresh_token_state_file() {
  local fastmcp_home="${FASTMCP_HOME:-$VIVENTIUM_STATE_ROOT/google_workspace_mcp/fastmcp}"
  printf "%s/oauth-proxy-tokens/google_refresh_tokens.json" "$fastmcp_home"
}

google_workspace_refresh_token_state_ready() {
  local state_file
  state_file="$(google_workspace_refresh_token_state_file)"
  if [[ ! -s "$state_file" ]]; then
    return 1
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text())
except Exception:
    raise SystemExit(1)

tokens = payload.get("refresh_tokens")
if isinstance(tokens, list) and any(isinstance(token, dict) and token.get("token") for token in tokens):
    raise SystemExit(0)
raise SystemExit(1)
PY
    return $?
  fi

  grep -q '"token"' "$state_file"
}

google_workspace_credentials_state_ready() {
  local credentials_dir="${GOOGLE_MCP_CREDENTIALS_DIR:-$VIVENTIUM_STATE_ROOT/google_workspace_mcp/credentials}"
  if [[ ! -d "$credentials_dir" ]]; then
    return 1
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$credentials_dir" <<'PY'
import json
import sys
from pathlib import Path

base = Path(sys.argv[1])
for path in sorted(base.glob("*.json")):
    try:
        payload = json.loads(path.read_text())
    except Exception:
        continue
    if payload.get("refresh_token"):
        raise SystemExit(0)
raise SystemExit(1)
PY
    return $?
  fi

  rg -l '"refresh_token"\s*:\s*".+"' "$credentials_dir"/*.json >/dev/null 2>&1
}

google_workspace_local_oauth_state_ready() {
  google_workspace_refresh_token_state_ready || google_workspace_credentials_state_ready
}

reconcile_google_workspace_local_oauth_state() {
  if [[ "$START_GOOGLE_MCP" != "true" || "$VIVENTIUM_RUNTIME_PROFILE" != "isolated" ]]; then
    return 0
  fi

  if google_workspace_local_oauth_state_ready; then
    return 0
  fi

  if ! command -v mongosh >/dev/null 2>&1; then
    log_warn "mongosh not found; cannot reconcile stale local Google Workspace MCP tokens"
    return 0
  fi

  if ! mongo_ping "$MONGO_URI"; then
    log_warn "MongoDB not ready; skipping Google Workspace MCP token reconciliation"
    return 0
  fi

  local stale_count
  stale_count=$(
    mongosh "$MONGO_URI" --quiet --eval 'db.tokens.countDocuments({identifier:/^mcp:google_workspace(?::|$)/})' 2>/dev/null | tr -d '\r[:space:]'
  )
  if [[ -z "$stale_count" || "$stale_count" == "0" ]]; then
    return 0
  fi

  local backup_dir="$VIVENTIUM_STATE_ROOT/backups"
  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local backup_file="$backup_dir/google_workspace_tokens_stale_${timestamp}.json"
  mkdir -p "$backup_dir"

  if ! mongosh "$MONGO_URI" --quiet --eval 'const docs=db.tokens.find({identifier:/^mcp:google_workspace(?::|$)/}).toArray(); print(EJSON.stringify(docs, null, 2));' >"$backup_file"; then
    log_warn "Failed to back up stale local Google Workspace MCP tokens to $backup_file"
    rm -f "$backup_file" >/dev/null 2>&1 || true
    return 0
  fi

  local deleted_count
  deleted_count=$(
    mongosh "$MONGO_URI" --quiet --eval 'const result=db.tokens.deleteMany({identifier:/^mcp:google_workspace(?::|$)/}); print(result.deletedCount);' 2>/dev/null | tr -d '\r[:space:]'
  )
  if [[ -z "$deleted_count" || "$deleted_count" == "0" ]]; then
    return 0
  fi

  log_warn "Cleared $deleted_count stale local Google Workspace MCP token doc(s); no durable local Google MCP auth state was found"
  log_info "Backed up stale Google Workspace MCP token docs to $backup_file"
  return 0
}
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Local Google OAuth redirect preflight.
# Purpose: Catch cloud-side redirect drift before the user clicks auth in the UI,
# so fresh-machine setup fails fast with the real cause instead of generic "Authentication failed".
verify_google_oauth_redirect_registration() {
  if [[ "$START_GOOGLE_MCP" != "true" || "$VIVENTIUM_RUNTIME_PROFILE" != "isolated" ]]; then
    return 0
  fi

  if [[ -z "${GOOGLE_OAUTH_CLIENT_ID:-}" || -z "${GOOGLE_OAUTH_REDIRECT_URI:-}" ]]; then
    return 0
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    log_warn "python3 not found; skipping Google OAuth redirect preflight"
    return 0
  fi

  local auth_url
  auth_url=$(
    python3 - "${GOOGLE_OAUTH_CLIENT_ID}" "${GOOGLE_OAUTH_REDIRECT_URI}" "${GOOGLE_WORKSPACE_MCP_SCOPE}" <<'PY'
import sys
from urllib.parse import urlencode

client_id, redirect_uri, scope = sys.argv[1:4]
params = {
    "client_id": client_id,
    "redirect_uri": redirect_uri,
    "response_type": "code",
    "scope": scope,
    "access_type": "offline",
    "prompt": "consent",
}
print("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
PY
  ) || return 0

  local response
  response=$(curl -sL --max-time 20 "$auth_url" || true)
  if [[ -z "$response" ]]; then
    log_warn "Google OAuth redirect preflight could not reach Google; continuing"
    return 0
  fi

  if echo "$response" | grep -qi 'redirect_uri_mismatch'; then
    log_error "Google OAuth redirect preflight failed for client ${GOOGLE_OAUTH_CLIENT_ID}"
    log_error "Authorized redirect URIs must include ${GOOGLE_OAUTH_REDIRECT_URI}"
    return 1
  fi

  log_success "Google OAuth redirect preflight passed"
  return 0
}
# === VIVENTIUM END ===

code_interpreter_health() {
  local url="${LIBRECHAT_CODE_BASEURL%/}/health"
  if curl -s --max-time 3 "$url" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

run_health_checks() {
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  Health Checks${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  local failures=0

  if [[ "$SKIP_LIVEKIT" != "true" ]]; then
    if wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
      :
    else
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_GOOGLE_MCP" == "true" ]]; then
    if wait_for_http "http://localhost:${GOOGLE_MCP_PORT}/health" "Google Workspace MCP"; then
      if [[ "$SKIP_MCP_VERIFY" == "true" ]]; then
        log_info "Skipping Google Workspace MCP tools verification"
      elif verify_google_workspace_tools; then
        log_success "Google Workspace MCP tools OK"
      else
        log_warn "Google Workspace MCP tools not verified"
      fi
    else
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_MS365_MCP" == "true" ]]; then
    if ms365_http_ping "$MS365_MCP_SERVER_URL"; then
      log_success "MS365 MCP responded"
    else
      log_warn "MS365 MCP did not respond yet"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_RAG_API" == "true" && "$SKIP_LIBRECHAT" != "true" ]] && ollama_embeddings_enabled_for_rag; then
    if ollama_http_ping "$(ollama_host_base_url)"; then
      log_success "Ollama embeddings runtime ready"
    else
      log_warn "Ollama embeddings runtime did not respond yet"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_RAG_API" == "true" && "$SKIP_LIBRECHAT" != "true" ]]; then
    if rag_api_http_ping "$VIVENTIUM_RAG_API_PORT"; then
      log_success "Local RAG API ready"
    else
      log_warn "Local RAG API did not respond yet"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_CODE_INTERPRETER" == "true" ]]; then
    if code_interpreter_health; then
      log_success "Code Interpreter API ready"
    else
      log_warn "Code Interpreter API did not respond"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_FIRECRAWL" == "true" ]]; then
    if firecrawl_http_ping; then
      log_success "Firecrawl scraper ready"
    else
      log_warn "Firecrawl did not respond yet"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_SEARXNG" == "true" ]]; then
    if searxng_http_ping; then
      log_success "SearxNG search ready"
    else
      log_warn "SearxNG did not respond yet"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$START_V1_AGENT" == "true" && -d "$V1_AGENT_DIR" ]]; then
    if pgrep -f "frontal_cortex.agent start" >/dev/null 2>&1; then
      log_success "V1 agent process running"
    else
      log_warn "V1 agent process not found"
      failures=$((failures + 1))
    fi

    if port_in_use "$MS365_MCP_CALLBACK_PORT"; then
      log_success "MS365 OAuth callback port listening"
    else
      log_warn "MS365 OAuth callback port not listening"
    fi
  fi

  if [[ "$START_TELEGRAM" == "true" && -n "${BOT_TOKEN:-}" ]]; then
    if telegram_pid_is_running; then
      log_success "Telegram bot process running"
    else
      log_warn "Telegram bot process not found"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$SKIP_LIBRECHAT" != "true" ]]; then
    local librechat_api_retries="${LIBRECHAT_API_HEALTH_RETRIES:-$(default_librechat_health_retries)}"
    local librechat_frontend_retries="${LIBRECHAT_FRONTEND_HEALTH_RETRIES:-$(default_librechat_health_retries)}"
    if mongo_ping "$MONGO_URI"; then
      log_success "MongoDB ready"
    else
      log_warn "MongoDB did not respond yet"
      failures=$((failures + 1))
    fi
    if is_truthy "${SEARCH:-false}"; then
      if wait_for_http "${MEILI_HOST%/}/health" "Meilisearch"; then
        :
      else
        failures=$((failures + 1))
      fi
    fi
    if wait_for_http "${LC_API_URL}/health" "LibreChat API" "$librechat_api_retries"; then
      :
    else
      failures=$((failures + 1))
    fi
    if wait_for_http "${LC_FRONTEND_URL}" "LibreChat Frontend" "$librechat_frontend_retries"; then
      :
    else
      failures=$((failures + 1))
    fi
  fi

  if [[ "$SKIP_PLAYGROUND" != "true" ]]; then
    local playground_port
    playground_port=$(get_playground_port)
    if wait_for_http "http://localhost:${playground_port}" "$PLAYGROUND_LABEL"; then
      :
    else
      failures=$((failures + 1))
    fi
  fi

  ## === VIVENTIUM START ===
  # Feature: Provider-agnostic voice gateway health validation
  # Purpose: Check worker process regardless of selected STT/TTS provider (not just OPENAI_API_KEY path)
  if [[ "$SKIP_VOICE_GATEWAY" != "true" && -d "$VOICE_GATEWAY_DIR" ]]; then
    local voice_gateway_ok=false
    local voice_gateway_health_port="${VIVENTIUM_VOICE_GATEWAY_HEALTH_PORT:-${VOICE_GATEWAY_PORT:-8000}}"
    for _ in $(seq 1 45); do
      local runtime_voice_pids=""
      runtime_voice_pids="$(find_voice_gateway_runtime_pids "$VOICE_GATEWAY_DIR")"
      if [[ "$VOICE_GATEWAY_STARTED_BY_SCRIPT" == "true" ]]; then
        if [[ -f "$LOG_DIR/voice_gateway.log" ]] && grep -q '"registered worker"' "$LOG_DIR/voice_gateway.log"; then
          voice_gateway_ok=true
          break
        fi
      elif [[ -n "$runtime_voice_pids" ]]; then
        voice_gateway_ok=true
        break
      fi
      if [[ "$VOICE_GATEWAY_STARTED_BY_SCRIPT" == "true" && -n "${VOICE_GATEWAY_PID:-}" ]]; then
        if ps -p "$VOICE_GATEWAY_PID" >/dev/null 2>&1; then
          :
        fi
      elif pgrep -f "worker.py.*start" >/dev/null 2>&1 || pgrep -f "worker.py.*dev" >/dev/null 2>&1; then
        voice_gateway_ok=true
        break
      fi
      if curl -fsS --max-time 2 "http://localhost:${voice_gateway_health_port}/health" >/dev/null 2>&1; then
        voice_gateway_ok=true
        break
      fi
      sleep 1
    done

    if [[ "$voice_gateway_ok" == "true" ]]; then
      log_success "Voice Gateway worker process running"
    else
      log_warn "Voice Gateway worker process not found (see $LOG_DIR/voice_gateway.log)"
      failures=$((failures + 1))
    fi
  fi
  ## === VIVENTIUM END ===

  if [[ "$failures" -gt 0 ]]; then
    log_warn "Health checks reported $failures issue(s) - see logs above"
  else
    log_success "Health checks passed"
  fi
}

cleanup() {
  if [[ "$CLEANUP_ENABLED" != "true" ]]; then
    return
  fi
  echo ""
  echo -e "${YELLOW}[viventium]${NC} Shutting down..."
  stop_detached_librechat_api_watchdog
  stop_telegram_local_bot_api
  [[ "$VOICE_GATEWAY_STARTED_BY_SCRIPT" == "true" && -n "${VOICE_GATEWAY_PID:-}" ]] && kill "${VOICE_GATEWAY_PID}" 2>/dev/null || true
  local cleanup_voice_gateway_runtime_pids=""
  cleanup_voice_gateway_runtime_pids="$(find_voice_gateway_runtime_pids "$VOICE_GATEWAY_DIR")"
  if [[ -n "$cleanup_voice_gateway_runtime_pids" ]]; then
    kill_pids "$cleanup_voice_gateway_runtime_pids"
  fi
  [[ "$PLAYGROUND_STARTED_BY_SCRIPT" == "true" && -n "${PLAYGROUND_PID:-}" ]] && kill "${PLAYGROUND_PID}" 2>/dev/null || true
  [[ "$LIBRECHAT_STARTED_BY_SCRIPT" == "true" && -n "${LIBRECHAT_PID:-}" ]] && kill "${LIBRECHAT_PID}" 2>/dev/null || true
  [[ -n "${OPTIONAL_DOCKER_RECOVERY_PID:-}" ]] && kill "${OPTIONAL_DOCKER_RECOVERY_PID}" 2>/dev/null || true
  if [[ "$LIBRECHAT_STARTED_BY_SCRIPT" == "true" ]]; then
    pkill -f "node.*api/server" 2>/dev/null || true
    pkill -f "vite.*client" 2>/dev/null || true
  fi
  [[ "$V1_AGENT_STARTED_BY_SCRIPT" == "true" && -n "${V1_AGENT_PID:-}" ]] && kill "${V1_AGENT_PID}" 2>/dev/null || true
  [[ "$TELEGRAM_STARTED_BY_SCRIPT" == "true" && -n "${TELEGRAM_BOT_PID:-}" ]] && kill "${TELEGRAM_BOT_PID}" 2>/dev/null || true
  local cleanup_telegram_deferred_pid=""
  cleanup_telegram_deferred_pid="$(read_pid_file "$TELEGRAM_BOT_DEFERRED_PID_FILE")"
  if [[ -n "$cleanup_telegram_deferred_pid" ]]; then
    kill_pids "$cleanup_telegram_deferred_pid"
    rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE"
  fi
  rm -f "$TELEGRAM_BOT_DEFERRED_MARKER_FILE"
  [[ "$GOOGLE_MCP_STARTED_BY_SCRIPT" == "true" && -n "${GOOGLE_MCP_PID:-}" ]] && kill "${GOOGLE_MCP_PID}" 2>/dev/null || true
  stop_remote_call_tunnels
  stop_pid_file_scoped "$GOOGLE_MCP_PID_FILE" "$GOOGLE_MCP_DIR"
  [[ "$SCHEDULING_MCP_STARTED_BY_SCRIPT" == "true" && -n "${SCHEDULING_MCP_PID:-}" ]] && kill "${SCHEDULING_MCP_PID}" 2>/dev/null || true
  stop_pid_file_scoped "$SCHEDULING_MCP_PID_FILE" "$SCHEDULING_MCP_DIR"
  [[ "${GLASSHIVE_STARTED_BY_SCRIPT:-false}" == "true" && -n "${GLASSHIVE_RUNTIME_PID:-}" ]] && kill "${GLASSHIVE_RUNTIME_PID}" 2>/dev/null || true
  [[ "${GLASSHIVE_STARTED_BY_SCRIPT:-false}" == "true" && -n "${GLASSHIVE_MCP_PID:-}" ]] && kill "${GLASSHIVE_MCP_PID}" 2>/dev/null || true
  [[ "${GLASSHIVE_STARTED_BY_SCRIPT:-false}" == "true" && -n "${GLASSHIVE_UI_PID:-}" ]] && kill "${GLASSHIVE_UI_PID}" 2>/dev/null || true
  if [[ "${GLASSHIVE_STARTED_BY_SCRIPT:-false}" == "true" ]]; then
    stop_pid_file_scoped "$GLASSHIVE_RUNTIME_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
    stop_pid_file_scoped "$GLASSHIVE_MCP_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
    stop_pid_file_scoped "$GLASSHIVE_UI_PID_FILE" "$GLASSHIVE_UI_DIR"
  fi
  [[ "$MS365_CALLBACK_STARTED_BY_SCRIPT" == "true" && -n "${MS365_MCP_CALLBACK_PID:-}" ]] && kill "${MS365_MCP_CALLBACK_PID}" 2>/dev/null || true
  if [[ "$SKIP_DOCKER" != "true" ]]; then
    if [[ "$MS365_STARTED_BY_SCRIPT" == "true" ]]; then
      docker compose -f "$ROOT_DIR/docker/ms365-mcp/docker-compose.yml" down >/dev/null 2>&1 || true
    fi
    if [[ "$RAG_API_STARTED_BY_SCRIPT" == "true" ]]; then
      (
        cd "$LIBRECHAT_DIR"
        RAG_PORT="$VIVENTIUM_RAG_API_PORT" docker compose -f "$LIBRECHAT_DIR/rag.yml" down >/dev/null 2>&1 || true
      )
    fi
    ## === VIVENTIUM START ===
    # Feature: Symmetric cleanup for optional docker services
    if [[ "$SEARXNG_STARTED_BY_SCRIPT" == "true" ]]; then
      docker compose -f "$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/searxng/docker-compose.yml" down >/dev/null 2>&1 || true
    fi
    if [[ "$FIRECRAWL_STARTED_BY_SCRIPT" == "true" ]]; then
      docker compose -f "$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/firecrawl/docker-compose.yml" down >/dev/null 2>&1 || true
    fi
    ## === VIVENTIUM END ===
    if [[ "$CODE_INTERPRETER_STARTED_BY_SCRIPT" == "true" ]]; then
      local ci_compose_file="$CODE_INTERPRETER_DIR/docker-compose.ghcr.yml"
      if [[ ! -f "$ci_compose_file" ]]; then
        ci_compose_file="$CODE_INTERPRETER_DIR/docker-compose.yml"
      fi
      if [[ -f "$ci_compose_file" ]]; then
        (
          cd "$CODE_INTERPRETER_DIR"
          docker compose -f "$ci_compose_file" down >/dev/null 2>&1 || true
        )
      fi

      local ci_project_containers
      ci_project_containers=$(docker ps -aq --filter "label=com.docker.compose.project=librecodeinterpreter" 2>/dev/null || true)
      if [[ -n "$ci_project_containers" ]]; then
        docker rm -f $ci_project_containers >/dev/null 2>&1 || true
      fi

      local ci_containers
      ci_containers=$(
        docker ps -aq \
          --filter "label=viventium.stack=viventium_v0_4" \
          --filter "label=viventium.component=code-interpreter" \
          2>/dev/null || true
      )
      if [[ -n "$ci_containers" ]]; then
        docker rm -f $ci_containers >/dev/null 2>&1 || true
      fi
    fi
    if [[ "$MONGO_STARTED_BY_SCRIPT" == "true" ]]; then
      local mongo_container
      mongo_container=$(docker ps -aq --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null | head -1 || true)
      if [[ -n "$mongo_container" ]]; then
        docker rm -f "$mongo_container" >/dev/null 2>&1 || true
      fi
    fi
    if [[ "$LIVEKIT_STARTED_BY_SCRIPT" == "true" && -n "${LIVEKIT_CONTAINER_ID:-}" ]]; then
      docker rm -f "${LIVEKIT_CONTAINER_ID}" >/dev/null 2>&1 || true
    fi
  fi
  if [[ "$MONGO_NATIVE_STARTED_BY_SCRIPT" == "true" && -f "$MONGO_NATIVE_PID_FILE" ]]; then
    local mongo_native_pid
    mongo_native_pid="$(cat "$MONGO_NATIVE_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$mongo_native_pid" ]]; then
      kill "$mongo_native_pid" 2>/dev/null || true
    fi
    rm -f "$MONGO_NATIVE_PID_FILE"
  fi
  if [[ "$MEILI_NATIVE_STARTED_BY_SCRIPT" == "true" && -f "$MEILI_NATIVE_PID_FILE" ]]; then
    local meili_native_pid
    meili_native_pid="$(cat "$MEILI_NATIVE_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$meili_native_pid" ]]; then
      kill "$meili_native_pid" 2>/dev/null || true
    fi
    rm -f "$MEILI_NATIVE_PID_FILE"
  fi
  ## === VIVENTIUM START ===
  # Feature: Symmetric cleanup for Skyvern helper script lifecycle
  if [[ "$SKYVERN_STARTED_BY_SCRIPT" == "true" ]]; then
    local skyvern_script="$ROOT_DIR/viventium-skyvern-start.sh"
    if [[ -x "$skyvern_script" ]]; then
      "$skyvern_script" stop >/dev/null 2>&1 || true
    fi
    if docker_daemon_ready; then
      local skyvern_project_containers
      skyvern_project_containers=$(docker ps -aq --filter "label=com.docker.compose.project=skyvern" 2>/dev/null || true)
      if [[ -n "$skyvern_project_containers" ]]; then
        docker rm -f $skyvern_project_containers >/dev/null 2>&1 || true
      fi
    fi
  fi
  ## === VIVENTIUM END ===
  echo -e "${GREEN}[viventium]${NC} All services stopped."
}
trap cleanup INT TERM EXIT

resolve_telegram_dir() {
  if [[ -d "$TELEGRAM_DIR_PRIMARY" ]]; then
    echo "$TELEGRAM_DIR_PRIMARY"
    return 0
  fi
  if [[ -d "$TELEGRAM_DIR_FALLBACK" ]]; then
    echo "$TELEGRAM_DIR_FALLBACK"
    return 0
  fi
  echo ""
  return 1
}

resolve_telegram_codex_dir() {
  if [[ -d "$TELEGRAM_CODEX_DIR" ]]; then
    echo "$TELEGRAM_CODEX_DIR"
    return 0
  fi
  echo ""
  return 1
}

ensure_telegram_media_prereqs() {
  if command -v ffmpeg >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$(uname -s)" != "Darwin" ]]; then
    log_error "Telegram voice/video media requires ffmpeg in PATH on this host"
    return 1
  fi

  if ! command -v brew >/dev/null 2>&1; then
    if [[ "${VIVENTIUM_AUTO_INSTALL_BREW:-true}" != "true" ]] || ! command -v curl >/dev/null 2>&1; then
      log_error "Telegram voice/video media requires ffmpeg. Run bin/viventium install or install ffmpeg manually."
      return 1
    fi

    local brew_bootstrap_log="$LOG_DIR/telegram_bot_homebrew_install.log"
    log_warn "Homebrew missing; attempting automatic install for Telegram media prerequisites"
    NONINTERACTIVE=1 CI=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" >"$brew_bootstrap_log" 2>&1 || {
      log_error "Failed to install Homebrew automatically for Telegram media prerequisites"
      tail -20 "$brew_bootstrap_log" 2>/dev/null || true
      return 1
    }
  fi

  local brew_prefix=""
  brew_prefix="$(brew --prefix 2>/dev/null || true)"
  if [[ -n "$brew_prefix" && -d "$brew_prefix/bin" ]]; then
    export PATH="$brew_prefix/bin:$brew_prefix/sbin:${PATH}"
  fi

  if [[ "${VIVENTIUM_AUTO_INSTALL_FFMPEG:-true}" != "true" ]]; then
    log_error "Telegram voice/video media requires ffmpeg. Install it or rerun the installer with auto-install enabled."
    return 1
  fi

  local ffmpeg_log="$LOG_DIR/telegram_bot_ffmpeg_install.log"
  log_warn "ffmpeg missing; attempting automatic install for Telegram media support"
  if ! HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg >"$ffmpeg_log" 2>&1; then
    log_error "Failed to install ffmpeg for Telegram media support"
    tail -20 "$ffmpeg_log" 2>/dev/null || true
    return 1
  fi

  if ! command -v ffmpeg >/dev/null 2>&1; then
    log_error "ffmpeg install finished but the binary is still unavailable to Telegram"
    return 1
  fi

  log_success "ffmpeg is ready for Telegram media support"
  return 0
}

start_google_workspace_mcp() {
  if [[ "$START_GOOGLE_MCP" != "true" ]]; then
    log_info "Skipping Google Workspace MCP startup"
    return 0
  fi

  if [[ ! -d "$GOOGLE_MCP_DIR" ]]; then
    log_warn "Google Workspace MCP directory not found: $GOOGLE_MCP_DIR"
    return 1
  fi

  if ! command -v uv >/dev/null 2>&1; then
    log_error "uv not found (required for Google Workspace MCP)"
    return 1
  fi

  local allow_fallback=false
  if [[ "$GOOGLE_MCP_PORT_WAS_DEFAULT" == "true" && "$GOOGLE_MCP_URLS_WERE_DEFAULT" == "true" ]]; then
    allow_fallback=true
  fi

  # === VIVENTIUM START ===
  # Feature: Clean up stale legacy Google MCP listener when running isolated local profile.
  # Purpose: Prevent old port-8000 Google MCP processes from serving stale OAuth flows.
  # === VIVENTIUM END ===
  if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" && "$GOOGLE_MCP_PORT" != "8000" ]] && port_in_use 8000; then
    kill_port_listeners "8000" "$GOOGLE_MCP_DIR"
  fi

  if port_in_use "$GOOGLE_MCP_PORT"; then
    if google_mcp_ready; then
      log_success "Google Workspace MCP already running on port $GOOGLE_MCP_PORT"
      return 0
    fi
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "Port $GOOGLE_MCP_PORT is in use; restarting Google Workspace MCP"
      kill_port_listeners "$GOOGLE_MCP_PORT" "$GOOGLE_MCP_DIR"
      if port_in_use "$GOOGLE_MCP_PORT"; then
        if google_mcp_ready; then
          log_warn "Google Workspace MCP still reachable on port $GOOGLE_MCP_PORT; using existing service"
          return 0
        fi
        if [[ "$allow_fallback" == "true" ]]; then
          local fallback_port
          fallback_port=$(find_free_port "$GOOGLE_MCP_PORT" "$MS365_MCP_CALLBACK_PORT" "$CODE_INTERPRETER_PORT")
          log_warn "Port $GOOGLE_MCP_PORT is still in use; using $fallback_port for this run"
          GOOGLE_MCP_PORT="$fallback_port"
          refresh_google_mcp_urls
        else
          log_error "Port $GOOGLE_MCP_PORT is still in use; skipping Google Workspace MCP startup"
          return 1
        fi
      fi
    else
      if [[ "$allow_fallback" == "true" ]]; then
        local fallback_port
        fallback_port=$(find_free_port "$GOOGLE_MCP_PORT" "$MS365_MCP_CALLBACK_PORT" "$CODE_INTERPRETER_PORT")
        log_warn "Port $GOOGLE_MCP_PORT is in use; using $fallback_port for this run"
        GOOGLE_MCP_PORT="$fallback_port"
        refresh_google_mcp_urls
      else
        log_error "Port $GOOGLE_MCP_PORT is already in use"
        return 1
      fi
    fi
  fi

  log_info "Starting Google Workspace MCP..."
  export MCP_ENABLE_OAUTH="${MCP_ENABLE_OAUTH:-true}"
  if [[ -z "${MCP_ENABLE_OAUTH21:-}" ]]; then
    if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
      export MCP_ENABLE_OAUTH21="true"
    else
      export MCP_ENABLE_OAUTH21="false"
    fi
  fi
  export WORKSPACE_MCP_PORT="$GOOGLE_MCP_PORT"
  export WORKSPACE_MCP_BASE_URI="${WORKSPACE_MCP_BASE_URI:-http://localhost}"
  if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
    load_google_oauth_from_librechat_env || true
    export FASTMCP_HOME="${FASTMCP_HOME:-$VIVENTIUM_STATE_ROOT/google_workspace_mcp/fastmcp}"
    export GOOGLE_MCP_CREDENTIALS_DIR="${GOOGLE_MCP_CREDENTIALS_DIR:-$VIVENTIUM_STATE_ROOT/google_workspace_mcp/credentials}"
    export GOOGLE_OAUTH_REDIRECT_URI="${GOOGLE_OAUTH_REDIRECT_URI:-http://localhost:${GOOGLE_MCP_PORT}/oauth2callback}"
    mkdir -p "$FASTMCP_HOME"
    mkdir -p "$GOOGLE_MCP_CREDENTIALS_DIR"
  fi
  if [[ -n "${GOOGLE_CLIENT_ID:-}" && -z "${GOOGLE_OAUTH_CLIENT_ID:-}" ]]; then
    export GOOGLE_OAUTH_CLIENT_ID="$GOOGLE_CLIENT_ID"
  fi
  if [[ -n "${GOOGLE_CLIENT_SECRET:-}" && -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    export GOOGLE_OAUTH_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET"
  fi
  # === VIVENTIUM START ===
  # Feature: Canonicalize legacy Google env vars to the active OAuth app.
  # Purpose: Prevent fallback tool-auth code from reviving stale repo-root Google client IDs.
  # === VIVENTIUM END ===
  if [[ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" ]]; then
    export GOOGLE_CLIENT_ID="$GOOGLE_OAUTH_CLIENT_ID"
  fi
  if [[ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    export GOOGLE_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET"
  fi
  if [[ -z "${GOOGLE_OAUTH_CLIENT_ID:-}" || -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    log_warn "Google OAuth client credentials not set - OAuth flow may fail"
  fi
  local librechat_callback="${LC_API_URL}/api/mcp/google_workspace/oauth/callback"
  if [[ -z "${OAUTH_CUSTOM_REDIRECT_URIS:-}" ]]; then
    export OAUTH_CUSTOM_REDIRECT_URIS="$librechat_callback"
  elif [[ "${OAUTH_CUSTOM_REDIRECT_URIS}" != *"$librechat_callback"* ]]; then
    export OAUTH_CUSTOM_REDIRECT_URIS="${OAUTH_CUSTOM_REDIRECT_URIS},${librechat_callback}"
  fi

  pushd "$GOOGLE_MCP_DIR" >/dev/null
  if [[ -x "start_server.sh" ]]; then
    # === VIVENTIUM START ===
    # Feature: Harden local Google MCP launcher handoff.
    # Purpose: Force the MCP child to bind to GOOGLE_MCP_PORT and detach cleanly from launcher shell state.
    # === VIVENTIUM END ===
    env PORT="$GOOGLE_MCP_PORT" \
      nohup bash start_server.sh >"$LOG_DIR/google_workspace_mcp.log" 2>&1 < /dev/null &
    GOOGLE_MCP_PID=$!
    GOOGLE_MCP_STARTED_BY_SCRIPT=true
    echo "$GOOGLE_MCP_PID" >"$GOOGLE_MCP_PID_FILE"
  elif [[ -f "main.py" ]]; then
    # Upstream layout fallback: start directly via uv when wrapper script is absent.
    env PORT="$GOOGLE_MCP_PORT" \
      nohup uv run main.py --transport streamable-http >"$LOG_DIR/google_workspace_mcp.log" 2>&1 < /dev/null &
    GOOGLE_MCP_PID=$!
    GOOGLE_MCP_STARTED_BY_SCRIPT=true
    echo "$GOOGLE_MCP_PID" >"$GOOGLE_MCP_PID_FILE"
    log_info "Google Workspace MCP started via uv run main.py fallback"
  else
    popd >/dev/null
    log_error "Google Workspace MCP startup script not found"
    return 1
  fi
  popd >/dev/null

  sleep 2
  if ! ps -p "$GOOGLE_MCP_PID" >/dev/null 2>&1; then
    log_error "Google Workspace MCP failed to start"
    tail -20 "$LOG_DIR/google_workspace_mcp.log" 2>/dev/null || true
    return 1
  fi

  wait_for_http "http://localhost:${GOOGLE_MCP_PORT}/health" "Google Workspace MCP" || true
  verify_google_oauth_redirect_registration || true
  if [[ "$SKIP_MCP_VERIFY" == "true" ]]; then
    log_info "Skipping Google Workspace MCP tools verification"
  elif verify_google_workspace_tools; then
    log_success "Google Workspace MCP tools available"
  else
    log_warn "Google Workspace MCP tools not verified yet"
  fi
  return 0
}

start_scheduling_mcp() {
  if [[ "$START_SCHEDULING_MCP" != "true" ]]; then
    log_info "Skipping Scheduling Cortex MCP startup"
    return 0
  fi

  if [[ ! -d "$SCHEDULING_MCP_DIR" ]]; then
    log_warn "Scheduling Cortex MCP directory not found: $SCHEDULING_MCP_DIR"
    return 1
  fi

  if port_in_use "$SCHEDULING_MCP_PORT"; then
    # === VIVENTIUM START ===
    # Feature: Restart Scheduling MCP on stack restart to refresh secrets.
    # === VIVENTIUM END ===
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "Scheduling Cortex MCP already running on port $SCHEDULING_MCP_PORT - restarting"
      stop_pid_file_scoped "$SCHEDULING_MCP_PID_FILE" "$SCHEDULING_MCP_DIR"
      kill_port_listeners "$SCHEDULING_MCP_PORT" "$SCHEDULING_MCP_DIR"
      if port_in_use "$SCHEDULING_MCP_PORT"; then
        log_warn "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT still in use (outside scope); skipping restart"
        return 1
      fi
    else
      log_success "Scheduling Cortex MCP already running on port $SCHEDULING_MCP_PORT"
      return 0
    fi
  fi

  if [[ -z "${SCHEDULER_LIBRECHAT_SECRET:-}" ]]; then
    log_warn "SCHEDULER_LIBRECHAT_SECRET not set - LibreChat dispatch will fail"
  fi

  log_info "Starting Scheduling Cortex MCP..."
  pushd "$SCHEDULING_MCP_DIR" >/dev/null

  if command -v uv >/dev/null 2>&1; then
    local deps_signature_file="$LOG_DIR/scheduling_cortex_mcp_deps.sha256"
    local deps_signature=""
    local cached_signature=""
    local needs_dependency_sync=true
    deps_signature="$("$PYTHON_BIN" - "$SCHEDULING_MCP_DIR" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
for rel_path in ("pyproject.toml", "uv.lock", "requirements.txt"):
    path = root / rel_path
    if not path.exists():
        continue
    digest.update(rel_path.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
)" || true
    if [[ -n "$deps_signature" && -x ".venv/bin/python" && -f "$deps_signature_file" ]]; then
      cached_signature="$(tr -d '\r\n' <"$deps_signature_file" 2>/dev/null || true)"
      if [[ "$cached_signature" == "$deps_signature" ]]; then
        needs_dependency_sync=false
      fi
    fi

    if [[ "$needs_dependency_sync" == "true" ]]; then
      log_info "Syncing Scheduling Cortex MCP dependencies..."
      if ! uv sync --frozen >"$LOG_DIR/scheduling_cortex_mcp_install.log" 2>&1; then
        log_error "Scheduling Cortex MCP dependency sync failed"
        tail -20 "$LOG_DIR/scheduling_cortex_mcp_install.log" 2>/dev/null || true
        popd >/dev/null
        return 1
      fi
      if [[ -n "$deps_signature" ]]; then
        printf '%s\n' "$deps_signature" >"$deps_signature_file"
      fi
    else
      log_success "Scheduling Cortex MCP dependencies already up to date"
    fi
    uv run python -m scheduling_cortex.server --transport streamable-http --port "$SCHEDULING_MCP_PORT" >"$LOG_DIR/scheduling_cortex_mcp.log" 2>&1 &
  else
    "$PYTHON_BIN" -m scheduling_cortex.server --transport streamable-http --port "$SCHEDULING_MCP_PORT" >"$LOG_DIR/scheduling_cortex_mcp.log" 2>&1 &
  fi

  SCHEDULING_MCP_PID=$!
  SCHEDULING_MCP_STARTED_BY_SCRIPT=true
  echo "$SCHEDULING_MCP_PID" >"$SCHEDULING_MCP_PID_FILE"

  popd >/dev/null

  sleep 2
  if ! ps -p "$SCHEDULING_MCP_PID" >/dev/null 2>&1; then
    log_error "Scheduling Cortex MCP failed to start"
    tail -20 "$LOG_DIR/scheduling_cortex_mcp.log" 2>/dev/null || true
    return 1
  fi

  log_success "Scheduling Cortex MCP started on port $SCHEDULING_MCP_PORT"
  return 0
}

glasshive_stack_ready() {
  curl -fsS "http://127.0.0.1:${GLASSHIVE_RUNTIME_PORT}/health" >/dev/null 2>&1 &&
    curl -fsS "http://127.0.0.1:${GLASSHIVE_UI_PORT}/" >/dev/null 2>&1
}

start_glasshive() {
  if [[ "$START_GLASSHIVE" != "true" ]]; then
    log_info "Skipping GlassHive startup"
    return 0
  fi

  if [[ ! -d "$GLASSHIVE_RUNTIME_DIR" ]]; then
    log_warn "GlassHive runtime directory not found: $GLASSHIVE_RUNTIME_DIR"
    return 1
  fi

  local ports_in_use=false
  if port_in_use "$GLASSHIVE_RUNTIME_PORT" || port_in_use "$GLASSHIVE_MCP_PORT" || port_in_use "$GLASSHIVE_UI_PORT"; then
    ports_in_use=true
  fi

  if [[ "$ports_in_use" == "true" ]]; then
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "GlassHive services already running - restarting"
      stop_pid_file_scoped "$GLASSHIVE_RUNTIME_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
      stop_pid_file_scoped "$GLASSHIVE_MCP_PID_FILE" "$GLASSHIVE_RUNTIME_DIR"
      stop_pid_file_scoped "$GLASSHIVE_UI_PID_FILE" "$GLASSHIVE_UI_DIR"
      kill_port_listeners "$GLASSHIVE_RUNTIME_PORT" "$GLASSHIVE_RUNTIME_DIR"
      kill_port_listeners "$GLASSHIVE_MCP_PORT" "$GLASSHIVE_RUNTIME_DIR"
      kill_port_listeners "$GLASSHIVE_UI_PORT" "$GLASSHIVE_UI_DIR"
    elif glasshive_stack_ready; then
      log_success "GlassHive already running on ports $GLASSHIVE_RUNTIME_PORT/$GLASSHIVE_MCP_PORT/$GLASSHIVE_UI_PORT"
      return 0
    else
      log_warn "GlassHive ports are in use but health checks failed; leaving existing services untouched"
      return 1
    fi
  fi

  if ! command -v uv >/dev/null 2>&1; then
    log_error "uv not found (required for GlassHive)"
    return 1
  fi

  log_info "Starting GlassHive runtime stack..."
  pushd "$GLASSHIVE_RUNTIME_DIR" >/dev/null
  if ! uv sync --frozen >"$LOG_DIR/glasshive_runtime_install.log" 2>&1; then
    log_error "GlassHive runtime dependency sync failed"
    tail -20 "$LOG_DIR/glasshive_runtime_install.log" 2>/dev/null || true
    popd >/dev/null
    return 1
  fi

  uv run uvicorn workers_projects_runtime.api:app --host 127.0.0.1 --port "$GLASSHIVE_RUNTIME_PORT" >"$LOG_DIR/glasshive_runtime.log" 2>&1 &
  GLASSHIVE_RUNTIME_PID=$!
  GLASSHIVE_STARTED_BY_SCRIPT=true
  echo "$GLASSHIVE_RUNTIME_PID" >"$GLASSHIVE_RUNTIME_PID_FILE"

  uv run python -m workers_projects_runtime.mcp_server --transport streamable-http --host 127.0.0.1 --port "$GLASSHIVE_MCP_PORT" >"$LOG_DIR/glasshive_mcp.log" 2>&1 &
  GLASSHIVE_MCP_PID=$!
  GLASSHIVE_STARTED_BY_SCRIPT=true
  echo "$GLASSHIVE_MCP_PID" >"$GLASSHIVE_MCP_PID_FILE"
  popd >/dev/null

  if [[ -d "$GLASSHIVE_UI_DIR" ]]; then
    pushd "$GLASSHIVE_UI_DIR" >/dev/null
    if ! uv sync --frozen >"$LOG_DIR/glasshive_ui_install.log" 2>&1; then
      log_error "GlassHive UI dependency sync failed"
      tail -20 "$LOG_DIR/glasshive_ui_install.log" 2>/dev/null || true
      popd >/dev/null
      return 1
    fi
    uv run uvicorn glass_drive_ui.server:app --host 127.0.0.1 --port "$GLASSHIVE_UI_PORT" >"$LOG_DIR/glasshive_ui.log" 2>&1 &
    GLASSHIVE_UI_PID=$!
    GLASSHIVE_STARTED_BY_SCRIPT=true
    echo "$GLASSHIVE_UI_PID" >"$GLASSHIVE_UI_PID_FILE"
    popd >/dev/null
  fi

  sleep 3

  if ! ps -p "$GLASSHIVE_RUNTIME_PID" >/dev/null 2>&1; then
    log_error "GlassHive runtime failed to start"
    tail -20 "$LOG_DIR/glasshive_runtime.log" 2>/dev/null || true
    return 1
  fi
  if ! ps -p "$GLASSHIVE_MCP_PID" >/dev/null 2>&1; then
    log_error "GlassHive MCP failed to start"
    tail -20 "$LOG_DIR/glasshive_mcp.log" 2>/dev/null || true
    return 1
  fi
  if [[ -n "${GLASSHIVE_UI_PID:-}" ]] && ! ps -p "$GLASSHIVE_UI_PID" >/dev/null 2>&1; then
    log_error "GlassHive UI failed to start"
    tail -20 "$LOG_DIR/glasshive_ui.log" 2>/dev/null || true
    return 1
  fi

  if ! glasshive_stack_ready; then
    log_warn "GlassHive processes started but health checks are not fully ready yet"
  else
    log_success "GlassHive started on ports $GLASSHIVE_RUNTIME_PORT/$GLASSHIVE_MCP_PORT/$GLASSHIVE_UI_PORT"
  fi
  return 0
}

start_ms365_mcp() {
  if [[ "$START_MS365_MCP" != "true" ]]; then
    log_info "Skipping MS365 MCP startup"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for MS365 MCP)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "MS365 MCP"; then
    return 1
  fi

  local compose_file="$ROOT_DIR/docker/ms365-mcp/docker-compose.yml"
  local startup_script="$LEGACY_V0_3_DIR/scripts/ms365/start_ms365_mcp_http.sh"

  if [[ ! -f "$compose_file" ]]; then
    log_warn "MS365 MCP compose file not found: $compose_file"
    return 1
  fi

  if load_ms365_credentials; then
    log_success "MS365 credentials loaded"
    export MS365_MCP_CLIENT_ID MS365_MCP_TENANT_ID MS365_MCP_CLIENT_SECRET MS365_BUSINESS_EMAIL
  else
    log_warn "MS365 credentials not found - OAuth will fail until configured"
  fi

  local base_port="$MS365_MCP_PORT"
  local ms365_port_in_use=false
  if port_in_use "$base_port"; then
    ms365_port_in_use=true
    if ms365_http_ping "http://localhost:${base_port}/mcp"; then
      if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
        log_warn "MS365 MCP already running on port $base_port - restarting"
        local ms365_compose="$ROOT_DIR/docker/ms365-mcp/docker-compose.yml"
        if [[ -f "$ms365_compose" ]]; then
          docker compose -f "$ms365_compose" down >/dev/null 2>&1 || true
        fi
      else
        MS365_MCP_PORT="$base_port"
        export MS365_MCP_PORT
        export MS365_MCP_TRANSPORT="streamable-http"
        export MS365_MCP_SERVER_URL="http://localhost:${MS365_MCP_PORT}/mcp"
        export MS365_MCP_AUTH_URL="http://localhost:${MS365_MCP_PORT}/authorize"
        export MS365_MCP_TOKEN_URL="http://localhost:${MS365_MCP_PORT}/token"
        write_ms365_runtime_exports
        log_info "MS365 MCP already running on port $base_port"
        return 0
      fi
    else
      if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
        log_warn "Port $base_port is in use; attempting restart on the same port"
        kill_port_listeners "$base_port" "$VIVENTIUM_CORE_DIR"
      else
        local new_port
        new_port=$(find_free_port "$base_port")
        log_warn "Port $base_port in use - using $new_port for MS365 MCP"
        base_port="$new_port"
      fi
    fi
  fi

  if [[ "$RESTART_DOCKER_SERVICES" == "true" && "$ms365_port_in_use" == "true" ]]; then
    if port_in_use "$base_port"; then
      if ! ms365_port_listener_is_viventium_owned "$base_port"; then
        log_warn "MS365 MCP port $base_port is occupied by a non-Viventium listener; reclaiming the port for Viventium"
        kill_port_listeners "$base_port"
      elif ms365_http_ping "http://localhost:${base_port}/mcp"; then
        MS365_MCP_PORT="$base_port"
        export MS365_MCP_PORT
        export MS365_MCP_TRANSPORT="streamable-http"
        export MS365_MCP_SERVER_URL="http://localhost:${MS365_MCP_PORT}/mcp"
        export MS365_MCP_AUTH_URL="http://localhost:${MS365_MCP_PORT}/authorize"
        export MS365_MCP_TOKEN_URL="http://localhost:${MS365_MCP_PORT}/token"
        write_ms365_runtime_exports
        log_warn "MS365 MCP still reachable on port $base_port; using existing service"
        return 0
      fi
      log_error "Port $base_port is still in use; skipping MS365 MCP startup"
      return 1
    fi
  fi

  MS365_MCP_PORT="$base_port"
  export MS365_MCP_PORT
  export MS365_MCP_TRANSPORT="streamable-http"
  export MS365_MCP_SERVER_URL="http://localhost:${MS365_MCP_PORT}/mcp"
  export MS365_MCP_AUTH_URL="http://localhost:${MS365_MCP_PORT}/authorize"
  export MS365_MCP_TOKEN_URL="http://localhost:${MS365_MCP_PORT}/token"
  write_ms365_runtime_exports
  local ms365_compose_up_timeout="${VIVENTIUM_MS365_MCP_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS:-1800}"

  if ! ms365_http_ping "$MS365_MCP_SERVER_URL"; then
    log_info "Starting MS365 MCP (Docker)..."
    if [[ -f "$startup_script" && -x "$startup_script" ]]; then
      if [[ "${MS365_MCP_FORCE_BUILD:-0}" = "1" ]]; then
        if ! VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS="$ms365_compose_up_timeout" "$startup_script" --detached --build; then
          log_error "MS365 MCP startup script failed"
          return 1
        fi
      else
        if ! VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS="$ms365_compose_up_timeout" "$startup_script" --detached; then
          log_error "MS365 MCP startup script failed"
          return 1
        fi
      fi
    else
      if [[ "${MS365_MCP_FORCE_BUILD:-0}" = "1" ]]; then
        if ! VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS="$ms365_compose_up_timeout" docker compose -f "$compose_file" up -d --build; then
          log_error "MS365 MCP docker compose failed"
          return 1
        fi
      else
        if ! VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS="$ms365_compose_up_timeout" docker compose -f "$compose_file" up -d; then
          log_error "MS365 MCP docker compose failed"
          return 1
        fi
      fi
    fi
    MS365_STARTED_BY_SCRIPT=true
  fi

  if ms365_http_ping "$MS365_MCP_SERVER_URL"; then
    log_success "MS365 MCP reachable at $MS365_MCP_SERVER_URL"
  else
    log_warn "MS365 MCP did not respond yet at $MS365_MCP_SERVER_URL"
  fi
  return 0
}

rag_api_http_ping() {
  local port="${1:-$VIVENTIUM_RAG_API_PORT}"
  curl -fsS --max-time 3 "http://localhost:${port}/health" >/dev/null 2>&1
}

# === VIVENTIUM START ===
# Feature: Ollama embeddings runtime readiness for local RAG.
# Purpose:
# - Keep the local-first embeddings default honest on fresh installs.
# - Start the local Ollama service when Conversation Recall depends on it instead of letting the
#   RAG sidecar fail later with hidden runtime drift.
# Added: 2026-04-09
# === VIVENTIUM END ===
ollama_embeddings_enabled_for_rag() {
  [[ "${EMBEDDINGS_PROVIDER:-}" == "ollama" ]]
}

ollama_host_base_url() {
  local base_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
  base_url="${base_url%/}"
  base_url="${base_url/host.docker.internal/localhost}"
  printf '%s\n' "$base_url"
}

ollama_http_ping() {
  local base_url="${1:-$(ollama_host_base_url)}"
  curl -fsS --max-time 3 "${base_url%/}/api/tags" >/dev/null 2>&1
}

ollama_tags_json() {
  local base_url="${1:-$(ollama_host_base_url)}"
  curl -fsS --max-time 10 "${base_url%/}/api/tags"
}

ollama_embedding_model_name() {
  local model="${EMBEDDINGS_MODEL:-qwen3-embedding:0.6b}"
  printf '%s\n' "$model"
}

ollama_model_present() {
  local base_url="${1:-$(ollama_host_base_url)}"
  local model="${2:-$(ollama_embedding_model_name)}"
  local tags_json=""

  if ! tags_json="$(ollama_tags_json "$base_url" 2>/dev/null)"; then
    return 1
  fi

  OLLAMA_TAGS_JSON="$tags_json" "$PYTHON_BIN" - "$model" <<'PY'
import json
import os
import sys

target = str(sys.argv[1] if len(sys.argv) > 1 else "").strip()
if not target:
    raise SystemExit(1)

targets = {target}
if ":" not in target:
    targets.add(f"{target}:latest")
elif target.endswith(":latest"):
    targets.add(target.rsplit(":", 1)[0])

try:
    payload = json.loads(os.environ.get("OLLAMA_TAGS_JSON", "") or "{}")
except json.JSONDecodeError:
    raise SystemExit(1)

for entry in payload.get("models") or []:
    name = str(entry.get("name") or entry.get("model") or "").strip()
    if name in targets:
        raise SystemExit(0)

raise SystemExit(1)
PY
}

ollama_pull_model() {
  local base_url="${1:-$(ollama_host_base_url)}"
  local model="${2:-$(ollama_embedding_model_name)}"
  local payload=""
  payload="$("$PYTHON_BIN" - "$model" <<'PY'
import json
import sys

model = sys.argv[1]
print(json.dumps({"name": model, "stream": False}))
PY
)"

  curl -fsS -H 'Content-Type: application/json' --data "$payload" "${base_url%/}/api/pull" >/dev/null
}

ensure_ollama_for_rag() {
  if ! ollama_embeddings_enabled_for_rag; then
    return 0
  fi

  local host_url=""
  host_url="$(ollama_host_base_url)"

  if ollama_http_ping "$host_url"; then
    log_success "Ollama embeddings runtime ready at $host_url"
    return 0
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    log_error "Ollama is required for the configured local embeddings runtime but is not installed"
    return 1
  fi

  if command -v brew >/dev/null 2>&1 && brew list ollama >/dev/null 2>&1; then
    log_info "Starting Ollama embeddings runtime..."
    HOMEBREW_NO_AUTO_UPDATE=1 brew services start ollama >/dev/null 2>&1 || true
  fi

  if wait_for_http "${host_url%/}/api/tags" "Ollama embeddings runtime" 5; then
    return 0
  fi

  log_error "Ollama embeddings runtime is not reachable at ${host_url}. Start it with 'brew services start ollama' or 'ollama serve' and retry."
  return 1
}

ensure_ollama_embedding_model_for_rag() {
  if ! ollama_embeddings_enabled_for_rag; then
    return 0
  fi

  local host_url=""
  local model=""
  host_url="$(ollama_host_base_url)"
  model="$(ollama_embedding_model_name)"

  if ollama_model_present "$host_url" "$model"; then
    log_success "Ollama embedding model ready: $model"
    return 0
  fi

  log_info "Pulling Ollama embedding model $model from $host_url..."
  if ! ollama_pull_model "$host_url" "$model"; then
    log_error "Failed to pull Ollama embedding model $model from $host_url"
    return 1
  fi

  if ollama_model_present "$host_url" "$model"; then
    log_success "Ollama embedding model ready: $model"
    return 0
  fi

  log_error "Ollama embedding model $model is still unavailable after pull"
  return 1
}

start_rag_api() {
  if [[ "$START_RAG_API" != "true" || "$SKIP_LIBRECHAT" == "true" ]]; then
    log_info "Skipping local RAG API startup"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for local RAG API)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "local RAG API"; then
    return 1
  fi
  if ! ensure_ollama_for_rag; then
    return 1
  fi
  if ! ensure_ollama_embedding_model_for_rag; then
    return 1
  fi

  local compose_file="$LIBRECHAT_DIR/rag.yml"
  if [[ ! -f "$compose_file" ]]; then
    log_warn "Local RAG compose file not found: $compose_file"
    return 1
  fi

  local rag_port="$VIVENTIUM_RAG_API_PORT"
  if port_in_use "$rag_port"; then
    if rag_api_http_ping "$rag_port"; then
      if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
        log_warn "Local RAG API already running on port $rag_port - restarting"
        (
          cd "$LIBRECHAT_DIR"
          RAG_PORT="$rag_port" docker compose -f "$compose_file" down >/dev/null 2>&1 || true
        )
      else
        export RAG_API_URL="http://localhost:${rag_port}"
        log_success "Local RAG API already running at $RAG_API_URL"
        return 0
      fi
    else
      if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
        log_warn "RAG API port $rag_port is in use; attempting restart on the same port"
        kill_port_listeners "$rag_port" "$LIBRECHAT_DIR"
      else
        log_warn "Port $rag_port is in use; skipping local RAG API startup"
        return 1
      fi
    fi
  fi

  if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
    if port_in_use "$rag_port"; then
      if rag_api_http_ping "$rag_port"; then
        export RAG_API_URL="http://localhost:${rag_port}"
        log_warn "Local RAG API still reachable on port $rag_port; using existing service"
        return 0
      fi
      log_error "RAG API port $rag_port is still in use; skipping startup"
      return 1
    fi
  fi

  local rag_compose_up_timeout="${VIVENTIUM_RAG_API_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS:-1800}"
  local quick_probe_retries="${VIVENTIUM_RAG_API_BOOT_PROBE_RETRIES:-5}"
  if ! [[ "$quick_probe_retries" =~ ^[0-9]+$ ]] || [[ "$quick_probe_retries" -lt 1 ]]; then
    quick_probe_retries=5
  fi

  log_info "Starting local RAG API (Docker)..."
  local rag_compose_status=0
  (
    cd "$LIBRECHAT_DIR"
    VIVENTIUM_DOCKER_COMPOSE_UP_TIMEOUT_SECONDS="$rag_compose_up_timeout" \
      RAG_PORT="$rag_port" \
      docker compose -f "$compose_file" up -d
  ) || rag_compose_status=$?
  RAG_API_STARTED_BY_SCRIPT=true

  if [[ "$rag_compose_status" -ne 0 ]]; then
    log_warn "Local RAG API compose start exited with status ${rag_compose_status}; checking whether the service is still converging"
  fi

  if wait_for_http "http://localhost:${rag_port}/health" "RAG API" "$quick_probe_retries"; then
    export RAG_API_URL="http://localhost:${rag_port}"
    return 0
  fi

  if rag_api_http_ping "$rag_port"; then
    export RAG_API_URL="http://localhost:${rag_port}"
    return 0
  fi

  log_warn "RAG API bootstrap still in progress; continuing startup"
  return 1
}

# === VIVENTIUM START ===
# Feature: Code Interpreter runtime image preflight.
# Purpose: Prevent execute_code failures ("No Docker image found for language 'py'") on fresh installs.
# === VIVENTIUM END ===
ensure_code_interpreter_runtime_image() {
  local registry="${DOCKER_IMAGE_REGISTRY:-ghcr.io/usnavy13/librecodeinterpreter}"
  local tag="${DOCKER_IMAGE_TAG:-latest}"
  local runtime_image="${registry%/}/python:${tag}"
  local build_script="$CODE_INTERPRETER_DIR/docker/build-images.sh"
  local build_log="$LOG_DIR/code_interpreter_python_build.log"

  if docker image inspect "$runtime_image" >/dev/null 2>&1; then
    return 0
  fi

  log_warn "Code Interpreter runtime image missing: $runtime_image"
  log_info "Pulling Code Interpreter Python runtime image..."
  if docker pull "$runtime_image" >/dev/null 2>&1; then
    log_success "Code Interpreter runtime image ready: $runtime_image"
    return 0
  fi

  if [[ -f "$build_script" ]]; then
    log_warn "Falling back to local Code Interpreter Python image build"
    if (
      cd "$CODE_INTERPRETER_DIR/docker" &&
        REGISTRY="${registry%/}" VERSION="$tag" bash "./$(basename "$build_script")" -l python
    ) >"$build_log" 2>&1; then
      log_success "Code Interpreter Python runtime image built locally: $runtime_image"
      return 0
    fi
    log_warn "Local Code Interpreter Python image build failed; see $build_log"
  fi

  log_warn "Failed to pull runtime image $runtime_image (Python execute_code may fail)"
  return 1
}

start_code_interpreter() {
  if [[ "$START_CODE_INTERPRETER" != "true" ]]; then
    log_info "Skipping Code Interpreter startup"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for Code Interpreter)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "Code Interpreter"; then
    return 1
  fi

  if [[ ! -d "$CODE_INTERPRETER_DIR" ]]; then
    log_warn "Code Interpreter directory not found: $CODE_INTERPRETER_DIR"
    return 1
  fi

  if ! ensure_code_interpreter_env; then
    return 1
  fi

  local compose_file="$CODE_INTERPRETER_DIR/docker-compose.ghcr.yml"
  if [[ ! -f "$compose_file" ]]; then
    compose_file="$CODE_INTERPRETER_DIR/docker-compose.yml"
  fi
  if [[ ! -f "$compose_file" ]]; then
    log_warn "Code Interpreter compose file not found in $CODE_INTERPRETER_DIR"
    return 1
  fi

  local existing_container
  existing_container=$(docker ps -q --filter "name=^/code-interpreter-api$" 2>/dev/null | head -1)
  if [[ -n "$existing_container" ]]; then
    local stack_label
    stack_label=$(docker inspect -f '{{ index .Config.Labels "viventium.stack" }}' "$existing_container" 2>/dev/null || true)
    if [[ "$stack_label" != "viventium_v0_4" && "$stack_label" != "viventium_lc_livekit" ]]; then
      log_warn "Found code-interpreter-api container not owned by Viventium; leaving it untouched"
      local host_port
      host_port=$(docker port "$existing_container" 8000/tcp 2>/dev/null | head -1 | awk -F: '{print $2}')
      if [[ -n "$host_port" ]]; then
        log_warn "External code interpreter maps to localhost:${host_port}"
      fi
      if code_interpreter_health; then
        log_success "Code Interpreter reachable at $LIBRECHAT_CODE_BASEURL"
        ensure_code_interpreter_runtime_image || true
        return 0
      fi
      if [[ "$CODE_BASEURL_WAS_DEFAULT" == "true" ]]; then
        log_warn "Set LIBRECHAT_CODE_BASEURL to the existing container host port or stop it"
      fi
      return 1
    fi

    local host_port
    host_port=$(docker port "$existing_container" 8000/tcp 2>/dev/null | head -1 | awk -F: '{print $2}')
    if [[ -n "$host_port" ]]; then
      local base_host
      base_host="${LIBRECHAT_CODE_BASEURL#*://}"
      base_host="${base_host%%/*}"
      base_host="${base_host%%:*}"
      if [[ "$CODE_BASEURL_WAS_DEFAULT" == "true" || "$base_host" == "localhost" || "$base_host" == "127.0.0.1" ]]; then
        CODE_INTERPRETER_PORT="$host_port"
        export LIBRECHAT_CODE_BASEURL="http://localhost:${CODE_INTERPRETER_PORT}"
      fi
    fi
    if code_interpreter_health; then
      log_success "Code Interpreter already running on port $CODE_INTERPRETER_PORT"
      ensure_code_interpreter_runtime_image || true
      return 0
    fi
    if [[ "$RESTART_DOCKER_SERVICES" != "true" ]]; then
      log_warn "Code Interpreter container found but health check failed"
      return 1
    fi
    log_warn "Restarting Code Interpreter container"
    docker rm -f "$existing_container" >/dev/null 2>&1 || true
  fi

  if [[ "$SKIP_DOCKER" != "true" ]]; then
    cleanup_orphaned_code_interpreter_exec_containers
  fi

  if port_in_use "$CODE_INTERPRETER_PORT"; then
    if [[ "$RESTART_DOCKER_SERVICES" == "true" && "$CODE_INTERPRETER_PORT" -eq 8001 ]]; then
      local fallback_port
      fallback_port=$(find_free_port "$CODE_INTERPRETER_PORT" "$GOOGLE_MCP_PORT" "$MS365_MCP_CALLBACK_PORT")
      log_warn "Code Interpreter port $CODE_INTERPRETER_PORT in use; using $fallback_port for this run"
      CODE_INTERPRETER_PORT="$fallback_port"
      export LIBRECHAT_CODE_BASEURL="http://localhost:${CODE_INTERPRETER_PORT}"
    else
      log_warn "Code Interpreter port $CODE_INTERPRETER_PORT in use; skipping startup"
      return 1
    fi
  fi

  local quick_probe_retries="${CODE_INTERPRETER_BOOT_PROBE_RETRIES:-5}"
  if ! [[ "$quick_probe_retries" =~ ^[0-9]+$ ]] || [[ "$quick_probe_retries" -lt 1 ]]; then
    quick_probe_retries=5
  fi
  local compose_log="$LOG_DIR/code_interpreter_compose.log"
  : >"$compose_log"

  log_info "Starting Code Interpreter (Docker)..."
  (
    cd "$CODE_INTERPRETER_DIR"
    API_PORT="$CODE_INTERPRETER_PORT" docker compose -f "$compose_file" up -d >>"$compose_log" 2>&1
  ) &
  local compose_pid=$!
  CODE_INTERPRETER_STARTED_BY_SCRIPT=true

  if wait_for_http "${LIBRECHAT_CODE_BASEURL%/}/health" "Code Interpreter" "$quick_probe_retries"; then
    ensure_code_interpreter_runtime_image || true
    return 0
  fi

  if ps -p "$compose_pid" >/dev/null 2>&1; then
    log_warn "Code Interpreter bootstrap still in progress; continuing startup. See $compose_log"
    return 1
  fi

  if code_interpreter_health; then
    log_success "Code Interpreter reachable at $LIBRECHAT_CODE_BASEURL"
    ensure_code_interpreter_runtime_image || true
    return 0
  fi

  log_warn "Code Interpreter did not respond yet at ${LIBRECHAT_CODE_BASEURL%/}/health"
  return 1
}

# === VIVENTIUM START ===
# Feature: Skyvern Browser Agent startup (Docker).
# Purpose: Bring up Skyvern API/UI alongside LibreChat with an optional skip flag.
# === VIVENTIUM END ===
cleanup_skyvern_containers() {
  local skyvern_script="$ROOT_DIR/viventium-skyvern-start.sh"
  if [[ -x "$skyvern_script" ]]; then
    "$skyvern_script" stop >/dev/null 2>&1 || true
  fi
  if docker_daemon_ready; then
    local skyvern_project_containers
    skyvern_project_containers=$(docker ps -aq --filter "label=com.docker.compose.project=skyvern" 2>/dev/null || true)
    if [[ -n "$skyvern_project_containers" ]]; then
      docker rm -f $skyvern_project_containers >/dev/null 2>&1 || true
    fi
  fi
}

start_skyvern() {
  if [[ "$START_SKYVERN" != "true" ]]; then
    log_info "Skipping Skyvern startup"
    return 0
  fi
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    log_info "Skipping Skyvern startup (SKIP_DOCKER=true)"
    return 0
  fi

  if ! ensure_skyvern_env; then
    return 1
  fi

  local subscription_auth_enabled=false
  case "${VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH:-}" in
    1|true|TRUE|yes|YES|on|ON) subscription_auth_enabled=true ;;
  esac
  if [[ "$subscription_auth_enabled" == "true" ]]; then
    if ! ensure_mongodb_ready; then
      log_warn "MongoDB not ready; Skyvern connected-account bridge may fall back to API key auth"
    fi
  fi

  local skyvern_script="$ROOT_DIR/viventium-skyvern-start.sh"
  if [[ ! -x "$skyvern_script" ]]; then
    log_warn "Skyvern start script not found or not executable: $skyvern_script"
    return 1
  fi

  if skyvern_http_ping; then
    log_success "Skyvern API reachable at $SKYVERN_BASE_URL"
    return 0
  fi

  local quick_probe_retries="${SKYVERN_BOOT_PROBE_RETRIES:-5}"
  if ! [[ "$quick_probe_retries" =~ ^[0-9]+$ ]] || [[ "$quick_probe_retries" -lt 1 ]]; then
    quick_probe_retries=5
  fi
  local skyvern_log="$LOG_DIR/skyvern_start.log"
  : >"$skyvern_log"

  log_info "Starting Skyvern Browser Agent..."
  "$skyvern_script" start >>"$skyvern_log" 2>&1 &
  local skyvern_pid=$!
  SKYVERN_STARTED_BY_SCRIPT=true

  local attempts=0
  local max_attempts="$quick_probe_retries"
  while [[ "$attempts" -lt "$max_attempts" ]]; do
    if skyvern_http_ping; then
      log_success "Skyvern API reachable at $SKYVERN_BASE_URL"
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 1
  done

  if ps -p "$skyvern_pid" >/dev/null 2>&1; then
    log_warn "Skyvern bootstrap still in progress; continuing startup. See $skyvern_log"
    return 1
  fi

  if skyvern_http_ping; then
    log_success "Skyvern API reachable at $SKYVERN_BASE_URL"
    return 0
  fi

  log_warn "Skyvern API did not respond yet at $SKYVERN_BASE_URL (checked health/docs/openapi); cleaning up Skyvern containers"
  cleanup_skyvern_containers
  return 1
}

install_docker_prewarm_pid_file() {
  local service="$1"
  local app_support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
  printf '%s\n' "${app_support_dir}/state/install/docker-prewarm-${service}.pid"
}

wait_for_install_docker_prewarm() {
  local service="$1"
  local label="$2"
  local pid_file=""
  local pid=""

  pid_file="$(install_docker_prewarm_pid_file "$service")"
  [[ -f "$pid_file" ]] || return 0

  pid="$(tr -d '\r\n' <"$pid_file" 2>/dev/null || true)"
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    rm -f "$pid_file"
    return 0
  fi
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$pid_file"
    return 0
  fi

  log_info "${label} image warmup already running from preflight; waiting for it to finish..."
  while kill -0 "$pid" >/dev/null 2>&1; do
    sleep 1
  done
  rm -f "$pid_file"
  return 0
}

start_firecrawl() {
  if [[ "$START_FIRECRAWL" != "true" ]]; then
    log_info "Skipping Firecrawl startup"
    return 0
  fi
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    log_info "Skipping Firecrawl startup (SKIP_DOCKER=true)"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for Firecrawl)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "Firecrawl"; then
    return 1
  fi

  # VIVENTIUM START: Use v0.4 Firecrawl compose.
  local compose_file="$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/firecrawl/docker-compose.yml"
  # VIVENTIUM END
  if [[ ! -f "$compose_file" ]]; then
    log_warn "Firecrawl compose file not found: $compose_file"
    return 1
  fi

  if ! wait_for_install_docker_prewarm "firecrawl" "Firecrawl"; then
    log_warn "Firecrawl prewarm did not finish cleanly; continuing with normal startup"
  fi

  if port_in_use "$FIRECRAWL_PORT"; then
    if firecrawl_http_ping; then
      log_success "Firecrawl already running at $FIRECRAWL_BASE_URL"
      return 0
    fi
    if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
      log_warn "Firecrawl port $FIRECRAWL_PORT in use but not responding - restarting"
      docker compose -f "$compose_file" down >/dev/null 2>&1 || true
    else
      log_warn "Firecrawl port $FIRECRAWL_PORT in use - skipping startup"
      return 1
    fi
  fi

  log_info "Starting Firecrawl (Docker)..."
  FIRECRAWL_PORT="$FIRECRAWL_PORT" docker compose -f "$compose_file" up -d
  FIRECRAWL_STARTED_BY_SCRIPT=true

  for _ in $(seq 1 20); do
    if firecrawl_http_ping; then
      log_success "Firecrawl reachable at $FIRECRAWL_BASE_URL"
      return 0
    fi
    sleep 1
  done

  log_warn "Firecrawl did not respond yet at $FIRECRAWL_BASE_URL"
  return 1
}

start_searxng() {
  if [[ "$START_SEARXNG" != "true" ]]; then
    log_info "Skipping SearxNG startup"
    return 0
  fi
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    log_info "Skipping SearxNG startup (SKIP_DOCKER=true)"
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found (required for SearxNG)"
    return 1
  fi
  if ! ensure_docker_daemon_for_service "SearxNG"; then
    return 1
  fi

  # VIVENTIUM START: Use v0.4 SearxNG compose.
  local compose_file="$VIVENTIUM_CORE_DIR/viventium_v0_4/docker/searxng/docker-compose.yml"
  # VIVENTIUM END
  if [[ ! -f "$compose_file" ]]; then
    log_warn "SearxNG compose file not found: $compose_file"
    return 1
  fi

  if ! wait_for_install_docker_prewarm "searxng" "SearxNG"; then
    log_warn "SearxNG prewarm did not finish cleanly; continuing with normal startup"
  fi

  if port_in_use "$SEARXNG_PORT"; then
    if searxng_http_ping; then
      log_success "SearxNG already running at $SEARXNG_INSTANCE_URL"
      return 0
    fi
    if [[ "$RESTART_DOCKER_SERVICES" == "true" ]]; then
      log_warn "SearxNG port $SEARXNG_PORT in use but not responding - restarting"
      docker compose -f "$compose_file" down >/dev/null 2>&1 || true
    else
      log_warn "SearxNG port $SEARXNG_PORT in use - skipping startup"
      return 1
    fi
  fi

  log_info "Starting SearxNG (Docker)..."
  SEARXNG_PORT="$SEARXNG_PORT" docker compose -f "$compose_file" up -d
  SEARXNG_STARTED_BY_SCRIPT=true

  local ready_retries="${VIVENTIUM_SEARXNG_READY_RETRIES:-60}"
  if ! [[ "$ready_retries" =~ ^[0-9]+$ ]] || [[ "$ready_retries" -lt 1 ]]; then
    ready_retries=60
  fi

  for _ in $(seq 1 "$ready_retries"); do
    if searxng_http_ping; then
      log_success "SearxNG reachable at $SEARXNG_INSTANCE_URL"
      return 0
    fi
    sleep 1
  done

  log_warn "SearxNG did not respond yet at $SEARXNG_INSTANCE_URL"
  return 1
}

start_ms365_oauth_callback() {
  if [[ "$START_V1_AGENT" != "true" ]]; then
    return 0
  fi

  if [[ ! -d "$LEGACY_V0_3_DIR/viventium_v1" ]]; then
    log_warn "V1 backend not found; skipping MS365 OAuth callback server"
    return 1
  fi

  local callback_port="$MS365_MCP_CALLBACK_PORT"
  if port_in_use "$callback_port"; then
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "MS365 callback port $callback_port in use - restarting callback server"
      kill_port_listeners "$callback_port" "$VIVENTIUM_CORE_DIR"
    elif [[ "${MS365_MCP_ALLOW_DYNAMIC_CALLBACK_PORT:-0}" = "1" ]]; then
      local new_port
      new_port=$(find_free_port "$callback_port")
      log_warn "MS365 callback port $callback_port in use - using $new_port"
      callback_port="$new_port"
    else
      log_warn "MS365 callback port $callback_port already in use - skipping callback server"
      return 0
    fi
  fi

  MS365_MCP_CALLBACK_PORT="$callback_port"
  export MS365_MCP_CALLBACK_PORT
  export MS365_OAUTH_CALLBACK_URL="${MS365_OAUTH_CALLBACK_URL:-http://localhost:${MS365_MCP_CALLBACK_PORT}/oauth/callback}"
  if [[ -z "${MS365_MCP_REDIRECT_URI:-}" ]]; then
    export MS365_MCP_REDIRECT_URI="$MS365_OAUTH_CALLBACK_URL"
  fi

  (
    export PYTHONPATH="$LEGACY_V0_3_DIR/viventium_v1:${PYTHONPATH:-}"
    if command -v uv >/dev/null 2>&1 && [[ -d "$V1_AGENT_DIR" ]]; then
      cd "$V1_AGENT_DIR"
      uv run -m backend.brain.tools.mcp.clients.ms365_oauth_callback --port "$MS365_MCP_CALLBACK_PORT"
    else
      cd "$LEGACY_V0_3_DIR/viventium_v1"
      "$PYTHON_BIN" -m backend.brain.tools.mcp.clients.ms365_oauth_callback --port "$MS365_MCP_CALLBACK_PORT"
    fi
  ) >"$LOG_DIR/ms365_oauth_callback.log" 2>&1 &
  MS365_MCP_CALLBACK_PID=$!
  MS365_CALLBACK_STARTED_BY_SCRIPT=true
  sleep 2
  if ! ps -p "$MS365_MCP_CALLBACK_PID" >/dev/null 2>&1; then
    log_warn "MS365 OAuth callback server failed to start (see $LOG_DIR/ms365_oauth_callback.log)"
    return 1
  fi
  log_success "MS365 OAuth callback server started (PID: $MS365_MCP_CALLBACK_PID)"
}

start_v1_agent() {
  if [[ "$START_V1_AGENT" != "true" ]]; then
    log_info "Skipping V1 agent startup"
    return 0
  fi

  if [[ ! -d "$V1_AGENT_DIR" ]]; then
    log_warn "V1 agent directory not found: $V1_AGENT_DIR"
    return 1
  fi

  local existing_agent_pid
  existing_agent_pid=$(pgrep -f "frontal_cortex.agent start" 2>/dev/null || true)
  if [[ -n "$existing_agent_pid" ]]; then
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "Stopping existing V1 agent (PID: $existing_agent_pid)"
      kill_pids "$existing_agent_pid"
    else
      log_success "V1 agent already running (PID: $existing_agent_pid)"
      return 0
    fi
  fi

  require_cmd uv

  if [[ "$SKIP_V1_SYNC" != "true" ]]; then
    log_info "Syncing V1 agent dependencies..."
    if ! (cd "$V1_AGENT_DIR" && uv sync 2>&1 | tee "$LOG_DIR/v1_uv_sync.log"); then
      log_error "V1 agent dependency sync failed (see $LOG_DIR/v1_uv_sync.log)"
      return 1
    fi

    # Pre-download turn detector models if missing
    local hf_cache_dir="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
    local model_dir="$hf_cache_dir/models--livekit--turn-detector"
    if [[ ! -d "$model_dir" || ! -d "$model_dir/blobs" || -z "$(ls -A "$model_dir/blobs" 2>/dev/null)" ]]; then
      log_info "Pre-downloading turn detector models..."
      (cd "$V1_AGENT_DIR" && uv run -m frontal_cortex.agent download-files >>"$LOG_DIR/v1_uv_sync.log" 2>&1) || true
    fi
  else
    log_warn "Skipping V1 agent dependency sync (SKIP_V1_SYNC=true)"
  fi

  log_info "Starting V1 agent (LiveKit: ${LIVEKIT_URL}, agent_name=${LIVEKIT_AGENT_NAME})..."
  (
    trap - INT TERM EXIT HUP
    cd "$V1_AGENT_DIR"
    export LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET LIVEKIT_AGENT_NAME
    export MS365_MCP_CLIENT_ID MS365_MCP_TENANT_ID MS365_MCP_CLIENT_SECRET MS365_BUSINESS_EMAIL
    export MS365_MCP_TRANSPORT MS365_MCP_SERVER_URL MS365_MCP_AUTH_URL MS365_MCP_TOKEN_URL
    export MS365_MCP_SCOPE MS365_OAUTH_CALLBACK_URL MS365_MCP_REDIRECT_URI
    exec uv run -m frontal_cortex.agent start
  ) >>"$LOG_DIR/v1_agent.log" 2>&1 &
  V1_AGENT_PID=$!
  V1_AGENT_STARTED_BY_SCRIPT=true
  sleep 3
  if ! ps -p "$V1_AGENT_PID" >/dev/null 2>&1; then
    log_error "V1 agent failed to start (see $LOG_DIR/v1_agent.log)"
    tail -30 "$LOG_DIR/v1_agent.log" 2>/dev/null || true
    return 1
  fi
  log_success "V1 agent started (PID: $V1_AGENT_PID)"
  return 0
}

start_telegram_bot() {
  rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE"
  rm -f "$TELEGRAM_BOT_DEFERRED_MARKER_FILE"
  if [[ "$START_TELEGRAM" != "true" ]]; then
    log_info "Skipping Telegram bot startup"
    return 0
  fi

  local _env_unset_marker="__VIVENTIUM_UNSET__"
  local _saved_api_key="${API_KEY-$_env_unset_marker}"
  local _saved_base_url="${BASE_URL-$_env_unset_marker}"
  local _saved_bot_token="${BOT_TOKEN-$_env_unset_marker}"
  local _saved_config_dir="${CONFIG_DIR-$_env_unset_marker}"
  local _saved_livekit_url="${LIVEKIT_URL-$_env_unset_marker}"
  local _saved_livekit_api_key="${LIVEKIT_API_KEY-$_env_unset_marker}"
  local _saved_livekit_api_secret="${LIVEKIT_API_SECRET-$_env_unset_marker}"
  local _saved_livekit_api_host="${LIVEKIT_API_HOST-$_env_unset_marker}"
  local _saved_next_public_livekit_url="${NEXT_PUBLIC_LIVEKIT_URL-$_env_unset_marker}"
  local _saved_livekit_agent_name="${LIVEKIT_AGENT_NAME-$_env_unset_marker}"
  local _saved_librechat_origin="${VIVENTIUM_LIBRECHAT_ORIGIN-$_env_unset_marker}"
  local _saved_call_session_secret="${VIVENTIUM_CALL_SESSION_SECRET-$_env_unset_marker}"
  local _saved_telegram_secret="${VIVENTIUM_TELEGRAM_SECRET-$_env_unset_marker}"
  local _saved_telegram_backend="${VIVENTIUM_TELEGRAM_BACKEND-$_env_unset_marker}"
  local _saved_telegram_max_file_size="${VIVENTIUM_TELEGRAM_MAX_FILE_SIZE-$_env_unset_marker}"
  local _saved_telegram_bot_api_origin="${VIVENTIUM_TELEGRAM_BOT_API_ORIGIN-$_env_unset_marker}"
  local _saved_telegram_bot_api_base_url="${VIVENTIUM_TELEGRAM_BOT_API_BASE_URL-$_env_unset_marker}"
  local _saved_telegram_bot_api_base_file_url="${VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_enabled="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_host="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_port="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_binary_path="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_api_id="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID-$_env_unset_marker}"
  local _saved_telegram_local_bot_api_api_hash="${VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH-$_env_unset_marker}"

  restore_telegram_env() {
    if [[ "$_saved_api_key" == "$_env_unset_marker" ]]; then unset API_KEY; else export API_KEY="$_saved_api_key"; fi
    if [[ "$_saved_base_url" == "$_env_unset_marker" ]]; then unset BASE_URL; else export BASE_URL="$_saved_base_url"; fi
    if [[ "$_saved_bot_token" == "$_env_unset_marker" ]]; then unset BOT_TOKEN; else export BOT_TOKEN="$_saved_bot_token"; fi
    if [[ "$_saved_config_dir" == "$_env_unset_marker" ]]; then unset CONFIG_DIR; else export CONFIG_DIR="$_saved_config_dir"; fi
    if [[ "$_saved_livekit_url" == "$_env_unset_marker" ]]; then unset LIVEKIT_URL; else export LIVEKIT_URL="$_saved_livekit_url"; fi
    if [[ "$_saved_livekit_api_key" == "$_env_unset_marker" ]]; then unset LIVEKIT_API_KEY; else export LIVEKIT_API_KEY="$_saved_livekit_api_key"; fi
    if [[ "$_saved_livekit_api_secret" == "$_env_unset_marker" ]]; then unset LIVEKIT_API_SECRET; else export LIVEKIT_API_SECRET="$_saved_livekit_api_secret"; fi
    if [[ "$_saved_livekit_api_host" == "$_env_unset_marker" ]]; then unset LIVEKIT_API_HOST; else export LIVEKIT_API_HOST="$_saved_livekit_api_host"; fi
    if [[ "$_saved_next_public_livekit_url" == "$_env_unset_marker" ]]; then unset NEXT_PUBLIC_LIVEKIT_URL; else export NEXT_PUBLIC_LIVEKIT_URL="$_saved_next_public_livekit_url"; fi
    if [[ "$_saved_livekit_agent_name" == "$_env_unset_marker" ]]; then unset LIVEKIT_AGENT_NAME; else export LIVEKIT_AGENT_NAME="$_saved_livekit_agent_name"; fi
    if [[ "$_saved_librechat_origin" == "$_env_unset_marker" ]]; then unset VIVENTIUM_LIBRECHAT_ORIGIN; else export VIVENTIUM_LIBRECHAT_ORIGIN="$_saved_librechat_origin"; fi
    if [[ "$_saved_call_session_secret" == "$_env_unset_marker" ]]; then unset VIVENTIUM_CALL_SESSION_SECRET; else export VIVENTIUM_CALL_SESSION_SECRET="$_saved_call_session_secret"; fi
    if [[ "$_saved_telegram_secret" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_SECRET; else export VIVENTIUM_TELEGRAM_SECRET="$_saved_telegram_secret"; fi
    if [[ "$_saved_telegram_backend" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_BACKEND; else export VIVENTIUM_TELEGRAM_BACKEND="$_saved_telegram_backend"; fi
    if [[ "$_saved_telegram_max_file_size" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_MAX_FILE_SIZE; else export VIVENTIUM_TELEGRAM_MAX_FILE_SIZE="$_saved_telegram_max_file_size"; fi
    if [[ "$_saved_telegram_bot_api_origin" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_BOT_API_ORIGIN; else export VIVENTIUM_TELEGRAM_BOT_API_ORIGIN="$_saved_telegram_bot_api_origin"; fi
    if [[ "$_saved_telegram_bot_api_base_url" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_BOT_API_BASE_URL; else export VIVENTIUM_TELEGRAM_BOT_API_BASE_URL="$_saved_telegram_bot_api_base_url"; fi
    if [[ "$_saved_telegram_bot_api_base_file_url" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL; else export VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL="$_saved_telegram_bot_api_base_file_url"; fi
    if [[ "$_saved_telegram_local_bot_api_enabled" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED="$_saved_telegram_local_bot_api_enabled"; fi
    if [[ "$_saved_telegram_local_bot_api_host" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST="$_saved_telegram_local_bot_api_host"; fi
    if [[ "$_saved_telegram_local_bot_api_port" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT="$_saved_telegram_local_bot_api_port"; fi
    if [[ "$_saved_telegram_local_bot_api_binary_path" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH="$_saved_telegram_local_bot_api_binary_path"; fi
    if [[ "$_saved_telegram_local_bot_api_api_id" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID="$_saved_telegram_local_bot_api_api_id"; fi
    if [[ "$_saved_telegram_local_bot_api_api_hash" == "$_env_unset_marker" ]]; then unset VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH; else export VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH="$_saved_telegram_local_bot_api_api_hash"; fi
  }

  local telegram_dir
  telegram_dir=$(resolve_telegram_dir)
  if [[ -z "$telegram_dir" ]]; then
    log_warn "Telegram bot directory not found (expected $TELEGRAM_DIR_PRIMARY or $TELEGRAM_DIR_FALLBACK)"
    return 1
  fi

  # Map OpenAI key for Whisper if API_KEY is not explicitly set
  if [[ -z "${API_KEY:-}" && -n "${OPENAI_API_KEY:-}" ]]; then
    export API_KEY="$OPENAI_API_KEY"
  fi
  if [[ -z "${BASE_URL:-}" ]]; then
    export BASE_URL="https://api.openai.com/v1"
  fi

  pushd "$telegram_dir" >/dev/null
  if [[ -f "$TELEGRAM_CONFIG_ENV_FILE" ]]; then
    apply_telegram_overlay_env "$TELEGRAM_CONFIG_ENV_FILE"
  elif [[ -f "config.env" ]]; then
    apply_telegram_overlay_env "config.env"
  elif [[ -f ".env" ]]; then
    apply_telegram_overlay_env ".env"
  elif [[ -f "../../.env" ]]; then
    apply_telegram_overlay_env "../../.env"
  fi
  export CONFIG_DIR="$TELEGRAM_USER_CONFIGS_DIR"

  local telegram_backend="${VIVENTIUM_TELEGRAM_BACKEND:-librechat}"
  telegram_backend=$(echo "$telegram_backend" | tr '[:upper:]' '[:lower:]')
  if [[ "$telegram_backend" != "librechat" && "$telegram_backend" != "livekit" ]]; then
    log_warn "Unknown Telegram backend '$telegram_backend' - defaulting to librechat"
    telegram_backend="librechat"
  fi

  if [[ -z "${BOT_TOKEN:-}" ]]; then
    log_warn "BOT_TOKEN not set - skipping Telegram bot startup"
    restore_telegram_env
    popd >/dev/null
    return 0
  fi
  if ! telegram_bot_token_looks_valid "${BOT_TOKEN:-}"; then
    log_warn "BOT_TOKEN does not look like a BotFather token - skipping Telegram bot startup"
    restore_telegram_env
    popd >/dev/null
    return 1
  fi
  if ! ensure_telegram_media_prereqs; then
    log_error "Telegram bot cannot start without ffmpeg for supported voice/video media"
    restore_telegram_env
    popd >/dev/null
    return 1
  fi
  if ! start_telegram_local_bot_api; then
    restore_telegram_env
    popd >/dev/null
    return 1
  fi

  local telegram_agent_name=""
  local previous_agent_name=""
  if [[ "$telegram_backend" == "livekit" ]]; then
    if [[ -z "${LIVEKIT_URL:-}" || -z "${LIVEKIT_API_KEY:-}" || -z "${LIVEKIT_API_SECRET:-}" ]]; then
      log_warn "LiveKit credentials missing - skipping Telegram bot startup"
      restore_telegram_env
      popd >/dev/null
      return 0
    fi

    telegram_agent_name="${VIVENTIUM_TELEGRAM_AGENT_NAME:-$LIVEKIT_AGENT_NAME}"
    if [[ -z "$telegram_agent_name" ]]; then
      telegram_agent_name="viventium"
    fi
    previous_agent_name="$LIVEKIT_AGENT_NAME"
  else
    if [[ -z "${VIVENTIUM_TELEGRAM_USER_ID:-}" ]]; then
      log_warn "VIVENTIUM_TELEGRAM_USER_ID not set - Telegram LibreChat bridge will attempt fallback"
    fi
    if [[ -z "${VIVENTIUM_TELEGRAM_SECRET:-}" && -z "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
      log_warn "VIVENTIUM_TELEGRAM_SECRET not set - Telegram LibreChat bridge will fail auth"
    fi
  fi

  if [[ "$telegram_backend" == "livekit" ]]; then
    log_info "Starting Telegram bot (backend=livekit, agent_name=${telegram_agent_name})..."
  else
    log_info "Starting Telegram bot (backend=librechat)..."
  fi
  EXISTING_TELEGRAM_PIDS=""
  if telegram_pid_is_running; then
    EXISTING_TELEGRAM_PIDS="$(read_pid_file "$TELEGRAM_BOT_PID_FILE")"
  fi
  if [[ -n "$EXISTING_TELEGRAM_PIDS" ]]; then
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "Existing Telegram bot process detected - restarting"
      kill_pids "$EXISTING_TELEGRAM_PIDS"
      rm -f "$TELEGRAM_BOT_PID_FILE"
      sleep 1
    else
      log_success "Telegram bot already running (PID: $EXISTING_TELEGRAM_PIDS)"
      restore_telegram_env
      popd >/dev/null
      return 0
    fi
  fi

  export VIVENTIUM_TELEGRAM_BACKEND="$telegram_backend"
  if [[ "$telegram_backend" == "librechat" ]]; then
    export VIVENTIUM_LIBRECHAT_ORIGIN="${VIVENTIUM_LIBRECHAT_ORIGIN:-${LC_API_URL}}"
  else
    export LIVEKIT_AGENT_NAME="$telegram_agent_name"
  fi
  pushd TelegramVivBot >/dev/null
  if [[ ( -e ".venv" || -L ".venv" ) && ! -d ".venv" ]]; then
    log_warn "Telegram bot venv path exists but is not a directory; rebuilding"
    rm -f ".venv"
  fi
  if [[ -d ".venv" && ( ! -f ".venv/pyvenv.cfg" || ! -e ".venv/bin" ) ]]; then
    log_warn "Telegram bot venv is incomplete; rebuilding"
    rm -rf ".venv"
  fi
  local telegram_python=""
  if [[ -f "pyproject.toml" && -f "uv.lock" ]] && command -v uv >/dev/null 2>&1; then
    local deps_signature_file="$LOG_DIR/telegram_bot_deps.sha256"
    local deps_signature=""
    local cached_signature=""
    local needs_dependency_sync=true
    deps_signature="$("$PYTHON_BIN" - "$PWD" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
for rel_path in ("pyproject.toml", "uv.lock", "requirements.txt"):
    path = root / rel_path
    if not path.exists():
        continue
    digest.update(rel_path.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
)" || true
    if [[ -n "$deps_signature" && -x ".venv/bin/python" && -f "$deps_signature_file" ]]; then
      cached_signature="$(tr -d '\r\n' <"$deps_signature_file" 2>/dev/null || true)"
      if [[ "$cached_signature" == "$deps_signature" ]]; then
        needs_dependency_sync=false
      fi
    fi

    if [[ "$needs_dependency_sync" == "true" ]]; then
      log_info "Syncing Telegram bot dependencies..."
      if ! uv sync --frozen >"$LOG_DIR/telegram_bot_install.log" 2>&1; then
        log_error "Telegram bot dependency sync failed"
        tail -20 "$LOG_DIR/telegram_bot_install.log" 2>/dev/null || true
        restore_telegram_env
        popd >/dev/null
        popd >/dev/null
        return 1
      fi
      if [[ -n "$deps_signature" ]]; then
        printf '%s\n' "$deps_signature" >"$deps_signature_file"
      fi
    else
      log_success "Telegram bot dependencies already up to date"
    fi
  fi
  if [[ -x ".venv/bin/python" ]]; then
    telegram_python=".venv/bin/python"
  else
    telegram_python="$PYTHON_BIN"
  fi

  # === VIVENTIUM START ===
  # Feature: Telegram voice-route parity for local Chatterbox.
  #
  # Purpose:
  # - Telegram now follows the same saved voice route source of truth as the modern playground.
  # - A user may pick local Chatterbox in the browser even when the process-level default provider
  #   is something else, so the Telegram runtime still needs the optional MLX deps available.
  # - Keep this install scoped to macOS/Apple Silicon hosts that can actually run the provider.
  local telegram_mlx_req="../../voice-gateway/requirements.mlx_audio_darwin.txt"
  if host_supports_local_chatterbox_mlx && [[ -x "$telegram_python" && -f "$telegram_mlx_req" ]]; then
    if ! "$telegram_python" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(
    0 if importlib.util.find_spec("mlx_audio") and importlib.util.find_spec("mlx_lm") else 1
)
PY
    then
      log_info "Installing optional local Chatterbox deps for Telegram bot..."
      if "$telegram_python" -m pip --version >/dev/null 2>&1; then
        "$telegram_python" -m pip install -r "$telegram_mlx_req" -q >"$LOG_DIR/telegram_bot_local_tts_install.log" 2>&1
      elif command -v uv >/dev/null 2>&1; then
        uv pip install --python "$telegram_python" --prerelease=allow -r "$telegram_mlx_req" -q >"$LOG_DIR/telegram_bot_local_tts_install.log" 2>&1
      else
        false
      fi
      if [[ $? -ne 0 ]]; then
        log_warn "Telegram local Chatterbox dependency install failed; voice replies may fall back"
        tail -20 "$LOG_DIR/telegram_bot_local_tts_install.log" 2>/dev/null || true
      fi
    fi
  fi
  # === VIVENTIUM END ===

  "$telegram_python" bot.py >"$LOG_DIR/telegram_bot.log" 2>&1 &
  TELEGRAM_BOT_PID=$!
  TELEGRAM_STARTED_BY_SCRIPT=true
  printf '%s\n' "$TELEGRAM_BOT_PID" >"$TELEGRAM_BOT_PID_FILE"
  popd >/dev/null
  popd >/dev/null
  restore_telegram_env
  if [[ "$telegram_backend" == "livekit" ]]; then
    export LIVEKIT_AGENT_NAME="$previous_agent_name"
  fi

  sleep 3
  if ! ps -p "$TELEGRAM_BOT_PID" >/dev/null 2>&1; then
    rm -f "$TELEGRAM_BOT_PID_FILE"
    log_error "Telegram bot failed to start (see $LOG_DIR/telegram_bot.log)"
    tail -30 "$LOG_DIR/telegram_bot.log" 2>/dev/null || true
    return 1
  fi
  log_success "Telegram bot started (PID: $TELEGRAM_BOT_PID)"
  return 0
}

schedule_deferred_telegram_bot_start() {
  local existing_pid=""
  local background_retries="${TELEGRAM_LIBRECHAT_DEFERRED_START_RETRIES:-${TELEGRAM_LIBRECHAT_START_RETRIES:-1800}}"

  if telegram_deferred_pid_is_running; then
    existing_pid="$(read_pid_file "$TELEGRAM_BOT_DEFERRED_PID_FILE")"
    if [[ -n "$existing_pid" ]]; then
      log_success "Deferred Telegram bot startup already queued (PID: $existing_pid)"
      return 0
    fi
  fi

  : >"$TELEGRAM_BOT_DEFERRED_MARKER_FILE"
  rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE"
  (
    trap 'rm -f "$TELEGRAM_BOT_DEFERRED_PID_FILE" "$TELEGRAM_BOT_DEFERRED_MARKER_FILE"' EXIT
    if wait_for_http "${LC_API_URL}/health" "LibreChat API before Telegram bot start" "$background_retries"; then
      if ! start_telegram_bot; then
        log_warn "Telegram bot startup had issues - continuing anyway"
      fi
    else
      log_warn "LibreChat API never became ready; skipping deferred Telegram bot startup"
    fi
  ) &
  local deferred_pid=$!
  printf '%s\n' "$deferred_pid" >"$TELEGRAM_BOT_DEFERRED_PID_FILE"
  log_info "Queued deferred Telegram bot startup watcher (PID: $deferred_pid)"
  return 0
}

start_telegram_codex() {
  if [[ "$START_TELEGRAM_CODEX" != "true" ]]; then
    log_info "Skipping Telegram Codex startup"
    return 0
  fi

  local telegram_codex_dir
  telegram_codex_dir="$(resolve_telegram_codex_dir)"
  if [[ -z "$telegram_codex_dir" ]]; then
    log_warn "Telegram Codex directory not found: $TELEGRAM_CODEX_DIR"
    return 1
  fi

  if [[ -z "${TELEGRAM_CODEX_BOT_TOKEN:-}" && ! -f "$TELEGRAM_CODEX_ENV_FILE" ]]; then
    log_warn "TELEGRAM_CODEX_BOT_TOKEN not set and $TELEGRAM_CODEX_ENV_FILE is missing - skipping Telegram Codex startup"
    return 0
  fi
  if [[ -n "${TELEGRAM_CODEX_BOT_TOKEN:-}" ]] && ! telegram_bot_token_looks_valid "${TELEGRAM_CODEX_BOT_TOKEN:-}"; then
    log_warn "TELEGRAM_CODEX_BOT_TOKEN does not look like a BotFather token - skipping Telegram Codex startup"
    return 1
  fi
  if [[ ! -f "$TELEGRAM_CODEX_SETTINGS_FILE" ]]; then
    log_warn "Telegram Codex settings file not found: $TELEGRAM_CODEX_SETTINGS_FILE"
    return 1
  fi
  if [[ ! -f "$TELEGRAM_CODEX_PROJECTS_FILE" ]]; then
    log_warn "Telegram Codex projects file not found: $TELEGRAM_CODEX_PROJECTS_FILE"
    return 1
  fi

  local existing_pids=""
  if telegram_codex_pid_is_running; then
    existing_pids="$(read_pid_file "$TELEGRAM_CODEX_PID_FILE")"
  fi
  if [[ -n "$existing_pids" ]]; then
    if [[ "$RESTART_SERVICES" == "true" ]]; then
      log_warn "Existing Telegram Codex process detected - restarting"
      kill_pids "$existing_pids"
      rm -f "$TELEGRAM_CODEX_PID_FILE"
      sleep 1
    else
      log_success "Telegram Codex already running (PID: $existing_pids)"
      return 0
    fi
  fi

  log_info "Starting Telegram Codex sidecar..."
  pushd "$telegram_codex_dir" >/dev/null
  export TELEGRAM_CODEX_ENV_FILE
  export TELEGRAM_CODEX_SETTINGS_FILE
  export TELEGRAM_CODEX_PROJECTS_FILE
  if command -v uv >/dev/null 2>&1; then
    uv run telegram-codex >"$LOG_DIR/telegram_codex.log" 2>&1 &
  else
    "$PYTHON_BIN" -m app.main >"$LOG_DIR/telegram_codex.log" 2>&1 &
  fi
  TELEGRAM_CODEX_PID=$!
  TELEGRAM_CODEX_STARTED_BY_SCRIPT=true
  printf '%s\n' "$TELEGRAM_CODEX_PID" >"$TELEGRAM_CODEX_PID_FILE"
  popd >/dev/null

  sleep 3
  if ! ps -p "$TELEGRAM_CODEX_PID" >/dev/null 2>&1; then
    rm -f "$TELEGRAM_CODEX_PID_FILE"
    log_error "Telegram Codex failed to start (see $LOG_DIR/telegram_codex.log)"
    tail -30 "$LOG_DIR/telegram_codex.log" 2>/dev/null || true
    return 1
  fi
  log_success "Telegram Codex started (PID: $TELEGRAM_CODEX_PID)"
  return 0
}

google_mcp_can_start_in_parallel_with_librechat() {
  if [[ "$START_GOOGLE_MCP" != "true" ]]; then
    return 1
  fi
  if ! port_in_use "$GOOGLE_MCP_PORT"; then
    return 0
  fi
  google_mcp_ready
}

ms365_mcp_can_start_in_parallel_with_librechat() {
  if [[ "$START_MS365_MCP" != "true" ]]; then
    return 1
  fi
  if ! port_in_use "$MS365_MCP_PORT"; then
    return 0
  fi
  ms365_http_ping "$MS365_MCP_SERVER_URL"
}

start_dependency_bound_optional_services() {
  if [[ "$START_GOOGLE_MCP" == "true" ]] && ! google_mcp_can_start_in_parallel_with_librechat; then
    GOOGLE_MCP_STARTED_PRE_LIBRECHAT=true
    if ! start_google_workspace_mcp; then
      log_warn "Google Workspace MCP startup had issues - continuing anyway"
    fi
  fi

  if [[ "$START_MS365_MCP" == "true" ]] && ! ms365_mcp_can_start_in_parallel_with_librechat; then
    MS365_MCP_STARTED_PRE_LIBRECHAT=true
    if ! start_ms365_mcp; then
      log_warn "MS365 MCP startup had issues - continuing anyway"
    fi
  fi
}

queue_optional_services_parallel_with_librechat() {
  if [[ "$START_SEARXNG" == "true" ]]; then
    queue_parallel_optional_start \
      "SearxNG startup had issues - continuing anyway" \
      start_searxng
  fi

  if [[ "$START_FIRECRAWL" == "true" ]]; then
    queue_parallel_optional_start \
      "Firecrawl startup had issues - continuing anyway" \
      start_firecrawl
  fi

  if [[ "$START_RAG_API" == "true" && "$SKIP_LIBRECHAT" != "true" ]]; then
    queue_parallel_optional_start \
      "Local RAG API startup had issues - conversation recall sync/file embeddings may be degraded" \
      start_rag_api
  fi

  if [[ "$START_GOOGLE_MCP" == "true" && "$GOOGLE_MCP_STARTED_PRE_LIBRECHAT" != "true" ]] &&
    google_mcp_can_start_in_parallel_with_librechat; then
    queue_parallel_optional_start \
      "Google Workspace MCP startup had issues - continuing anyway" \
      start_google_workspace_mcp
  fi

  if [[ "$START_MS365_MCP" == "true" && "$MS365_MCP_STARTED_PRE_LIBRECHAT" != "true" ]] &&
    ms365_mcp_can_start_in_parallel_with_librechat; then
    queue_parallel_optional_start \
      "MS365 MCP startup had issues - continuing anyway" \
      start_ms365_mcp
  fi

  if [[ "$START_SCHEDULING_MCP" == "true" ]]; then
    queue_parallel_optional_start \
      "Scheduling Cortex MCP startup had issues - continuing anyway" \
      start_scheduling_mcp
  fi

  if [[ "$START_GLASSHIVE" == "true" ]]; then
    queue_parallel_optional_start \
      "GlassHive startup had issues - continuing anyway" \
      start_glasshive
  fi
}

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Viventium LibreChat Voice Stack${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${CYAN}[viventium]${NC} Root: $ROOT_DIR"
echo ""

# Show configuration
echo -e "Configuration:"
echo -e "  Runtime Profile:   ${GREEN}${VIVENTIUM_RUNTIME_PROFILE}${NC}"
echo -e "  Runtime State:     ${GREEN}${VIVENTIUM_STATE_ROOT}${NC}"
echo -e "  LiveKit URL:       ${GREEN}${LIVEKIT_URL}${NC}"
echo -e "  LiveKit API Key:   ${GREEN}${LIVEKIT_API_KEY}${NC}"
echo -e "  LiveKit Node IP:   ${GREEN}${LIVEKIT_NODE_IP}${NC}"
echo -e "  Playground URL:    ${GREEN}${VIVENTIUM_PLAYGROUND_URL}${NC}"
echo -e "  Playground UI:     ${GREEN}${PLAYGROUND_VARIANT}${NC}"
echo -e "  LibreChat Origin:  ${GREEN}${VIVENTIUM_LIBRECHAT_ORIGIN}${NC}"
echo -e "  Mongo URI:         ${GREEN}${MONGO_URI}${NC}"
echo -e "  Scheduler DB:      ${GREEN}${SCHEDULING_DB_PATH}${NC}"
echo -e "  Default Timezone:  ${GREEN}${VIVENTIUM_DEFAULT_TIMEZONE:-UTC}${NC}"
echo -e "  Voice Agent Name:  ${GREEN}${VIVENTIUM_VOICE_GATEWAY_AGENT_NAME}${NC}"
echo -e "  MS365 MCP URL:     ${GREEN}${MS365_MCP_SERVER_URL}${NC}"
echo -e "  Google MCP URL:    ${GREEN}${GOOGLE_WORKSPACE_MCP_URL}${NC}"
echo -e "  Code Interpreter: ${GREEN}${LIBRECHAT_CODE_BASEURL}${NC}"
if [[ -n "${FIRECRAWL_BASE_URL:-}" ]]; then
  echo -e "  Firecrawl URL:    ${GREEN}${FIRECRAWL_BASE_URL}${NC}"
fi
if [[ -n "${SEARXNG_INSTANCE_URL:-}" ]]; then
  echo -e "  SearxNG URL:       ${GREEN}${SEARXNG_INSTANCE_URL}${NC}"
fi
if [[ -n "${VIVENTIUM_WEB_SEARCH_PROVIDER:-}" ]]; then
  echo -e "  Web Search:        ${GREEN}${VIVENTIUM_WEB_SEARCH_PROVIDER}${NC}"
fi
if [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
  _secret_len=${#VIVENTIUM_CALL_SESSION_SECRET}
  if [[ $_secret_len -ge 8 ]]; then
    _secret_mask="${VIVENTIUM_CALL_SESSION_SECRET:0:4}...${VIVENTIUM_CALL_SESSION_SECRET: -4}"
  else
    _secret_mask="(len=$_secret_len)"
  fi
  echo -e "  Call Secret:       ${GREEN}${_secret_mask}${NC}"
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo -e "  OpenAI API Key:    ${GREEN}${OPENAI_API_KEY:0:8}...${NC}"
else
  echo -e "  OpenAI API Key:    ${YELLOW}Not set (STT will fail)${NC}"
fi
# Check for ElevenLabs API key (support both ELEVEN_API_KEY and ELEVENLABS_API_KEY)
ELEVEN_API_KEY_FINAL="${ELEVEN_API_KEY:-${ELEVENLABS_API_KEY:-}}"
if [[ -n "${ELEVEN_API_KEY_FINAL:-}" ]]; then
  echo -e "  ElevenLabs API Key: ${GREEN}${ELEVEN_API_KEY_FINAL:0:8}...${NC}"
else
  echo -e "  ElevenLabs API Key: ${YELLOW}Not set (TTS will fallback to OpenAI)${NC}"
fi
# Check for xAI API key
if [[ -n "${XAI_API_KEY:-}" ]]; then
  echo -e "  xAI API Key:        ${GREEN}${XAI_API_KEY:0:8}...${NC}"
else
  echo -e "  xAI API Key:        ${YELLOW}Not set${NC}"
fi
if [[ -n "${CARTESIA_API_KEY:-}" ]]; then
  echo -e "  Cartesia API Key:   ${GREEN}${CARTESIA_API_KEY:0:8}...${NC}"
else
  echo -e "  Cartesia API Key:   ${YELLOW}Not set${NC}"
fi
if [[ -n "${VIVENTIUM_FC_CONSCIOUS_VOICE_ID:-}" ]]; then
  echo -e "  TTS Voice ID:      ${GREEN}${VIVENTIUM_FC_CONSCIOUS_VOICE_ID}${NC}"
fi
if [[ -n "${VIVENTIUM_XAI_VOICE:-}" ]]; then
  echo -e "  xAI Voice:         ${GREEN}${VIVENTIUM_XAI_VOICE}${NC}"
fi
if [[ -n "${VIVENTIUM_TTS_PROVIDER:-}" ]]; then
  echo -e "  TTS Provider:      ${GREEN}${VIVENTIUM_TTS_PROVIDER}${NC}"
else
  echo -e "  TTS Provider:      ${GREEN}elevenlabs (default)${NC}"
fi
if [[ -n "${VIVENTIUM_STT_PROVIDER:-}" ]]; then
  echo -e "  STT Provider:      ${GREEN}${VIVENTIUM_STT_PROVIDER}${NC}"
fi
if [[ -n "${VIVENTIUM_CARTESIA_VOICE_ID:-}" ]]; then
  echo -e "  Cartesia Voice ID: ${GREEN}${VIVENTIUM_CARTESIA_VOICE_ID}${NC}"
fi
echo ""

require_cmd curl

## === VIVENTIUM START ===
# Feature: Startup preflight guard
# Purpose: Prevent partial startup (containers/processes) when required repos/files are missing
if ! ensure_required_paths_ready; then
  exit 1
fi
## === VIVENTIUM END ===

if [[ "$RESTART_SERVICES" == "true" ]]; then
  stop_running_services
fi

cleanup_stale_containers

# Enable cleanup once we've printed config and are about to start services.
CLEANUP_ENABLED=true

# Kick Docker Desktop early on macOS so daemon warm-up overlaps with runtime prep
# instead of blocking later when the first Docker-backed service is reached.
prewarm_docker_desktop_startup

# Resolve playground port early so LibreChat gets the correct URL if we need
# to fall back due to a port conflict.
if [[ "$SKIP_PLAYGROUND" != "true" ]]; then
  PLAYGROUND_PORT="$(get_playground_port)"
  if [[ "$RESTART_SERVICES" == "true" && -n "$PLAYGROUND_PORT" ]]; then
    if port_in_use "$PLAYGROUND_PORT"; then
      kill_port_listeners "$PLAYGROUND_PORT" "$PLAYGROUND_APP_DIR"
    fi
    if port_in_use "$PLAYGROUND_PORT"; then
      if [[ "$PLAYGROUND_URL_WAS_DEFAULT" == "true" ]]; then
        fallback_port=$(find_free_port "$PLAYGROUND_PORT" "$MS365_MCP_CALLBACK_PORT")
        log_warn "Playground port $PLAYGROUND_PORT in use (outside scope); using $fallback_port for this run"
        PLAYGROUND_PORT="$fallback_port"
        VIVENTIUM_PLAYGROUND_URL="http://localhost:${PLAYGROUND_PORT}"
      else
        log_warn "Playground port $PLAYGROUND_PORT in use (outside scope); skipping playground startup"
        PLAYGROUND_START_BLOCKED=true
      fi
    fi
  fi
fi

prepare_remote_call_access

export LIVEKIT_NODE_IP="${LIVEKIT_NODE_IP:-$(detect_livekit_node_ip)}"

if [[ -n "${VIVENTIUM_PUBLIC_CLIENT_URL:-}" || -n "${VIVENTIUM_PUBLIC_PLAYGROUND_URL:-}" || -n "${VIVENTIUM_PUBLIC_LIVEKIT_URL:-}" ]]; then
  echo -e "${CYAN}[viventium]${NC} Public remote access:"
  [[ -n "${VIVENTIUM_PUBLIC_CLIENT_URL:-}" ]] && echo -e "  App:         ${GREEN}${VIVENTIUM_PUBLIC_CLIENT_URL}${NC}"
  [[ -n "${VIVENTIUM_PUBLIC_SERVER_URL:-}" ]] && echo -e "  API:         ${GREEN}${VIVENTIUM_PUBLIC_SERVER_URL}${NC}"
  [[ -n "${VIVENTIUM_PUBLIC_PLAYGROUND_URL:-}" ]] && echo -e "  Playground:  ${GREEN}${VIVENTIUM_PUBLIC_PLAYGROUND_URL}${NC}"
  [[ -n "${VIVENTIUM_PUBLIC_LIVEKIT_URL:-}" ]] && echo -e "  LiveKit:     ${GREEN}${VIVENTIUM_PUBLIC_LIVEKIT_URL}${NC}"
fi
start_remote_call_mapping_refresh_worker

# ----------------------------
# LiveKit server (Docker)
# ----------------------------
# === VIVENTIUM START ===
# Feature: Idempotent LiveKit startup (reuse container, avoid mid-session restarts)
# Added: 2026-01-11
# === VIVENTIUM END ===
if [[ "$SKIP_LIVEKIT" != "true" ]]; then
  native_install_mode=false
  if [[ "${VIVENTIUM_INSTALL_MODE:-docker}" == "native" ]]; then
    native_install_mode=true
  fi
  if [[ "$SKIP_DOCKER" == "true" ]]; then
    if ! wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
      log_error "LiveKit is not reachable at ${LIVEKIT_API_HOST} and --skip-docker is enabled"
      exit 1
    fi
    log_success "Using external/native LiveKit at ${LIVEKIT_API_HOST}"
  else
    if curl -fsS --max-time 2 "$LIVEKIT_API_HOST" >/dev/null 2>&1; then
      log_success "Using existing/native LiveKit at ${LIVEKIT_API_HOST}"
    else
      native_livekit_bin=""
      if [[ "$native_install_mode" == "true" ]]; then
        native_livekit_bin="$(livekit_native_binary_path || true)"
      elif ! docker image inspect livekit/livekit-server >/dev/null 2>&1; then
        native_livekit_bin="$(livekit_native_binary_path || true)"
      fi

      if [[ -n "$native_livekit_bin" ]]; then
        if ! start_native_livekit_fallback "$native_livekit_bin"; then
          exit 1
        fi
      else
        require_cmd docker

        if ! docker_daemon_ready; then
          # === VIVENTIUM START ===
          # Feature: Auto-start Docker Desktop on macOS for one-click local startup.
          # === VIVENTIUM END ===
          request_docker_desktop_launch || true
          docker_start_retries="${VIVENTIUM_DOCKER_START_RETRIES:-90}"
          if ! [[ "$docker_start_retries" =~ ^[0-9]+$ ]] || [[ "$docker_start_retries" -lt 1 ]]; then
            docker_start_retries=90
          fi
          for _ in $(seq 1 "$docker_start_retries"); do
            if docker_daemon_ready; then
              break
            fi
            sleep 2
          done
        fi

        if ! docker_daemon_ready; then
          echo -e "${RED}[viventium]${NC} Docker is not running"
          exit 1
        fi

        EXISTING=$(docker ps -q \
          --filter "label=viventium.stack=viventium_v0_4" \
          --filter "label=viventium.service=livekit" \
          --filter "label=viventium.profile=${VIVENTIUM_RUNTIME_PROFILE}" \
          2>/dev/null | head -1)
        if [[ -z "$EXISTING" ]]; then
          EXISTING=$(docker ps -q --filter "name=^/viventium-livekit-${VIVENTIUM_RUNTIME_PROFILE}-" 2>/dev/null | head -1)
        fi
        if [[ -z "$EXISTING" && "$VIVENTIUM_RUNTIME_PROFILE" == "compat" ]]; then
          EXISTING=$(docker ps -q \
            --filter "label=viventium.stack=viventium_v0_4" \
            --filter "label=viventium.service=livekit" \
            2>/dev/null | head -1)
        fi
        if [[ -z "$EXISTING" && "$VIVENTIUM_RUNTIME_PROFILE" == "compat" ]]; then
          EXISTING=$(docker ps -q --filter "name=^/viventium-livekit-" 2>/dev/null | head -1)
        fi

        if [[ -n "$EXISTING" ]]; then
          echo -e "${GREEN}[viventium]${NC} LiveKit already running (container: ${EXISTING:0:12})"
          LIVEKIT_CONTAINER_ID="$EXISTING"
          if ! wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
            log_error "LiveKit container is running but not responding at ${LIVEKIT_API_HOST}"
            exit 1
          fi
        else
          if port_in_use "$LIVEKIT_HTTP_PORT"; then
            echo -e "${YELLOW}[viventium]${NC} Port $LIVEKIT_HTTP_PORT in use by another container; using external LiveKit if available"
            if ! wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
              log_error "LiveKit did not respond at ${LIVEKIT_API_HOST}; stop the other service or set LIVEKIT_URL"
              exit 1
            fi
          else
            # === VIVENTIUM START ===
            # Purpose: Store generated LiveKit config under .viventium to avoid dirtying the repo.
            # === VIVENTIUM END ===
            LIVEKIT_CFG_DIR="$VIVENTIUM_STATE_ROOT/livekit"
            mkdir -p "$LIVEKIT_CFG_DIR"
            LIVEKIT_CFG="$LIVEKIT_CFG_DIR/livekit.yaml"
            LIVEKIT_TURN_CERT_MOUNT=""
            LIVEKIT_TURN_KEY_MOUNT=""
            if [[ -n "${LIVEKIT_TURN_DOMAIN:-}" && -n "${LIVEKIT_TURN_TLS_PORT:-}" && -f "${LIVEKIT_TURN_CERT_FILE:-}" && -f "${LIVEKIT_TURN_KEY_FILE:-}" ]]; then
              LIVEKIT_TURN_CERT_MOUNT="/etc/viventium-livekit-turn.crt"
              LIVEKIT_TURN_KEY_MOUNT="/etc/viventium-livekit-turn.key"
            fi
            write_livekit_config "$LIVEKIT_CFG" "$LIVEKIT_TURN_CERT_MOUNT" "$LIVEKIT_TURN_KEY_MOUNT"

            echo -e "${CYAN}[viventium]${NC} Starting LiveKit server (Docker) ..."
            LIVEKIT_DOCKER_ARGS=(
              docker run -d
              --name "viventium-livekit-${VIVENTIUM_RUNTIME_PROFILE}-$$"
              --label "viventium.stack=viventium_v0_4"
              --label "viventium.service=livekit"
              --label "viventium.profile=${VIVENTIUM_RUNTIME_PROFILE}"
              -p "${LIVEKIT_HTTP_PORT}:${LIVEKIT_HTTP_PORT}"
              -p "${LIVEKIT_TCP_PORT}:${LIVEKIT_TCP_PORT}"
              -p "${LIVEKIT_UDP_PORT}:${LIVEKIT_UDP_PORT}/udp"
              -v "$LIVEKIT_CFG:/etc/livekit.yaml:ro"
            )
            if [[ -n "${LIVEKIT_TURN_TLS_PORT:-}" ]]; then
              LIVEKIT_DOCKER_ARGS+=(-p "${LIVEKIT_TURN_TLS_PORT}:${LIVEKIT_TURN_TLS_PORT}")
            fi
            if [[ -n "$LIVEKIT_TURN_CERT_MOUNT" && -n "$LIVEKIT_TURN_KEY_MOUNT" ]]; then
              LIVEKIT_DOCKER_ARGS+=(
                -v "${LIVEKIT_TURN_CERT_FILE}:${LIVEKIT_TURN_CERT_MOUNT}:ro"
                -v "${LIVEKIT_TURN_KEY_FILE}:${LIVEKIT_TURN_KEY_MOUNT}:ro"
              )
            fi
            LIVEKIT_DOCKER_ARGS+=(
              livekit/livekit-server
              --config /etc/livekit.yaml
              --node-ip "$LIVEKIT_NODE_IP"
            )
            LIVEKIT_CONTAINER_ID="$("${LIVEKIT_DOCKER_ARGS[@]}")"
            LIVEKIT_STARTED_BY_SCRIPT=true
            echo -e "${GREEN}[viventium]${NC} LiveKit container: ${LIVEKIT_CONTAINER_ID:0:12}"
            echo -e "${CYAN}[viventium]${NC} LiveKit node IP: ${LIVEKIT_NODE_IP}"

            if ! wait_for_http "$LIVEKIT_API_HOST" "LiveKit"; then
              log_error "LiveKit did not respond after startup; check Docker logs"
              exit 1
            fi
          fi
        fi
      fi
    fi
  fi
fi

# Prepare the local LibreChat runtime files before optional services start.
# RAG and related compose stacks mount LibreChat/.env and librechat.yaml directly.
if [[ "$SKIP_LIBRECHAT" != "true" ]]; then
  ensure_librechat_env || {
    log_error "Failed to prepare LibreChat .env"
    exit 1
  }
  ensure_librechat_yaml || log_warn "LibreChat config missing; using default config"
  render_librechat_config || log_warn "LibreChat config generation failed; using default config"
fi

# ----------------------------
# MCP Servers
# ----------------------------
rm -f "$MS365_MCP_RUNTIME_EXPORT_FILE"

if ! start_code_interpreter; then
  log_warn "Code Interpreter startup had issues - continuing anyway"
fi

start_dependency_bound_optional_services
queue_optional_services_parallel_with_librechat

# === VIVENTIUM START ===
# Feature: Start Skyvern Browser Agent by default.
# === VIVENTIUM END ===
if ! start_skyvern; then
  log_warn "Skyvern startup had issues - continuing anyway"
fi

# ----------------------------
# MS365 OAuth callback (V1 agent)
# ----------------------------
if ! start_ms365_oauth_callback; then
  if [[ "$START_V1_AGENT" == "true" ]]; then
    log_warn "MS365 OAuth callback server failed to start - OAuth flows may fail"
  fi
fi

# ----------------------------
# V1 Agent (LiveKit)
# ----------------------------
if ! start_v1_agent; then
  log_warn "V1 agent startup had issues - continuing anyway"
fi

# ----------------------------
# Telegram Bot
# ----------------------------
DEFER_TELEGRAM_LIBRECHAT_START=false
if [[ "$START_TELEGRAM" == "true" ]]; then
  telegram_backend_preference="$(echo "${VIVENTIUM_TELEGRAM_BACKEND:-librechat}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$telegram_backend_preference" == "librechat" && "$SKIP_LIBRECHAT" != "true" ]]; then
    DEFER_TELEGRAM_LIBRECHAT_START=true
    : >"$TELEGRAM_BOT_DEFERRED_MARKER_FILE"
    log_info "Deferring Telegram bot startup until LibreChat API is ready"
  fi
fi

if [[ "$DEFER_TELEGRAM_LIBRECHAT_START" != "true" ]]; then
  if ! start_telegram_bot; then
    log_warn "Telegram bot startup had issues - continuing anyway"
  fi
fi

if ! start_telegram_codex; then
  log_warn "Telegram Codex startup had issues - continuing anyway"
fi

# ----------------------------
# LibreChat
# ----------------------------
if [[ "$SKIP_LIBRECHAT" != "true" ]]; then
  if [[ ! -d "$LIBRECHAT_DIR" ]]; then
    echo -e "${RED}[viventium]${NC} LibreChat directory not found: $LIBRECHAT_DIR"
    exit 1
  fi
  require_cmd node
  require_cmd npm
  ensure_validated_node20_runtime || {
    log_error "LibreChat startup requires the validated node@20 runtime"
    exit 1
  }

  if ! ensure_mongodb_ready; then
    log_error "MongoDB is required for LibreChat startup"
    exit 1
  fi

  if ! ensure_meilisearch_ready; then
    log_error "Meilisearch is required for local conversation search startup"
    exit 1
  fi

  reconcile_google_workspace_local_oauth_state

  START_LIBRECHAT=true
  LIBRECHAT_BACKEND_ALREADY_RUNNING=false
  LIBRECHAT_FRONTEND_ALREADY_RUNNING=false
  if port_in_use "$LC_API_PORT"; then
    if curl -s --max-time 3 "${LC_API_URL}/health" >/dev/null 2>&1; then
      if [[ "$RESTART_SERVICES" == "true" ]]; then
        log_warn "LibreChat already running - restarting"
        kill_port_listeners "$LC_API_PORT" "$LIBRECHAT_DIR"
        kill_port_listeners "$LC_FRONTEND_PORT" "$LIBRECHAT_DIR"
        if port_in_use "$LC_API_PORT" || port_in_use "$LC_FRONTEND_PORT"; then
          log_warn "LibreChat ports still in use (outside scope); skipping startup"
          START_LIBRECHAT=false
        fi
      else
        LIBRECHAT_BACKEND_ALREADY_RUNNING=true
      fi
    else
      if [[ "$RESTART_SERVICES" == "true" ]]; then
        log_warn "LibreChat port $LC_API_PORT in use - restarting"
        kill_port_listeners "$LC_API_PORT" "$LIBRECHAT_DIR"
        kill_port_listeners "$LC_FRONTEND_PORT" "$LIBRECHAT_DIR"
        if port_in_use "$LC_API_PORT" || port_in_use "$LC_FRONTEND_PORT"; then
          log_warn "LibreChat ports still in use (outside scope); skipping startup"
          START_LIBRECHAT=false
        fi
      else
        log_warn "Port $LC_API_PORT in use - skipping LibreChat startup"
        START_LIBRECHAT=false
      fi
    fi
  fi

  if [[ "$START_LIBRECHAT" == "true" ]] && port_in_use "$LC_FRONTEND_PORT"; then
    if curl -s --max-time 3 "${LC_FRONTEND_URL}" >/dev/null 2>&1; then
      if [[ "$RESTART_SERVICES" == "true" ]]; then
        log_warn "LibreChat port $LC_FRONTEND_PORT in use - restarting"
        kill_port_listeners "$LC_FRONTEND_PORT" "$LIBRECHAT_DIR"
        if port_in_use "$LC_FRONTEND_PORT"; then
          log_warn "LibreChat port $LC_FRONTEND_PORT still in use (outside scope); skipping startup"
          START_LIBRECHAT=false
        fi
      else
        LIBRECHAT_FRONTEND_ALREADY_RUNNING=true
      fi
    else
      if [[ "$RESTART_SERVICES" == "true" ]]; then
        log_warn "LibreChat port $LC_FRONTEND_PORT in use - restarting"
        kill_port_listeners "$LC_FRONTEND_PORT" "$LIBRECHAT_DIR"
        if port_in_use "$LC_FRONTEND_PORT"; then
          log_warn "LibreChat port $LC_FRONTEND_PORT still in use (outside scope); skipping startup"
          START_LIBRECHAT=false
        fi
      else
        log_warn "Port $LC_FRONTEND_PORT in use - skipping LibreChat startup"
        START_LIBRECHAT=false
      fi
    fi
  fi

  if [[ "$START_LIBRECHAT" == "true" ]]; then
    if [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" == "true" && "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" == "true" ]]; then
      log_success "LibreChat already running on ports $LC_API_PORT/$LC_FRONTEND_PORT"
      START_LIBRECHAT=false
    elif [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" == "true" || "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" == "true" ]]; then
      log_warn "LibreChat partial stack already running; starting the missing service(s)"
    fi
  fi

  if [[ "$START_LIBRECHAT" != "true" ]]; then
    :
  else
    refresh_parallel_runtime_endpoint_overrides
    ensure_librechat_env || {
      log_error "Failed to prepare LibreChat .env"
      exit 1
    }
    ensure_librechat_yaml || log_warn "LibreChat config missing; using default config"
    render_librechat_config || log_warn "LibreChat config generation failed; using default config"

  # Export env vars for LibreChat
  export VIVENTIUM_CALL_SESSION_SECRET
  export LIVEKIT_API_KEY
  export LIVEKIT_API_SECRET
  export LIVEKIT_URL
  export VIVENTIUM_PLAYGROUND_URL
  export MS365_MCP_SERVER_URL MS365_MCP_AUTH_URL MS365_MCP_TOKEN_URL MS365_MCP_SCOPE MS365_MCP_REDIRECT_URI
  export MS365_MCP_CLIENT_ID MS365_MCP_CLIENT_SECRET MS365_MCP_TENANT_ID MS365_BUSINESS_EMAIL
  export GOOGLE_WORKSPACE_MCP_URL GOOGLE_WORKSPACE_MCP_AUTH_URL GOOGLE_WORKSPACE_MCP_TOKEN_URL GOOGLE_WORKSPACE_MCP_SCOPE GOOGLE_WORKSPACE_MCP_REDIRECT_URI
  export GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET
  export LIBRECHAT_CODE_BASEURL LIBRECHAT_CODE_API_KEY

  ensure_librechat_node_dependencies || {
    log_error "Failed to prepare LibreChat Node dependencies"
    exit 1
  }

  # A failed dependency install can tear down local persistence services before the
  # retry succeeds. Re-assert them here so user-default reconciliation and agent
  # seeding do not inherit a stale "Mongo was ready earlier" assumption.
  if ! ensure_mongodb_ready; then
    log_error "MongoDB is required before LibreChat user-default reconciliation and agent seeding"
    exit 1
  fi

  if ! ensure_meilisearch_ready; then
    log_error "Meilisearch is required before LibreChat user-default reconciliation and agent seeding"
    exit 1
  fi

  librechat_server_packages_need_rebuild=false
  librechat_client_package_needs_rebuild=false
  librechat_client_bundle_needs_build=false
  if should_rebuild_librechat_server_packages; then
    librechat_server_packages_need_rebuild=true
  fi
  if should_rebuild_librechat_client_package; then
    librechat_client_package_needs_rebuild=true
  fi
  if [[ ! -f "$LIBRECHAT_DIR/client/dist/index.html" ]]; then
    librechat_client_bundle_needs_build=true
  fi
  if [[ "$librechat_server_packages_need_rebuild" == "true" || "$librechat_client_package_needs_rebuild" == "true" ]]; then
    LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=true
  fi
  if [[ "$librechat_client_bundle_needs_build" == "true" ]]; then
    LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN=true
  fi

  reconcile_viventium_user_defaults || \
    log_warn "Viventium local user defaults may not fully reflect install defaults for this run"

  ensure_viventium_agents_seeded || {
    log_error "Failed to seed built-in Viventium agents"
    exit 1
  }

  echo -e "${CYAN}[viventium]${NC} Starting LibreChat (backend+frontend) ..."

  USE_LIBRECHAT_WRAPPER=false
  if [[ -f "$LIBRECHAT_DIR/viventium-start.sh" ]]; then
    direct_librechat_reason=""
    if detached_start_requested; then
      direct_librechat_reason="detached launch"
    elif [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" == "true" || "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" == "true" ]]; then
      direct_librechat_reason="partial stack repair"
    elif should_rebuild_librechat_packages; then
      direct_librechat_reason="LibreChat package rebuild required"
    fi

    if [[ -n "$direct_librechat_reason" ]]; then
      log_info "Using direct LibreChat startup fallback (${direct_librechat_reason})"
    elif command -v mongosh >/dev/null 2>&1; then
      USE_LIBRECHAT_WRAPPER=true
    else
      log_warn "mongosh not found; using direct LibreChat startup fallback"
    fi
  fi

  if [[ "$USE_LIBRECHAT_WRAPPER" == "true" ]]; then
    (
      trap - INT TERM EXIT HUP
      cd "$LIBRECHAT_DIR"
      exec ./viventium-start.sh
    ) &
    LIBRECHAT_PID=$!
  else
    # Fallback: start directly without mongosh dependency.
    (
      trap - INT TERM EXIT HUP
      cd "$LIBRECHAT_DIR"

      ## === VIVENTIUM START ===
      # Rebuild packages only when dist markers are missing/stale (or forced).
      if [[ "$librechat_server_packages_need_rebuild" == "true" ]]; then
        echo -e "${YELLOW}[viventium]${NC} Building LibreChat server packages..."
        npm run build:data-provider
        npm run build:data-schemas
        npm run build:api
      fi
      if [[ "$librechat_client_package_needs_rebuild" == "true" || "$librechat_client_bundle_needs_build" == "true" ]]; then
        echo -e "${YELLOW}[viventium]${NC} Building LibreChat client package..."
        npm run build:client-package
      else
        echo -e "${CYAN}[viventium]${NC} Using existing LibreChat package builds"
      fi
      ## === VIVENTIUM END ===

      if [[ "$librechat_client_bundle_needs_build" == "true" ]]; then
        echo -e "${YELLOW}[viventium]${NC} Building LibreChat client bundle..."
        (
          build_node_options="$(librechat_client_build_node_options)"
          if [[ -n "$build_node_options" ]]; then
            export NODE_OPTIONS="${build_node_options}${NODE_OPTIONS:+ ${NODE_OPTIONS}}"
          fi
          cd client
          npm run build
        )
      fi

      if is_truthy "${SEARCH:-false}"; then
        echo -e "${YELLOW}[viventium]${NC} Ensuring local conversation search is fully indexed..."
        if ! node scripts/viventium-sync-local-search.js; then
          log_warn "Local conversation search sync failed; continuing without blocking frontend startup"
        fi
      fi

      # Keep detached/direct launches supervised by this shell so a later
      # frontend exit cannot strand Telegram behind a dead LibreChat API.
      STARTED_LIBRECHAT_PIDS=()
      if [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" != "true" ]]; then
        npm run backend:dev &
        BACKEND_PID=$!
        STARTED_LIBRECHAT_PIDS+=("$BACKEND_PID")
        sleep 5
      fi
      if [[ "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" != "true" ]]; then
        librechat_dev_host="${HOST:-::}"
        (
          cd client
          BACKEND_PORT="$LC_API_PORT" VIVENTIUM_LC_API_PORT="$LC_API_PORT" npm run dev -- --host "$librechat_dev_host" --port "$LC_FRONTEND_PORT"
        ) &
        FRONTEND_PID=$!
        STARTED_LIBRECHAT_PIDS+=("$FRONTEND_PID")
      fi
      if (( ${#STARTED_LIBRECHAT_PIDS[@]} > 0 )); then
        wait "${STARTED_LIBRECHAT_PIDS[@]}"
      fi
    ) &
    LIBRECHAT_PID=$!
  fi
  LIBRECHAT_STARTED_BY_SCRIPT=true
  echo -e "${GREEN}[viventium]${NC} LibreChat pid: $LIBRECHAT_PID"
  fi
fi

if [[ "$DEFER_TELEGRAM_LIBRECHAT_START" == "true" ]]; then
  if ! schedule_deferred_telegram_bot_start; then
    log_warn "Unable to queue deferred Telegram bot startup; falling back to inline wait"
    if wait_for_http "${LC_API_URL}/health" "LibreChat API before Telegram bot start" "${TELEGRAM_LIBRECHAT_START_RETRIES:-240}"; then
      if ! start_telegram_bot; then
        log_warn "Telegram bot startup had issues - continuing anyway"
      fi
    else
      log_warn "LibreChat API never became ready; skipping deferred Telegram bot startup"
    fi
  fi
fi

# ----------------------------
# Agents Playground
# ----------------------------
if [[ "$SKIP_PLAYGROUND" != "true" ]]; then
  if [[ ! -d "$PLAYGROUND_APP_DIR" ]]; then
    echo -e "${YELLOW}[viventium]${NC} Playground directory not found, skipping"
  else
    require_cmd node

    # Derive the Next dev server port from VIVENTIUM_PLAYGROUND_URL so the
    # deep-links returned by /api/viventium/calls always match what's running.
    if [[ -z "$PLAYGROUND_PORT" ]]; then
      PLAYGROUND_PORT="$(get_playground_port)"
    fi

    START_PLAYGROUND_RUN=true
    if [[ "$PLAYGROUND_START_BLOCKED" == "true" ]]; then
      START_PLAYGROUND_RUN=false
    fi
    if port_in_use "$PLAYGROUND_PORT"; then
      if [[ "$RESTART_SERVICES" == "true" ]]; then
        log_warn "Playground already running on port $PLAYGROUND_PORT - restarting"
        kill_port_listeners "$PLAYGROUND_PORT" "$PLAYGROUND_APP_DIR"
        if port_in_use "$PLAYGROUND_PORT"; then
          if [[ "$PLAYGROUND_URL_WAS_DEFAULT" == "true" ]]; then
            fallback_port=$(find_free_port "$PLAYGROUND_PORT" "$MS365_MCP_CALLBACK_PORT")
            log_warn "Playground port $PLAYGROUND_PORT still in use (outside scope); using $fallback_port for this run"
            PLAYGROUND_PORT="$fallback_port"
            VIVENTIUM_PLAYGROUND_URL="http://localhost:${PLAYGROUND_PORT}"
          else
            log_warn "Playground port $PLAYGROUND_PORT still in use (outside scope); skipping startup"
            START_PLAYGROUND_RUN=false
          fi
        fi
      else
        log_success "$PLAYGROUND_LABEL already running on port $PLAYGROUND_PORT"
        START_PLAYGROUND_RUN=false
      fi
    fi

    if [[ "$START_PLAYGROUND_RUN" == "true" ]]; then
      echo -e "${CYAN}[viventium]${NC} Starting ${PLAYGROUND_LABEL} (Next dev) on port $PLAYGROUND_PORT ..."
      (
        trap - INT TERM EXIT HUP
        cd "$PLAYGROUND_APP_DIR"
        # Install deps if needed
        if [[ ! -d "node_modules" ]]; then
          echo -e "${YELLOW}[viventium]${NC} Installing playground dependencies..."
          if command -v corepack >/dev/null 2>&1; then
            corepack pnpm install
          elif command -v pnpm >/dev/null 2>&1; then
            pnpm install
          else
            npm install
          fi
        fi
        # Ensure Next sees env vars. Modern Viventium calls are expected to be
        # launched from LibreChat deep-links carrying callSessionId metadata.
        # Leaving AGENT_NAME unset prevents the bare root page from dispatching
        # a voice worker without that session context.
        export LIVEKIT_API_KEY LIVEKIT_API_SECRET LIVEKIT_API_HOST LIVEKIT_URL NEXT_PUBLIC_LIVEKIT_URL
        if [[ "$PLAYGROUND_VARIANT" == "modern" ]]; then
          if [[ -n "${VIVENTIUM_PLAYGROUND_AGENT_NAME:-}" ]]; then
            export AGENT_NAME="$VIVENTIUM_PLAYGROUND_AGENT_NAME"
          else
            unset AGENT_NAME || true
          fi
        else
          export AGENT_NAME="${AGENT_NAME:-$VIVENTIUM_VOICE_GATEWAY_AGENT_NAME}"
          export NEXT_PUBLIC_PLAYGROUND_VARIANT="$PLAYGROUND_VARIANT"
        fi
        if [[ "$PLAYGROUND_VARIANT" == "modern" ]]; then
          export VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR="${VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR:-.next-viventium-dev}"
          next_dist_dir="$VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR"
          if [[ -e "$next_dist_dir" ]]; then
            echo -e "${YELLOW}[viventium]${NC} Resetting stale modern-playground build cache..."
            rm -rf "$next_dist_dir"
          fi
        else
          unset VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR || true
        fi
        # Next.js parses `next dev [dir] [options]`. Passing an extra `--` causes
        # `--port` to be treated as the project directory (crash).
        if [[ -x "node_modules/.bin/next" ]]; then
          exec "./node_modules/.bin/next" dev -p "$PLAYGROUND_PORT"
        else
          exec npx next dev -p "$PLAYGROUND_PORT"
        fi
      ) &
      PLAYGROUND_PID=$!
      PLAYGROUND_STARTED_BY_SCRIPT=true
      echo -e "${GREEN}[viventium]${NC} Playground pid: $PLAYGROUND_PID"
    fi
  fi
fi

# ----------------------------
# Voice Gateway worker
# ----------------------------
if [[ "$SKIP_VOICE_GATEWAY" != "true" ]]; then
  if [[ ! -d "$VOICE_GATEWAY_DIR" ]]; then
    echo -e "${YELLOW}[viventium]${NC} Voice gateway directory not found, skipping"
  else
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      if [[ "${VIVENTIUM_TTS_PROVIDER:-}" == "openai" || "${VIVENTIUM_STT_PROVIDER:-}" == "openai" ]]; then
        echo -e "${YELLOW}[viventium]${NC} OPENAI_API_KEY not set - OpenAI STT/TTS will fail"
      else
        echo -e "${YELLOW}[viventium]${NC} OPENAI_API_KEY not set - continuing with non-OpenAI STT/TTS"
      fi
    fi
    require_cmd "$PYTHON_BIN"

    # === VIVENTIUM START ===
    # Feature: Robust voice worker detection across invocation styles.
    # Purpose: catch parent launchers plus spawned runtime children scoped to the voice-gateway dir.
    EXISTING_VOICE_GATEWAY_PIDS=""
    VOICE_GATEWAY_PID_CANDIDATES="$(
      {
        pgrep -f "voice-gateway/worker.py" 2>/dev/null || true
        pgrep -f "worker.py dev" 2>/dev/null || true
        pgrep -f "worker.py start" 2>/dev/null || true
        find_voice_gateway_runtime_pids "$VOICE_GATEWAY_DIR"
      } | awk 'NF' | sort -u
    )"
    if [[ -n "$VOICE_GATEWAY_PID_CANDIDATES" ]]; then
      for pid in $VOICE_GATEWAY_PID_CANDIDATES; do
        if pid_matches_scope "$pid" "$VOICE_GATEWAY_DIR"; then
          EXISTING_VOICE_GATEWAY_PIDS+="$pid "
        fi
      done
      EXISTING_VOICE_GATEWAY_PIDS=$(echo "$EXISTING_VOICE_GATEWAY_PIDS" | xargs 2>/dev/null || true)
    fi
    # === VIVENTIUM END ===
    if [[ -n "$EXISTING_VOICE_GATEWAY_PIDS" && "$RESTART_SERVICES" != "true" ]]; then
      echo -e "${GREEN}[viventium]${NC} Voice Gateway already running (PID: $EXISTING_VOICE_GATEWAY_PIDS)"
    else
      if [[ -n "$EXISTING_VOICE_GATEWAY_PIDS" ]]; then
        log_warn "Stopping existing Voice Gateway worker"
        kill_pids "$EXISTING_VOICE_GATEWAY_PIDS"
      fi
      # === VIVENTIUM START ===
      # Feature: Delay voice worker launch until cold web surfaces settle.
      # Purpose: LiveKit worker availability is CPU-load based. On clean Macs, starting the
      # voice worker while LibreChat/Playground are still building can make the worker flap
      # "unavailable" before the first call arrives.
      if [[ "$SKIP_LIBRECHAT" != "true" ]]; then
        voice_api_retries="${VOICE_GATEWAY_START_API_RETRIES:-120}"
        voice_frontend_retries="${VOICE_GATEWAY_START_FRONTEND_RETRIES:-120}"
        if ! wait_for_http "${LC_API_URL}/health" "LibreChat API before Voice Gateway start" "$voice_api_retries"; then
          log_warn "LibreChat API was not ready before Voice Gateway launch; continuing anyway"
        fi
        if ! wait_for_http "${LC_FRONTEND_URL}" "LibreChat Frontend before Voice Gateway start" "$voice_frontend_retries"; then
          log_warn "LibreChat Frontend was not ready before Voice Gateway launch; continuing anyway"
        fi
      fi
      if [[ "$SKIP_PLAYGROUND" != "true" ]]; then
        voice_playground_port=""
        voice_playground_port="$(get_playground_port)"
        if port_has_listener "$voice_playground_port"; then
          log_success "${PLAYGROUND_LABEL} port is listening before Voice Gateway start"
        elif ! wait_for_http "http://localhost:${voice_playground_port}" "${PLAYGROUND_LABEL} before Voice Gateway start" "${VOICE_GATEWAY_START_PLAYGROUND_RETRIES:-120}"; then
          log_warn "${PLAYGROUND_LABEL} was not ready before Voice Gateway launch; continuing anyway"
        fi
      fi
      # === VIVENTIUM END ===
      echo -e "${CYAN}[viventium]${NC} Starting Voice Gateway worker ..."
      (
        trap - INT TERM EXIT HUP
        cd "$VOICE_GATEWAY_DIR"
        venv_dir="$VOICE_GATEWAY_DIR/.venv"
        preferred_python="$(resolve_voice_python_bin || true)"
        if [[ -z "$preferred_python" ]]; then
          log_error "Local voice gateway requires Python 3.10+; install Homebrew python@3.12 or rerun the installer/upgrade preflight"
          exit 1
        fi

        if [[ "$SKIP_VOICE_DEPS" != "true" ]]; then
          if [[ ( -e "$venv_dir" || -L "$venv_dir" ) && ! -d "$venv_dir" ]]; then
            log_warn "Voice gateway venv path exists but is not a directory; rebuilding"
            rm -f "$venv_dir"
          fi
          if [[ -d "$venv_dir" && ( ! -f "$venv_dir/pyvenv.cfg" || ! -e "$venv_dir/bin" ) ]]; then
            log_warn "Voice gateway venv is incomplete; rebuilding with ${preferred_python}"
            rm -rf "$venv_dir"
          fi
          if [[ -x "$venv_dir/bin/python" ]]; then
            voice_python="$venv_dir/bin/python"
            venv_version="$("$voice_python" - <<'PY'
import sys
print(f"{sys.version_info[0]}.{sys.version_info[1]}")
PY
)"
            rebuild_venv=false
            if [[ "$venv_version" =~ ^3\.(1[3-9]|[4-9][0-9])$ ]]; then
              log_warn "Voice gateway venv uses Python ${venv_version} (silero VAD unsupported); rebuilding with ${preferred_python}"
              rebuild_venv=true
            elif ! "$voice_python" -m pip show livekit-plugins-silero >/dev/null 2>&1; then
              log_warn "Silero VAD not installed; rebuilding voice gateway venv with ${preferred_python}"
              rebuild_venv=true
            fi
            if [[ "$rebuild_venv" == "true" ]]; then
              rm -rf "$venv_dir"
            fi
          fi

          if [[ ! -x "$venv_dir/bin/python" ]]; then
            log_info "Creating voice gateway virtualenv at $venv_dir (python: $preferred_python)"
            "$preferred_python" -m venv "$venv_dir" || {
              log_error "Failed to create voice gateway virtualenv"
              exit 1
            }
          fi
          voice_python="$venv_dir/bin/python"

          # Install deps if needed
          if [[ -f "requirements.txt" ]]; then
            needs_install=false
            turn_detection_requested="$(printf '%s' "${VIVENTIUM_TURN_DETECTION:-}" | tr '[:upper:]' '[:lower:]')"
            wants_voice_turn_detector=false
            has_voice_turn_detector=false
            if [[ "${VIVENTIUM_STT_PROVIDER:-}" == "assemblyai" ]]; then
              case "$turn_detection_requested" in
                ""|turn_detector|semantic|semantic_turn_detector|multilingual)
                  wants_voice_turn_detector=true
                  ;;
              esac
            fi
            if ! "$voice_python" -m pip show livekit-agents >/dev/null 2>&1; then
              needs_install=true
            fi
            if ! "$voice_python" -m pip show livekit-plugins-elevenlabs >/dev/null 2>&1; then
              needs_install=true
            fi
            if [[ "${VIVENTIUM_STT_PROVIDER:-}" == "assemblyai" ]]; then
              if ! "$voice_python" -m pip show livekit-plugins-assemblyai >/dev/null 2>&1; then
                needs_install=true
              fi
            fi
            if [[ "${VIVENTIUM_STT_PROVIDER:-}" == "whisper_local" || "${VIVENTIUM_STT_PROVIDER:-}" == "pywhispercpp" ]]; then
              if ! "$voice_python" -m pip show pywhispercpp >/dev/null 2>&1; then
                needs_install=true
              fi
            fi
            if [[ "$wants_voice_turn_detector" == "true" ]]; then
              if ! "$voice_python" -m pip show livekit-plugins-turn-detector >/dev/null 2>&1; then
                needs_install=true
              fi
            fi
            if [[ "$needs_install" == "true" ]]; then
              echo -e "${YELLOW}[viventium]${NC} Installing voice gateway dependencies..."
              "$voice_python" -m pip install -r requirements.txt -q || {
                log_error "Voice gateway dependency install failed"
                exit 1
              }
            fi
            if "$voice_python" -m pip show livekit-plugins-turn-detector >/dev/null 2>&1; then
              has_voice_turn_detector=true
            fi
            if [[ "$has_voice_turn_detector" == "true" ]]; then
              if ! "$voice_python" - <<'PY' >/dev/null 2>&1
from huggingface_hub import hf_hub_download
from livekit.plugins.turn_detector.models import HG_MODEL, MODEL_REVISIONS, ONNX_FILENAME

revision = MODEL_REVISIONS["multilingual"]
hf_hub_download(
    HG_MODEL,
    ONNX_FILENAME,
    subfolder="onnx",
    revision=revision,
    local_files_only=True,
)
hf_hub_download(
    HG_MODEL,
    "languages.json",
    revision=revision,
    local_files_only=True,
)
PY
              then
                echo -e "${YELLOW}[viventium]${NC} Pre-downloading voice turn detector model..."
                "$voice_python" worker.py download-files >>"$LOG_DIR/voice_gateway_deps.log" 2>&1 || {
                  if [[ "$wants_voice_turn_detector" == "true" ]]; then
                    log_warn "Voice turn detector model pre-download failed; runtime will fall back to AssemblyAI STT endpointing if needed"
                  else
                    log_warn "Voice turn detector model pre-download failed; boot logs may still show plugin initialization errors until the cache is available"
                  fi
                }
              fi
            fi
          fi

          # === VIVENTIUM START ===
          # Feature: Optional local Chatterbox Turbo (MLX-Audio) deps + model prefetch.
          #
          # Purpose:
          # - When VIVENTIUM_TTS_PROVIDER=local_chatterbox_turbo_mlx_8bit, install MLX-Audio deps
          #   into the voice-gateway venv and prefetch the model weights into the HF cache.
          # - Keep main voice-gateway requirements compatible with Linux/Container Apps by keeping
          #   MLX deps in a separate requirements file.
          if [[ "${VIVENTIUM_TTS_PROVIDER:-}" == "local_chatterbox_turbo_mlx_8bit" ]]; then
            if ! host_supports_local_chatterbox_mlx; then
              fallback_provider="${VIVENTIUM_TTS_PROVIDER_FALLBACK:-openai}"
              if [[ -z "$fallback_provider" ]]; then
                fallback_provider="openai"
              fi
              export VIVENTIUM_TTS_PROVIDER="$fallback_provider"
              export TTS_PROVIDER_PRIMARY="$fallback_provider"
              log_warn "local_chatterbox_turbo_mlx_8bit selected but this host does not support MLX-Audio; using ${fallback_provider} instead"
            else
              mlx_req="requirements.mlx_audio_darwin.txt"
              if [[ -f "$mlx_req" ]]; then
                if ! "$voice_python" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("mlx_audio") else 1)
PY
                then
                  echo -e "${YELLOW}[viventium]${NC} Installing local MLX-Audio deps for Chatterbox Turbo..."
                  "$voice_python" -m pip install -r "$mlx_req" -q || {
                    log_error "MLX-Audio dependency install failed"
                    exit 1
                  }
                fi

                prefetch="${VIVENTIUM_LOCAL_TTS_PREFETCH:-1}"
                prefetch="$(echo "$prefetch" | tr '[:upper:]' '[:lower:]')"
                if [[ "$prefetch" != "0" && "$prefetch" != "false" && "$prefetch" != "off" && "$prefetch" != "no" ]]; then
                  model_id="${VIVENTIUM_MLX_AUDIO_MODEL_ID:-mlx-community/chatterbox-turbo-8bit}"
                  echo -e "${CYAN}[viventium]${NC} Prefetching Chatterbox model weights (model=${model_id})..."
                  VIVENTIUM_MLX_AUDIO_MODEL_ID="$model_id" "$voice_python" - <<'PY' || \
                    log_warn "Chatterbox model prefetch failed (will try again on first TTS request)"
import os
from mlx_audio.tts.utils import load_model
model_id = (os.getenv("VIVENTIUM_MLX_AUDIO_MODEL_ID") or "").strip() or "mlx-community/chatterbox-turbo-8bit"
load_model(model_id)
PY
                fi
              else
                log_warn "Missing $mlx_req; cannot install local chatterbox deps"
              fi
            fi
          fi
          # === VIVENTIUM END ===
        else
          if [[ -x "$venv_dir/bin/python" ]]; then
            voice_python="$venv_dir/bin/python"
          else
            log_warn "Voice gateway venv missing; using ${preferred_python} without dependency checks"
            voice_python="$preferred_python"
          fi
        fi
        export LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET
        export LIVEKIT_AGENT_NAME="$VIVENTIUM_VOICE_GATEWAY_AGENT_NAME"
        export VIVENTIUM_LIBRECHAT_ORIGIN VIVENTIUM_CALL_SESSION_SECRET
        # === VIVENTIUM START ===
        # Feature: Voice STT/VAD env passthrough (v1 parity)
        # === VIVENTIUM END ===
        export VIVENTIUM_STT_PROVIDER="${VIVENTIUM_STT_PROVIDER:-whisper_local}"
        export VIVENTIUM_VOICE_STT_PROVIDER="${VIVENTIUM_VOICE_STT_PROVIDER:-$VIVENTIUM_STT_PROVIDER}"
        if [[ -z "${VIVENTIUM_STT_MODEL:-}" ]]; then
          export VIVENTIUM_STT_MODEL="$(default_stt_model "$VIVENTIUM_STT_PROVIDER")"
        else
          export VIVENTIUM_STT_MODEL
        fi
        export VIVENTIUM_STT_LANGUAGE="${VIVENTIUM_STT_LANGUAGE:-en}"
        if [[ -z "${VIVENTIUM_STT_THREADS:-}" ]]; then
          export VIVENTIUM_STT_THREADS="$(default_stt_thread_count)"
        else
          export VIVENTIUM_STT_THREADS
        fi
        if [[ -z "${VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S:-}" ]]; then
          export VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S="$(default_voice_initialize_process_timeout "$VIVENTIUM_STT_PROVIDER")"
        else
          export VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S
        fi
        if [[ -z "${VIVENTIUM_VOICE_IDLE_PROCESSES:-}" ]]; then
          export VIVENTIUM_VOICE_IDLE_PROCESSES="$(default_voice_idle_processes "$VIVENTIUM_STT_PROVIDER")"
        else
          export VIVENTIUM_VOICE_IDLE_PROCESSES
        fi
        if [[ -z "${VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD:-}" ]]; then
          export VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD="$(default_voice_worker_load_threshold "$VIVENTIUM_STT_PROVIDER")"
        else
          export VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD
        fi
        export VIVENTIUM_STT_VAD_ACTIVATION="${VIVENTIUM_STT_VAD_ACTIVATION:-0.4}"
        export VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH="${VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH:-600}"
        export VIVENTIUM_STT_VAD_MIN_SILENCE="${VIVENTIUM_STT_VAD_MIN_SILENCE:-0.5}"
        export VIVENTIUM_STT_VAD_MIN_SPEECH="${VIVENTIUM_STT_VAD_MIN_SPEECH:-0.1}"
        export VIVENTIUM_STT_VAD_FORCE_CPU="${VIVENTIUM_STT_VAD_FORCE_CPU:-}"
        export ASSEMBLYAI_API_KEY="${ASSEMBLYAI_API_KEY:-}"
        # Voice configuration (ElevenLabs TTS - matching old viventium_v1 voice)
        export VIVENTIUM_TTS_PROVIDER="${VIVENTIUM_TTS_PROVIDER:-elevenlabs}"
        export VIVENTIUM_FC_CONSCIOUS_VOICE_ID="${VIVENTIUM_FC_CONSCIOUS_VOICE_ID:-CrmDm7REHG6iBx8uySLf}"
        # LiveKit ElevenLabs plugin uses ELEVEN_API_KEY (also support ELEVENLABS_API_KEY for compatibility)
        # Set ELEVEN_API_KEY from ELEVENLABS_API_KEY if not already set
        if [[ -z "${ELEVEN_API_KEY:-}" ]] && [[ -n "${ELEVENLABS_API_KEY:-}" ]]; then
          export ELEVEN_API_KEY="$ELEVENLABS_API_KEY"
        fi
        # Also export ELEVENLABS_API_KEY for backward compatibility
        export ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}"
        # xAI Grok Voice configuration (Available voices: Ara, Rex, Sal, Eve, Leo)
        export XAI_API_KEY="${XAI_API_KEY:-}"
        export VIVENTIUM_XAI_VOICE="${VIVENTIUM_XAI_VOICE:-Sal}"
        export VIVENTIUM_XAI_WSS_URL="${VIVENTIUM_XAI_WSS_URL:-wss://api.x.ai/v1/realtime}"
        export VIVENTIUM_XAI_SAMPLE_RATE="${VIVENTIUM_XAI_SAMPLE_RATE:-24000}"
        export VIVENTIUM_XAI_INSTRUCTIONS="${VIVENTIUM_XAI_INSTRUCTIONS:-}"
        # Cartesia Sonic-3 configuration
        export CARTESIA_API_KEY="${CARTESIA_API_KEY:-}"
        export VIVENTIUM_CARTESIA_API_URL="${VIVENTIUM_CARTESIA_API_URL:-https://api.cartesia.ai/tts/bytes}"
        export VIVENTIUM_CARTESIA_API_VERSION="${VIVENTIUM_CARTESIA_API_VERSION:-2025-04-16}"
        export VIVENTIUM_CARTESIA_MODEL_ID="${VIVENTIUM_CARTESIA_MODEL_ID:-sonic-3}"
        export VIVENTIUM_CARTESIA_VOICE_ID="${VIVENTIUM_CARTESIA_VOICE_ID:-e8e5fffb-252c-436d-b842-8879b84445b6}"
        export VIVENTIUM_CARTESIA_SAMPLE_RATE="${VIVENTIUM_CARTESIA_SAMPLE_RATE:-44100}"
        export VIVENTIUM_CARTESIA_SPEED="${VIVENTIUM_CARTESIA_SPEED:-1.0}"
        export VIVENTIUM_CARTESIA_VOLUME="${VIVENTIUM_CARTESIA_VOLUME:-1.0}"
        export VIVENTIUM_CARTESIA_EMOTION="${VIVENTIUM_CARTESIA_EMOTION:-neutral}"
        # Debug: Show what we're exporting
        if [[ -n "${ELEVEN_API_KEY:-}" ]]; then
          echo -e "${CYAN}[viventium]${NC} ELEVEN_API_KEY is set (${ELEVEN_API_KEY:0:8}...)"
        else
          echo -e "${YELLOW}[viventium]${NC} WARNING: ELEVEN_API_KEY not set - ElevenLabs TTS will fallback to OpenAI"
        fi
        if [[ -n "${XAI_API_KEY:-}" ]]; then
          echo -e "${CYAN}[viventium]${NC} XAI_API_KEY is set (${XAI_API_KEY:0:8}...) - xAI Grok Voice available"
        fi
        if [[ -n "${CARTESIA_API_KEY:-}" ]]; then
          echo -e "${CYAN}[viventium]${NC} CARTESIA_API_KEY is set (${CARTESIA_API_KEY:0:8}...) - Cartesia TTS available"
        fi
        exec "$voice_python" worker.py start \
          --log-level="$VIVENTIUM_VOICE_GATEWAY_LOG_LEVEL" \
          --url "$LIVEKIT_URL" \
          --api-key "$LIVEKIT_API_KEY" \
          --api-secret "$LIVEKIT_API_SECRET"
      ) >"$LOG_DIR/voice_gateway.log" 2>&1 &
      VOICE_GATEWAY_PID=$!
      VOICE_GATEWAY_STARTED_BY_SCRIPT=true
      echo -e "${GREEN}[viventium]${NC} Voice Gateway pid: $VOICE_GATEWAY_PID (log: $LOG_DIR/voice_gateway.log)"
    fi
  fi
fi

# Wait for services to start
if [[ "${#PARALLEL_OPTIONAL_START_PIDS[@]}" -gt 0 ]]; then
  if detached_start_requested; then
    log_info "Detached launch is still waiting for parallel optional sidecars before exiting"
  fi
  wait_for_parallel_optional_starts || true
fi
start_optional_docker_recovery_worker
sleep 3

if detached_start_requested; then
  start_detached_librechat_api_watchdog
  log_info "Skipping blocking post-start health checks for detached launch; detached watchdog will monitor LibreChat API health while helper/user surfaces monitor readiness"
elif [[ "$SKIP_HEALTH_CHECKS" != "true" ]]; then
  run_health_checks
else
  log_info "Skipping health checks"
fi

prewarm_remote_call_access

echo ""
if detached_start_requested; then
  echo -e "${YELLOW}========================================${NC}"
  echo -e "${YELLOW}  Detached Startup Submitted${NC}"
  echo -e "${YELLOW}========================================${NC}"
else
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  All Services Running${NC}"
  echo -e "${GREEN}========================================${NC}"
fi
echo ""
LOCAL_NETWORK_HOST="$(detect_livekit_node_ip)"
LOCAL_NETWORK_FRONTEND_URL=""
if [[ -n "$LOCAL_NETWORK_HOST" && "$LOCAL_NETWORK_HOST" != 127.0.0.1 ]]; then
  LOCAL_NETWORK_FRONTEND_URL="http://${LOCAL_NETWORK_HOST}:${LC_FRONTEND_PORT}"
fi
echo -e "  ${CYAN}LibreChat Frontend:${NC}  ${LC_FRONTEND_URL}"
if [[ -n "$LOCAL_NETWORK_FRONTEND_URL" ]]; then
  echo -e "  ${CYAN}Local Network URL:${NC}  ${LOCAL_NETWORK_FRONTEND_URL}"
fi
echo -e "  ${CYAN}LibreChat API:${NC}       ${LC_API_URL}/api"
if is_truthy "${SEARCH:-false}"; then
  echo -e "  ${CYAN}Conversation Search:${NC} enabled (${MEILI_HOST})"
fi
if [[ "$START_RAG_API" == "true" && -n "${RAG_API_URL:-}" ]]; then
  echo -e "  ${CYAN}Conversation Recall:${NC} ${RAG_API_URL}"
fi
echo -e "  ${CYAN}${PLAYGROUND_LABEL}:${NC}   $VIVENTIUM_PLAYGROUND_URL"
echo -e "  ${CYAN}LiveKit WS:${NC}          $LIVEKIT_URL"
echo -e "  ${CYAN}MS365 MCP:${NC}          $MS365_MCP_SERVER_URL"
echo -e "  ${CYAN}Google MCP:${NC}         $GOOGLE_WORKSPACE_MCP_URL"
echo -e "  ${CYAN}Code Interpreter:${NC}   $LIBRECHAT_CODE_BASEURL"
if [[ "$START_V1_AGENT" == "true" ]]; then
  if [[ "$V1_AGENT_STARTED_BY_SCRIPT" == "true" ]]; then
    echo -e "  ${CYAN}V1 Agent:${NC}            running (PID: $V1_AGENT_PID)"
  else
    echo -e "  ${CYAN}V1 Agent:${NC}            enabled (check $LOG_DIR/v1_agent.log)"
  fi
else
  echo -e "  ${CYAN}V1 Agent:${NC}            disabled"
fi
if [[ "$START_TELEGRAM" == "true" ]]; then
  if telegram_local_bot_api_enabled; then
    if telegram_local_bot_api_pid_is_running || telegram_local_bot_api_ready; then
      echo -e "  ${CYAN}Telegram Local API:${NC}  running"
    else
      echo -e "  ${CYAN}Telegram Local API:${NC}  enabled (check $TELEGRAM_LOCAL_BOT_API_LOG_FILE)"
    fi
  else
    echo -e "  ${CYAN}Telegram Local API:${NC}  disabled"
  fi
  if [[ -z "${BOT_TOKEN:-}" ]]; then
    echo -e "  ${CYAN}Telegram Bot:${NC}        BOT_TOKEN not set"
  elif ! telegram_bot_token_looks_valid "${BOT_TOKEN:-}"; then
    echo -e "  ${CYAN}Telegram Bot:${NC}        invalid BotFather token"
  elif [[ "$TELEGRAM_STARTED_BY_SCRIPT" == "true" ]]; then
    echo -e "  ${CYAN}Telegram Bot:${NC}        running (PID: $TELEGRAM_BOT_PID)"
  elif telegram_deferred_start_pending; then
    echo -e "  ${CYAN}Telegram Bot:${NC}        starting (waiting for LibreChat API)"
  else
    echo -e "  ${CYAN}Telegram Bot:${NC}        enabled (check $LOG_DIR/telegram_bot.log)"
  fi
else
  echo -e "  ${CYAN}Telegram Bot:${NC}        disabled"
fi
if [[ "$START_TELEGRAM_CODEX" == "true" ]]; then
  if [[ -z "${TELEGRAM_CODEX_BOT_TOKEN:-}" && ! -f "$TELEGRAM_CODEX_ENV_FILE" ]]; then
    echo -e "  ${CYAN}Telegram Codex:${NC}      TELEGRAM_CODEX_BOT_TOKEN not set"
  elif [[ -n "${TELEGRAM_CODEX_BOT_TOKEN:-}" ]] && ! telegram_bot_token_looks_valid "${TELEGRAM_CODEX_BOT_TOKEN:-}"; then
    echo -e "  ${CYAN}Telegram Codex:${NC}      invalid BotFather token"
  elif [[ "${TELEGRAM_CODEX_STARTED_BY_SCRIPT:-false}" == "true" ]]; then
    echo -e "  ${CYAN}Telegram Codex:${NC}      running (PID: $TELEGRAM_CODEX_PID)"
  else
    echo -e "  ${CYAN}Telegram Codex:${NC}      enabled (check $LOG_DIR/telegram_codex.log)"
  fi
else
  echo -e "  ${CYAN}Telegram Codex:${NC}      disabled"
fi
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Testing Voice Call Button${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "1. Open ${GREEN}${LC_FRONTEND_URL}${NC} in browser"
echo -e "2. Log in and select an ${GREEN}Agent${NC} conversation"
echo -e "3. Look for the ${GREEN}phone icon${NC} in the chat header"
echo -e "4. Click it to open the voice playground"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

if [[ "${VIVENTIUM_DETACHED_START:-false}" == "1" || "${VIVENTIUM_DETACHED_START:-false}" == "true" ]]; then
  CLEANUP_ENABLED=false
  log_success "Detached launch submitted; services will keep warming in the background"
  exit 0
fi

wait
