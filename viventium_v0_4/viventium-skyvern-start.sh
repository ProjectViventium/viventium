#!/usr/bin/env bash
#
# === VIVENTIUM START ===
# Skyvern Browser Agent: AI-powered browser automation with 85%+ success rate
# Added: 2026-01-28
#
# Documentation: docs/requirements_and_learnings/19_Browser_Agent_Skyvern.md
# Source: https://docs.skyvern.com
#
# Purpose:
# - Start Skyvern browser automation services
# - Provides computer vision-based web navigation
# - Integrates with LibreChat via official MCP server
#
# What it provides:
# - Skyvern API for browser task automation
# - Skyvern UI for watching tasks in real-time
# - Recording and artifacts of all browser sessions
#
# Usage:
#   ./viventium-skyvern-start.sh [command]
#
# Commands:
#   start            Start Skyvern services (default)
#   stop             Stop all Skyvern services
#   restart          Stop then start
#   status           Show status of Skyvern services
#   logs             Tail logs from Skyvern
#   init             Initialize/configure LLM settings
#   help             Show this help
#
# Environment Variables (set in .env.local):
#   SKYVERN_API_KEY                 - Local API key (shown in UI after first start)
#   VIVENTIUM_SKYVERN_LLM_KEY       - Requested upstream model (default: openai/gpt-5.4)
#   VIVENTIUM_SKYVERN_BRIDGE_API_KEY - Optional override for LibreChat Skyvern bridge auth
#
# Ports:
#   8000 - Skyvern API
#   8080 - Skyvern UI (watch tasks live)
#   9090 - Artifact API
#   9222 - CDP browser forwarding
#
# === VIVENTIUM END ===
#

set -euo pipefail

# Ensure Homebrew binaries are available in non-interactive shells.
if [[ -d "/opt/homebrew/bin" ]]; then
  export PATH="/opt/homebrew/bin:${PATH}"
fi
if [[ -d "/opt/homebrew/opt/node@20/bin" ]]; then
  export PATH="/opt/homebrew/opt/node@20/bin:${PATH}"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
PYTHON_BIN="${PYTHON_BIN:-python3}"
DOCKER_BIN="$(command -v docker || true)"

docker() {
  if [[ -z "$DOCKER_BIN" ]]; then
    echo "docker: command not found" >&2
    return 127
  fi

  local timeout_seconds="${VIVENTIUM_DOCKER_TIMEOUT_SECONDS:-180}"
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
        f"[skyvern] Docker command timed out after {timeout:.0f}s: {' '.join(args[1:])}\n"
    )
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIVENTIUM_CORE_DIR="$(dirname "$ROOT_DIR")"
VIVENTIUM_WORKSPACE_DIR="$(dirname "$VIVENTIUM_CORE_DIR")"
if [[ -f "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh" ]]; then
  # shellcheck source=/dev/null
  source "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh"
fi
if ! declare -F discover_private_repo_dir >/dev/null 2>&1; then
  path_is_git_repo_root() {
    local candidate="${1:-}"
    [[ -n "$candidate" && -d "$candidate" ]] || return 1
    local git_root=""
    git_root="$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "$git_root" ]] || return 1
    [[ "$(cd "$candidate" && pwd -P)" == "$(cd "$git_root" && pwd -P)" ]]
  }

  discover_private_repo_dir() {
    local workspace_root="$1"
    local repo_root="${2:-$workspace_root}"
    local candidate=""
    local candidates=(
      "$repo_root/private-companion-repo"
      "$repo_root/.private-companion-repo"
      "$workspace_root/private-companion-repo"
      "$workspace_root/.private-companion-repo"
    )
    for candidate in "${candidates[@]}"; do
      if path_is_git_repo_root "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
    return 1
  }
fi

VIVENTIUM_PRIVATE_REPO_DIR="${VIVENTIUM_PRIVATE_REPO_DIR:-$(discover_private_repo_dir "$VIVENTIUM_WORKSPACE_DIR" "$VIVENTIUM_CORE_DIR" || true)}"
if [[ -n "$VIVENTIUM_PRIVATE_REPO_DIR" ]]; then
  VIVENTIUM_PRIVATE_CURATED_DIR="${VIVENTIUM_PRIVATE_CURATED_DIR:-$VIVENTIUM_PRIVATE_REPO_DIR/curated}"
  VIVENTIUM_PRIVATE_MIRROR_DIR="${VIVENTIUM_PRIVATE_MIRROR_DIR:-$VIVENTIUM_PRIVATE_REPO_DIR/mirror}"
else
  VIVENTIUM_PRIVATE_CURATED_DIR="${VIVENTIUM_PRIVATE_CURATED_DIR:-}"
  VIVENTIUM_PRIVATE_MIRROR_DIR="${VIVENTIUM_PRIVATE_MIRROR_DIR:-}"
fi

resolve_path_or_default() {
  local fallback="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if [[ -n "$candidate" && -e "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf '%s\n' "$fallback"
}

resolve_dir_or_default() {
  local fallback="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if [[ -n "$candidate" && -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf '%s\n' "$fallback"
}

SKYVERN_DIR="$ROOT_DIR/docker/skyvern"
SKYVERN_ENV_FILE="${VIVENTIUM_SKYVERN_ENV_FILE:-$(resolve_path_or_default \
  "$SKYVERN_DIR/.env" \
  "$SKYVERN_DIR/.env" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/configs/skyvern/skyvern.env" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/.env")}"
SKYVERN_POSTGRES_DATA_DIR="${VIVENTIUM_SKYVERN_POSTGRES_DATA_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/postgres-data" \
  "$SKYVERN_DIR/postgres-data" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/postgres-data" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/postgres-data")}"
SKYVERN_STREAMLIT_DIR="${VIVENTIUM_SKYVERN_STREAMLIT_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/.streamlit" \
  "$SKYVERN_DIR/.streamlit" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/.streamlit" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/.streamlit")}"
SKYVERN_ARTIFACTS_DIR="${VIVENTIUM_SKYVERN_ARTIFACTS_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/artifacts" \
  "$SKYVERN_DIR/artifacts" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/artifacts" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/artifacts")}"
SKYVERN_VIDEOS_DIR="${VIVENTIUM_SKYVERN_VIDEOS_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/videos" \
  "$SKYVERN_DIR/videos" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/videos" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/videos")}"
SKYVERN_HAR_DIR="${VIVENTIUM_SKYVERN_HAR_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/har" \
  "$SKYVERN_DIR/har" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/har" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/har")}"
SKYVERN_LOG_DATA_DIR="${VIVENTIUM_SKYVERN_LOG_DIR:-$(resolve_dir_or_default \
  "$SKYVERN_DIR/log" \
  "$SKYVERN_DIR/log" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/skyvern/log" \
  "$VIVENTIUM_PRIVATE_MIRROR_DIR/viventium_v0_4/docker/skyvern/log")}"
LOG_ROOT="${VIVENTIUM_BASE_STATE_DIR:-$(resolve_dir_or_default \
  "$VIVENTIUM_CORE_DIR/.viventium" \
  "$VIVENTIUM_CORE_DIR/.viventium" \
  "$VIVENTIUM_PRIVATE_CURATED_DIR/runtime-state/.viventium" \
  "$VIVENTIUM_PRIVATE_REPO_DIR/.viventium")}"
LOG_DIR="$LOG_ROOT/logs"
SKYVERN_RECOVERY_DIR="$LOG_ROOT/skyvern-recovery"
export SKYVERN_ENV_FILE SKYVERN_POSTGRES_DATA_DIR SKYVERN_STREAMLIT_DIR SKYVERN_ARTIFACTS_DIR SKYVERN_VIDEOS_DIR SKYVERN_HAR_DIR SKYVERN_LOG_DATA_DIR

mkdir -p "$LOG_DIR"

# ----------------------------
# Helper functions
# ----------------------------
log_info() {
  echo -e "${CYAN}[skyvern]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[skyvern]${NC} $1"
}

log_error() {
  echo -e "${RED}[skyvern]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[skyvern]${NC} $1"
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

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

skyvern_compose() {
  (cd "$SKYVERN_DIR" && docker compose "$@")
}

upsert_env_kv() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file
  tmp_file="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "$file" >"$tmp_file"
  mv "$tmp_file" "$file"
}

ensure_skyvern_env_file() {
  mkdir -p "$SKYVERN_DIR"
  if [[ ! -f "$SKYVERN_ENV_FILE" ]]; then
    cat >"$SKYVERN_ENV_FILE" <<EOF
# Auto-generated by viventium-skyvern-start.sh for local setup.
ENABLE_OPENAI=false
ENABLE_ANTHROPIC=false
ENABLE_OPENAI_COMPATIBLE=true
OPENAI_COMPATIBLE_MODEL_KEY=OPENAI_COMPATIBLE
OPENAI_COMPATIBLE_MODEL_NAME=${SKYVERN_MODEL_NAME_RESOLVED:-openai/gpt-5.4}
OPENAI_COMPATIBLE_SUPPORTS_VISION=true
OPENAI_COMPATIBLE_API_BASE=${SKYVERN_BRIDGE_BASE_URL_RESOLVED:-http://host.docker.internal:3180/api/viventium/skyvern/openai/v1}
OPENAI_COMPATIBLE_API_KEY=${SKYVERN_BRIDGE_API_KEY_RESOLVED:-}
LLM_KEY=OPENAI_COMPATIBLE
LLM_CONFIG_TEMPERATURE=1
SKYVERN_API_PORT=${SKYVERN_API_PORT}
SKYVERN_UI_PORT=${SKYVERN_UI_PORT}
EOF
  fi

  upsert_env_kv "$SKYVERN_ENV_FILE" "ENABLE_OPENAI" "false"
  upsert_env_kv "$SKYVERN_ENV_FILE" "ENABLE_ANTHROPIC" "false"
  upsert_env_kv "$SKYVERN_ENV_FILE" "ENABLE_OPENAI_COMPATIBLE" "true"
  upsert_env_kv "$SKYVERN_ENV_FILE" "OPENAI_COMPATIBLE_MODEL_KEY" "OPENAI_COMPATIBLE"
  upsert_env_kv "$SKYVERN_ENV_FILE" "OPENAI_COMPATIBLE_MODEL_NAME" "${SKYVERN_MODEL_NAME_RESOLVED:-openai/gpt-5.4}"
  upsert_env_kv "$SKYVERN_ENV_FILE" "OPENAI_COMPATIBLE_SUPPORTS_VISION" "true"
  upsert_env_kv "$SKYVERN_ENV_FILE" "OPENAI_COMPATIBLE_API_BASE" "${SKYVERN_BRIDGE_BASE_URL_RESOLVED:-http://host.docker.internal:3180/api/viventium/skyvern/openai/v1}"
  upsert_env_kv "$SKYVERN_ENV_FILE" "OPENAI_COMPATIBLE_API_KEY" "${SKYVERN_BRIDGE_API_KEY_RESOLVED:-}"
  upsert_env_kv "$SKYVERN_ENV_FILE" "LLM_KEY" "OPENAI_COMPATIBLE"
  upsert_env_kv "$SKYVERN_ENV_FILE" "LLM_CONFIG_TEMPERATURE" "1"
  upsert_env_kv "$SKYVERN_ENV_FILE" "SKYVERN_API_PORT" "${SKYVERN_API_PORT}"
  upsert_env_kv "$SKYVERN_ENV_FILE" "SKYVERN_UI_PORT" "${SKYVERN_UI_PORT}"
  chmod 600 "$SKYVERN_ENV_FILE" >/dev/null 2>&1 || true
}

extract_connected_openai_token() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  if [[ ! -d "$ROOT_DIR/LibreChat" ]]; then
    return 1
  fi
  if [[ -z "${CREDS_KEY:-}" || -z "${CREDS_IV:-}" ]]; then
    return 1
  fi

  (
    cd "$ROOT_DIR/LibreChat"
    MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017/LibreChat}" \
    CREDS_KEY="${CREDS_KEY}" \
    CREDS_IV="${CREDS_IV}" \
    VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID="${VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID:-}" \
      node - <<'NODE'
const crypto = require('node:crypto');

let MongoClient;
let ObjectId;
try {
  ({ MongoClient, ObjectId } = require('mongodb'));
} catch {
  process.exit(0);
}

const mongoUri = process.env.MONGO_URI;
const credsKeyHex = process.env.CREDS_KEY || '';
const credsIvHex = process.env.CREDS_IV || '';
const preferredUserId = (process.env.VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID || '').trim();

if (!mongoUri || credsKeyHex.length === 0 || credsIvHex.length === 0) {
  process.exit(0);
}

let key;
let iv;
try {
  key = Buffer.from(credsKeyHex, 'hex');
  iv = Buffer.from(credsIvHex, 'hex');
} catch {
  process.exit(0);
}

if (key.length !== 32 || iv.length !== 16) {
  process.exit(0);
}

function decryptHex(cipherHex) {
  const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(cipherHex, 'hex')),
    decipher.final(),
  ]);
  return decrypted.toString('utf8');
}

function pickToken(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  if (payload.oauthProvider !== 'openai-codex') {
    return null;
  }
  if (typeof payload.apiKey === 'string' && payload.apiKey.length > 0) {
    return payload.apiKey;
  }
  return null;
}

async function main() {
  const client = new MongoClient(mongoUri);
  try {
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChat';
    const db = client.db(dbName);
    const keys = db.collection('keys');

    const docs = [];
    if (preferredUserId) {
      try {
        docs.push(
          ...(await keys
            .find({ name: 'openAI', userId: new ObjectId(preferredUserId) })
            .sort({ _id: -1 })
            .limit(5)
            .toArray()),
        );
      } catch {
        // Ignore malformed user id.
      }
    }

    if (docs.length === 0) {
      docs.push(...(await keys.find({ name: 'openAI' }).sort({ _id: -1 }).limit(25).toArray()));
    }

    for (const doc of docs) {
      if (!doc || typeof doc.value !== 'string' || doc.value.length === 0) {
        continue;
      }
      try {
        const decrypted = decryptHex(doc.value);
        const parsed = JSON.parse(decrypted);
        const token = pickToken(parsed);
        if (token) {
          process.stdout.write(token);
          return;
        }
      } catch {
        // Ignore malformed/legacy keys and continue.
      }
    }
  } finally {
    await client.close();
  }
}

main().catch(() => process.exit(0));
NODE
  ) 2>/dev/null || true
}

extract_connected_anthropic_token() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  if [[ ! -d "$ROOT_DIR/LibreChat" ]]; then
    return 1
  fi
  if [[ -z "${CREDS_KEY:-}" || -z "${CREDS_IV:-}" ]]; then
    return 1
  fi

  (
    cd "$ROOT_DIR/LibreChat"
    MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017/LibreChat}" \
    CREDS_KEY="${CREDS_KEY}" \
    CREDS_IV="${CREDS_IV}" \
    VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID="${VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID:-}" \
      node - <<'NODE'
const crypto = require('node:crypto');

let MongoClient;
let ObjectId;
try {
  ({ MongoClient, ObjectId } = require('mongodb'));
} catch {
  process.exit(0);
}

const mongoUri = process.env.MONGO_URI;
const credsKeyHex = process.env.CREDS_KEY || '';
const credsIvHex = process.env.CREDS_IV || '';
const preferredUserId = (process.env.VIVENTIUM_SKYVERN_CONNECTED_ACCOUNT_USER_ID || '').trim();

if (!mongoUri || credsKeyHex.length === 0 || credsIvHex.length === 0) {
  process.exit(0);
}

let key;
let iv;
try {
  key = Buffer.from(credsKeyHex, 'hex');
  iv = Buffer.from(credsIvHex, 'hex');
} catch {
  process.exit(0);
}

if (key.length !== 32 || iv.length !== 16) {
  process.exit(0);
}

function decryptHex(cipherHex) {
  const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(cipherHex, 'hex')),
    decipher.final(),
  ]);
  return decrypted.toString('utf8');
}

function pickToken(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  if (payload.oauthProvider !== 'anthropic' || payload.oauthType !== 'subscription') {
    return null;
  }
  if (typeof payload.authToken === 'string' && payload.authToken.length > 0) {
    return payload.authToken;
  }
  if (typeof payload.apiKey === 'string' && payload.apiKey.length > 0) {
    return payload.apiKey;
  }
  return null;
}

async function main() {
  const client = new MongoClient(mongoUri);
  try {
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChat';
    const db = client.db(dbName);
    const keys = db.collection('keys');

    const docs = [];
    if (preferredUserId) {
      try {
        docs.push(
          ...(await keys
            .find({ name: 'anthropic', userId: new ObjectId(preferredUserId) })
            .sort({ _id: -1 })
            .limit(5)
            .toArray()),
        );
      } catch {
        // Ignore malformed user id.
      }
    }

    if (docs.length === 0) {
      docs.push(...(await keys.find({ name: 'anthropic' }).sort({ _id: -1 }).limit(25).toArray()));
    }

    for (const doc of docs) {
      if (!doc || typeof doc.value !== 'string' || doc.value.length === 0) {
        continue;
      }
      try {
        const decrypted = decryptHex(doc.value);
        const parsed = JSON.parse(decrypted);
        const token = pickToken(parsed);
        if (token) {
          process.stdout.write(token);
          return;
        }
      } catch {
        // Ignore malformed/legacy keys and continue.
      }
    }
  } finally {
    await client.close();
  }
}

main().catch(() => process.exit(0));
NODE
  ) 2>/dev/null || true
}

resolve_skyvern_llm_profile() {
  SKYVERN_MODEL_NAME_RESOLVED="${VIVENTIUM_SKYVERN_LLM_KEY:-openai/gpt-5.4}"
  SKYVERN_LLM_KEY_RESOLVED="OPENAI_COMPATIBLE"
  SKYVERN_BRIDGE_API_KEY_RESOLVED="${VIVENTIUM_SKYVERN_BRIDGE_API_KEY:-${SKYVERN_API_KEY:-}}"
  SKYVERN_BRIDGE_BASE_URL_RESOLVED="${VIVENTIUM_SKYVERN_BRIDGE_BASE_URL:-http://host.docker.internal:${VIVENTIUM_LC_API_PORT:-${PORT:-3180}}/api/viventium/skyvern/openai/v1}"
  SKYVERN_LLM_SOURCE="none"
  local normalized_model="${SKYVERN_MODEL_NAME_RESOLVED#openai/}"
  local requested_provider="openai"
  if [[ "$normalized_model" == anthropic/* || "$normalized_model" == claude* ]]; then
    requested_provider="anthropic"
  fi

  if [[ "$requested_provider" == "anthropic" ]]; then
    if is_truthy "${VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH:-false}" &&
      ! is_truthy "${VIVENTIUM_SKYVERN_DISABLE_CONNECTED_ACCOUNT_BRIDGE:-false}" &&
      [[ -n "$(extract_connected_anthropic_token)" ]]; then
      SKYVERN_LLM_SOURCE="anthropic connected account via LibreChat bridge"
    elif [[ -n "${VIVENTIUM_ANTHROPIC_DIRECT_API_KEY:-}" &&
      "${VIVENTIUM_ANTHROPIC_DIRECT_API_KEY}" != "user_provided" ]]; then
      SKYVERN_LLM_SOURCE="VIVENTIUM_ANTHROPIC_DIRECT_API_KEY via LibreChat bridge"
    elif [[ -n "${ANTHROPIC_API_KEY:-}" && "${ANTHROPIC_API_KEY}" != "user_provided" ]]; then
      SKYVERN_LLM_SOURCE="ANTHROPIC_API_KEY via LibreChat bridge"
    fi
  else
    if is_truthy "${VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH:-false}" &&
      ! is_truthy "${VIVENTIUM_SKYVERN_DISABLE_CONNECTED_ACCOUNT_BRIDGE:-false}" &&
      [[ -n "$(extract_connected_openai_token)" ]]; then
      SKYVERN_LLM_SOURCE="openai connected account via LibreChat bridge"
    elif [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "user_provided" ]]; then
      SKYVERN_LLM_SOURCE="OPENAI_API_KEY via LibreChat bridge"
    fi
  fi

  export SKYVERN_LLM_KEY_RESOLVED
  export SKYVERN_MODEL_NAME_RESOLVED
  export SKYVERN_BRIDGE_API_KEY_RESOLVED
  export SKYVERN_BRIDGE_BASE_URL_RESOLVED
}

postgres_container_id() {
  docker ps -aq --filter "name=^/viventium-skyvern-postgres$" 2>/dev/null | head -1
}

postgres_status_summary() {
  local container_id
  container_id="$(postgres_container_id)"
  if [[ -z "$container_id" ]]; then
    echo "missing"
    return 0
  fi

  local state health
  state="$(docker inspect -f '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || true)"
  if [[ -z "$state" ]]; then
    echo "unknown"
    return 0
  fi
  if [[ "$health" == "none" ]]; then
    echo "$state"
    return 0
  fi
  echo "${state}/${health}"
}

wait_for_postgres_healthy() {
  local timeout="${1:-45}"
  local attempts=0
  while [[ "$attempts" -lt "$timeout" ]]; do
    local summary
    summary="$(postgres_status_summary)"
    if [[ "$summary" == "running/healthy" || "$summary" == "running" ]]; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 1
  done
  return 1
}

postgres_logs_indicate_corruption() {
  local logs
  logs="$(skyvern_compose logs --no-color --tail=160 postgres 2>/dev/null || true)"
  [[ "$logs" == *'could not open directory "pg_notify"'* ]] ||
    [[ "$logs" == *'could not open directory "pg_stat"'* ]] ||
    [[ "$logs" == *'could not open directory "pg_stat_tmp"'* ]] ||
    [[ "$logs" == *"database files are incompatible"* ]] ||
    [[ "$logs" == *"could not locate required checkpoint record"* ]]
}

recover_skyvern_postgres_data() {
  local timestamp backup_dir
  timestamp="$(date +%Y%m%dT%H%M%S)"
  backup_dir="$SKYVERN_RECOVERY_DIR/postgres-data-corrupt-${timestamp}"
  mkdir -p "$SKYVERN_RECOVERY_DIR"

  skyvern_compose down >/dev/null 2>&1 || true

  if [[ -d "$SKYVERN_POSTGRES_DATA_DIR" ]]; then
    mv "$SKYVERN_POSTGRES_DATA_DIR" "$backup_dir"
    log_warn "Backed up corrupt Skyvern PostgreSQL data to $backup_dir"
  fi

  mkdir -p "$SKYVERN_POSTGRES_DATA_DIR"
}

skyvern_api_ready() {
  local endpoint
  local status
  local endpoints=(
    "/api/v1/health"
    "/docs"
    "/openapi.json"
  )
  for endpoint in "${endpoints[@]}"; do
    status="$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${SKYVERN_API_PORT}${endpoint}" || true)"
    if [[ "$status" =~ ^2 ]]; then
      return 0
    fi
  done
  return 1
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
      # Skip readonly bash variables
      [[ "$key" == "UID" || "$key" == "EUID" || "$key" == "PPID" || "$key" == "BASHPID" ]] && continue
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
# Also load LibreChat .env for Azure AI Foundry credentials
if [[ -f "$ROOT_DIR/LibreChat/.env" ]]; then
  load_env_file "$ROOT_DIR/LibreChat/.env"
fi

# ----------------------------
# Defaults
# ----------------------------
export SKYVERN_API_PORT="${SKYVERN_API_PORT:-${VIVENTIUM_SKYVERN_API_PORT:-8000}}"
export SKYVERN_UI_PORT="${SKYVERN_UI_PORT:-${VIVENTIUM_SKYVERN_UI_PORT:-8080}}"

# ----------------------------
# Show help
# ----------------------------
show_help() {
  echo ""
  echo -e "${CYAN}Skyvern Browser Agent${NC}"
  echo ""
  echo "Usage: $0 [command]"
  echo ""
  echo "Commands:"
  echo "  start     Start Skyvern services (default if no command given)"
  echo "  stop      Stop all Skyvern services"
  echo "  restart   Stop then start services"
  echo "  status    Show status of Skyvern services"
  echo "  logs      Tail logs from Skyvern"
  echo "  init      Initialize/configure LLM settings"
  echo "  help      Show this help"
  echo ""
  echo "What it provides:"
  echo "  - Skyvern API for browser task automation (85%+ success rate)"
  echo "  - Skyvern UI for watching tasks in real-time"
  echo "  - Computer vision-based web navigation"
  echo "  - Recording of all browser sessions"
  echo ""
  echo "After first start:"
  echo "  1. Open http://localhost:$SKYVERN_UI_PORT"
  echo "  2. Go to Settings to get your local API key"
  echo "  3. Add SKYVERN_API_KEY to .env.local"
  echo ""
  echo "In LibreChat:"
  echo "  1. Click 'Integrations' in chat input"
  echo "  2. Find 'skyvern' and click 'Initialize'"
  echo "  3. Use: 'Go to website X and do Y'"
  echo ""
}

# ----------------------------
# Status
# ----------------------------
show_status() {
  require_docker
  
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  Skyvern Browser Agent Status${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""
  
  # Check Skyvern API
  local skyvern_container
  skyvern_container=$(docker ps -q --filter "name=viventium-skyvern$" 2>/dev/null || true)
  if [[ -n "$skyvern_container" ]]; then
    log_success "Skyvern API: running on port $SKYVERN_API_PORT"
    
    # Check if API is responding
    if skyvern_api_ready; then
      log_success "API Health: healthy"
    else
      log_warn "API Health: not ready yet (may still be starting)"
    fi
  else
    log_warn "Skyvern API: not running"
  fi
  
  # Check Skyvern UI
  local ui_container
  ui_container=$(docker ps -q --filter "name=viventium-skyvern-ui" 2>/dev/null || true)
  if [[ -n "$ui_container" ]]; then
    log_success "Skyvern UI: running on port $SKYVERN_UI_PORT"
  else
    log_warn "Skyvern UI: not running"
  fi
  
  # Check PostgreSQL
  local pg_summary
  pg_summary="$(postgres_status_summary)"
  if [[ "$pg_summary" == "running/healthy" || "$pg_summary" == "running" ]]; then
    log_success "PostgreSQL: $pg_summary"
  elif [[ "$pg_summary" == "missing" ]]; then
    log_warn "PostgreSQL: not running"
  else
    log_warn "PostgreSQL: $pg_summary"
  fi
  
  # Show API key status
  if [[ -n "${SKYVERN_API_KEY:-}" ]]; then
    log_success "SKYVERN_API_KEY: configured"
  else
    log_warn "SKYVERN_API_KEY: not set (get from http://localhost:$SKYVERN_UI_PORT/settings)"
  fi
  
  echo ""
  echo "URLs:"
  echo "  Skyvern UI:     http://localhost:$SKYVERN_UI_PORT"
  echo "  Skyvern API:    http://localhost:$SKYVERN_API_PORT"
  echo "  API Probe:      http://localhost:$SKYVERN_API_PORT/docs"
  echo ""
}

# ----------------------------
# Show logs
# ----------------------------
show_logs() {
  require_docker
  
  local skyvern_container
  skyvern_container=$(docker ps -q --filter "name=viventium-skyvern$" 2>/dev/null || true)
  if [[ -n "$skyvern_container" ]]; then
    docker logs -f "$skyvern_container"
  else
    log_error "Skyvern not running. Start it first with: $0 start"
    exit 1
  fi
}

# ----------------------------
# Stop services
# ----------------------------
stop_services() {
  require_docker
  
  log_warn "Stopping Skyvern services..."
  
  skyvern_compose down 2>/dev/null || true
  
  log_success "Skyvern services stopped"
}

# ----------------------------
# Initialize LLM settings
# ----------------------------
init_llm() {
  log_info "Installing Skyvern Python SDK..."
  pip install -q skyvern 2>/dev/null || pip3 install -q skyvern 2>/dev/null
  
  log_info "Running Skyvern LLM configuration wizard..."
  echo ""
  echo "This will help you configure which LLM to use with Skyvern."
  echo "Options include: OpenAI GPT-4o, Anthropic Claude, Azure OpenAI, Ollama"
  echo ""
  
  skyvern init llm
}

# ----------------------------
# Start services
# ----------------------------
start_services() {
  require_docker

  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  Skyvern Browser Agent${NC}"
  echo -e "${CYAN}  AI Browser Automation (85%+ success)${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo ""

  resolve_skyvern_llm_profile
  ensure_skyvern_env_file

  # Show configuration
  echo -e "Configuration:"
  echo -e "  API Port:      ${GREEN}$SKYVERN_API_PORT${NC}"
  echo -e "  UI Port:       ${GREEN}$SKYVERN_UI_PORT${NC}"
  echo -e "  LLM Key:       ${GREEN}${SKYVERN_LLM_KEY_RESOLVED}${NC}"
  echo -e "  Model:         ${GREEN}${SKYVERN_MODEL_NAME_RESOLVED}${NC}"
  echo -e "  Bridge URL:    ${GREEN}${SKYVERN_BRIDGE_BASE_URL_RESOLVED}${NC}"
  echo -e "  LLM Auth Src:  ${GREEN}${SKYVERN_LLM_SOURCE}${NC}"
  if [[ -n "${SKYVERN_API_KEY:-}" ]]; then
    echo -e "  Skyvern Key:   ${GREEN}${SKYVERN_API_KEY:0:8}...${NC}"
  else
    echo -e "  Skyvern Key:   ${YELLOW}(get from UI after first start)${NC}"
  fi
  echo ""

  if [[ -z "${SKYVERN_BRIDGE_API_KEY_RESOLVED:-}" ]]; then
    log_warn "No Skyvern bridge credential resolved."
    log_warn "Set SKYVERN_API_KEY or VIVENTIUM_SKYVERN_BRIDGE_API_KEY in .env.local."
    echo ""
  fi

  if [[ "$SKYVERN_LLM_SOURCE" == "none" ]]; then
    log_warn "No upstream model auth source resolved for the requested Skyvern model."
    log_warn "Reconnect the matching connected account or set the explicit provider key locally."
    echo ""
  fi

  # Check if already running
  local skyvern_container
  skyvern_container=$(docker ps -q --filter "name=viventium-skyvern$" 2>/dev/null || true)
  if [[ -n "$skyvern_container" ]]; then
    log_success "Skyvern already running"
    show_final_status
    return 0
  fi

  export SKYVERN_LLM_KEY_RESOLVED="${SKYVERN_LLM_KEY_RESOLVED:-OPENAI_COMPATIBLE}"
  export SKYVERN_MODEL_NAME_RESOLVED="${SKYVERN_MODEL_NAME_RESOLVED:-openai/gpt-5.4}"
  export SKYVERN_BRIDGE_API_KEY_RESOLVED="${SKYVERN_BRIDGE_API_KEY_RESOLVED:-}"
  export SKYVERN_BRIDGE_BASE_URL_RESOLVED="${SKYVERN_BRIDGE_BASE_URL_RESOLVED:-http://host.docker.internal:3180/api/viventium/skyvern/openai/v1}"

  # Start services
  log_info "Starting Skyvern services..."
  local initial_compose_failed=false
  if ! skyvern_compose up -d; then
    initial_compose_failed=true
  fi

  if [[ "$initial_compose_failed" == "true" ]] || ! wait_for_postgres_healthy 45; then
    if postgres_logs_indicate_corruption; then
      log_warn "Detected corrupted Skyvern PostgreSQL state. Recovering local DB volume..."
      recover_skyvern_postgres_data
      log_info "Restarting Skyvern services after PostgreSQL recovery..."
      if ! skyvern_compose up -d; then
        log_error "Skyvern failed to restart after PostgreSQL recovery"
        return 1
      fi
      if ! wait_for_postgres_healthy 45; then
        log_error "Skyvern PostgreSQL did not become healthy after recovery"
        return 1
      fi
      log_success "Skyvern PostgreSQL recovered"
    else
      log_error "Skyvern PostgreSQL failed to become healthy"
      return 1
    fi
  fi

  # Wait for Skyvern to be ready
  log_info "Waiting for Skyvern to initialize (this may take 30-60 seconds on first start)..."
  local attempts=0
  local max_attempts=90
  while [[ $attempts -lt $max_attempts ]]; do
    # Check if the private Streamlit config file exists (Skyvern's health check)
    local skyvern_streamlit_file="/app/.streamlit/secret"
    skyvern_streamlit_file="${skyvern_streamlit_file}s.toml"
    if docker exec viventium-skyvern test -f "$skyvern_streamlit_file" 2>/dev/null; then
      # Also check API health
      if skyvern_api_ready; then
        log_success "Skyvern API ready"
        break
      fi
    fi
    attempts=$((attempts + 1))
    echo -ne "\r  Waiting... ${attempts}s"
    sleep 1
  done
  echo ""
  
  if [[ $attempts -ge $max_attempts ]]; then
    log_error "Skyvern did not become ready in time. Check logs with: $0 logs"
    return 1
  fi

  show_final_status
}

show_final_status() {
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  Skyvern Browser Agent Running${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""
  echo -e "  ${CYAN}Skyvern UI:${NC}      http://localhost:$SKYVERN_UI_PORT"
  echo -e "  ${CYAN}Skyvern API:${NC}     http://localhost:$SKYVERN_API_PORT"
  echo -e "  ${CYAN}API Probe:${NC}       http://localhost:$SKYVERN_API_PORT/docs"
  echo ""
  
  if [[ -z "${SKYVERN_API_KEY:-}" ]]; then
    echo -e "${YELLOW}NEXT STEP:${NC}"
    echo "  1. Open http://localhost:$SKYVERN_UI_PORT"
    echo "  2. Go to Settings and copy your API key"
    echo "  3. Add to .env.local: SKYVERN_API_KEY=your_key"
    echo ""
  fi
  
  echo -e "${CYAN}In LibreChat:${NC}"
  echo "  1. Click 'Integrations' button in chat input"
  echo "  2. Find 'skyvern' and click 'Initialize'"
  echo "  3. Status should change to 'Connected'"
  echo ""
  echo -e "${CYAN}Try:${NC}"
  echo "  'Go to hackernews.com and get the top 3 posts with their titles and points'"
  echo ""
  echo -e "${YELLOW}Commands:${NC}"
  echo "  $0 status    Show service status"
  echo "  $0 logs      Tail Skyvern logs"
  echo "  $0 stop      Stop Skyvern services"
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
  init)
    init_llm
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
