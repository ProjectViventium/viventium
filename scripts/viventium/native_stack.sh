#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

APP_SUPPORT_DIR="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
STATE_DIR="${VIVENTIUM_BASE_STATE_DIR:-$APP_SUPPORT_DIR/state}"
LOG_DIR="${APP_SUPPORT_DIR}/logs"
NATIVE_STATE_DIR="${STATE_DIR}/native"
NATIVE_LOG_DIR="${LOG_DIR}/native"
VIVENTIUM_RUNTIME_PROFILE="${VIVENTIUM_RUNTIME_PROFILE:-compat}"
PROFILE_STATE_DIR="${STATE_DIR}/runtime/${VIVENTIUM_RUNTIME_PROFILE}"

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
    local iface candidate
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
}

MONGO_PORT="${VIVENTIUM_LOCAL_MONGO_PORT:-27117}"
MONGO_DB="${VIVENTIUM_LOCAL_MONGO_DB:-LibreChatViventium}"
MONGO_HOST="${MONGO_HOST:-127.0.0.1}"
LEGACY_MONGO_DATA_DIR="${STATE_DIR}/mongo-data"
if [[ -n "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-}" ]]; then
  MONGO_DATA_DIR="${VIVENTIUM_LOCAL_MONGO_DATA_PATH}"
elif [[ -d "${PROFILE_STATE_DIR}/mongo-data" ]]; then
  MONGO_DATA_DIR="${PROFILE_STATE_DIR}/mongo-data"
elif [[ -d "${LEGACY_MONGO_DATA_DIR}" ]]; then
  MONGO_DATA_DIR="${LEGACY_MONGO_DATA_DIR}"
else
  MONGO_DATA_DIR="${PROFILE_STATE_DIR}/mongo-data"
fi
MONGO_PID_FILE="$NATIVE_STATE_DIR/mongod.pid"
MONGO_LOG_FILE="$NATIVE_LOG_DIR/mongod.log"

MEILI_PORT="${VIVENTIUM_LOCAL_MEILI_PORT:-7700}"
MEILI_HOST="${MEILI_BIND_HOST:-127.0.0.1}"
LEGACY_MEILI_DATA_DIR="${STATE_DIR}/meili-data"
if [[ -n "${VIVENTIUM_LOCAL_MEILI_DATA_PATH:-}" ]]; then
  MEILI_DATA_DIR="${VIVENTIUM_LOCAL_MEILI_DATA_PATH}"
elif [[ -d "${PROFILE_STATE_DIR}/meili-data" ]]; then
  MEILI_DATA_DIR="${PROFILE_STATE_DIR}/meili-data"
elif [[ -d "${LEGACY_MEILI_DATA_DIR}" ]]; then
  MEILI_DATA_DIR="${LEGACY_MEILI_DATA_DIR}"
else
  MEILI_DATA_DIR="${PROFILE_STATE_DIR}/meili-data"
fi
if [[ -d "${MEILI_DATA_DIR}/data.ms" && ! -f "${MEILI_DATA_DIR}/VERSION" ]]; then
  MEILI_DATA_DIR="${MEILI_DATA_DIR}/data.ms"
fi
MEILI_LOG_FILE="$NATIVE_LOG_DIR/meilisearch.log"
MEILI_PID_FILE="$NATIVE_STATE_DIR/meilisearch.pid"
if [[ -z "${MEILI_MASTER_KEY:-}" ]]; then
  if [[ -n "${VIVENTIUM_LOCAL_MEILI_MASTER_KEY:-}" ]]; then
    MEILI_MASTER_KEY="${VIVENTIUM_LOCAL_MEILI_MASTER_KEY}"
  elif [[ -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
    MEILI_MASTER_KEY="${VIVENTIUM_CALL_SESSION_SECRET}"
  elif command -v python3 >/dev/null 2>&1; then
    MEILI_MASTER_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  elif command -v openssl >/dev/null 2>&1; then
    MEILI_MASTER_KEY="$(openssl rand -hex 32 2>/dev/null | tr -d '\n')"
  else
    MEILI_MASTER_KEY="viventium-local-meili"
  fi
fi

LIVEKIT_HTTP_PORT="${LIVEKIT_HTTP_PORT:-7880}"
LIVEKIT_TCP_PORT="${LIVEKIT_TCP_PORT:-7881}"
LIVEKIT_UDP_PORT="${LIVEKIT_UDP_PORT:-7882}"
LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:${LIVEKIT_HTTP_PORT}}"
LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-devkey}"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-secret}"
if [[ "${VIVENTIUM_RUNTIME_PROFILE}" == "isolated" && -n "${VIVENTIUM_CALL_SESSION_SECRET:-}" ]]; then
  if [[ "${LIVEKIT_API_KEY}" == "devkey" ]]; then
    LIVEKIT_API_KEY="viventium-local"
  fi
  if [[ "${LIVEKIT_API_SECRET}" == "secret" ]]; then
    LIVEKIT_API_SECRET="${VIVENTIUM_CALL_SESSION_SECRET}"
  fi
fi
LIVEKIT_NODE_IP="${LIVEKIT_NODE_IP:-$(detect_livekit_node_ip)}"
LIVEKIT_CFG_DIR="${VIVENTIUM_LIVEKIT_CFG_DIR:-$PROFILE_STATE_DIR/livekit}"
LIVEKIT_CFG_FILE="$LIVEKIT_CFG_DIR/livekit.yaml"
LIVEKIT_PID_FILE="$NATIVE_STATE_DIR/livekit.pid"
LIVEKIT_META_FILE="$NATIVE_STATE_DIR/livekit.runtime.env"
LIVEKIT_LOG_FILE="$NATIVE_LOG_DIR/livekit.log"
LIVEKIT_TURN_DOMAIN="${LIVEKIT_TURN_DOMAIN:-}"
LIVEKIT_TURN_TLS_PORT="${LIVEKIT_TURN_TLS_PORT:-}"
LIVEKIT_TURN_CERT_FILE="${LIVEKIT_TURN_CERT_FILE:-}"
LIVEKIT_TURN_KEY_FILE="${LIVEKIT_TURN_KEY_FILE:-}"
NATIVE_STACK_SKIP_LIVEKIT="${VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT:-0}"
VOICE_ENABLED="${VIVENTIUM_VOICE_ENABLED:-true}"

mkdir -p "$NATIVE_STATE_DIR" "$NATIVE_LOG_DIR" "$PROFILE_STATE_DIR" "$MONGO_DATA_DIR" "$MEILI_DATA_DIR" "$LIVEKIT_CFG_DIR"

port_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

listener_pid() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1 || true
}

process_command_line() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

wait_for_port() {
  local port="$1"
  local label="$2"
  local attempts="${3:-60}"
  local sleep_s="${4:-1}"

  for _ in $(seq 1 "$attempts"); do
    if port_listening "$port"; then
      echo "[native] ${label} listening on ${port}"
      return 0
    fi
    sleep "$sleep_s"
  done

  echo "[native] ERROR: ${label} did not start on port ${port}" >&2
  return 1
}

write_pid() {
  local pid="$1"
  local path="$2"
  printf '%s\n' "$pid" >"$path"
}

stop_pid() {
  local pid="$1"
  local label="$2"
  if [[ -z "$pid" ]]; then
    return 0
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "[native] Stopping ${label} (${pid})"
    kill "$pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
}

stop_pid_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  local pid
  pid="$(tr -d '[:space:]' <"$path" || true)"
  stop_pid "$pid" "$label"
  rm -f "$path"
}

write_livekit_runtime_meta() {
  cat >"$LIVEKIT_META_FILE" <<EOF
LIVEKIT_NODE_IP=${LIVEKIT_NODE_IP}
LIVEKIT_HTTP_PORT=${LIVEKIT_HTTP_PORT}
LIVEKIT_TCP_PORT=${LIVEKIT_TCP_PORT}
LIVEKIT_UDP_PORT=${LIVEKIT_UDP_PORT}
LIVEKIT_TURN_DOMAIN=${LIVEKIT_TURN_DOMAIN}
LIVEKIT_TURN_TLS_PORT=${LIVEKIT_TURN_TLS_PORT}
LIVEKIT_TURN_CERT_FILE=${LIVEKIT_TURN_CERT_FILE}
LIVEKIT_TURN_KEY_FILE=${LIVEKIT_TURN_KEY_FILE}
EOF
}

livekit_meta_matches_expected() {
  if [[ ! -f "$LIVEKIT_META_FILE" ]]; then
    return 1
  fi
  local actual_node_ip actual_http_port actual_tcp_port actual_udp_port
  local actual_turn_domain actual_turn_tls_port actual_turn_cert_file actual_turn_key_file
  actual_node_ip="$(grep '^LIVEKIT_NODE_IP=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_http_port="$(grep '^LIVEKIT_HTTP_PORT=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_tcp_port="$(grep '^LIVEKIT_TCP_PORT=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_udp_port="$(grep '^LIVEKIT_UDP_PORT=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_turn_domain="$(grep '^LIVEKIT_TURN_DOMAIN=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_turn_tls_port="$(grep '^LIVEKIT_TURN_TLS_PORT=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_turn_cert_file="$(grep '^LIVEKIT_TURN_CERT_FILE=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  actual_turn_key_file="$(grep '^LIVEKIT_TURN_KEY_FILE=' "$LIVEKIT_META_FILE" | head -1 | cut -d= -f2- || true)"
  [[ "$actual_node_ip" == "$LIVEKIT_NODE_IP" ]] &&
    [[ "$actual_http_port" == "$LIVEKIT_HTTP_PORT" ]] &&
    [[ "$actual_tcp_port" == "$LIVEKIT_TCP_PORT" ]] &&
    [[ "$actual_udp_port" == "$LIVEKIT_UDP_PORT" ]] &&
    [[ "$actual_turn_domain" == "$LIVEKIT_TURN_DOMAIN" ]] &&
    [[ "$actual_turn_tls_port" == "$LIVEKIT_TURN_TLS_PORT" ]] &&
    [[ "$actual_turn_cert_file" == "$LIVEKIT_TURN_CERT_FILE" ]] &&
    [[ "$actual_turn_key_file" == "$LIVEKIT_TURN_KEY_FILE" ]]
}

livekit_command_matches_expected() {
  local pid="$1"
  local command_line
  command_line="$(process_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1
  [[ "$command_line" == *"$LIVEKIT_CFG_FILE"* ]] || return 1
  [[ "$command_line" == *"--node-ip"*"$LIVEKIT_NODE_IP"* ]] || return 1
}

managed_livekit_listener_pid() {
  local pid command_line
  pid="$(listener_pid "$LIVEKIT_HTTP_PORT")"
  [[ -n "$pid" ]] || return 1
  command_line="$(process_command_line "$pid")"
  [[ "$command_line" == *"livekit"* ]] || return 1
  [[ "$command_line" == *"$LIVEKIT_CFG_FILE"* ]] || return 1
  printf '%s\n' "$pid"
}

stop_livekit() {
  stop_pid_file "$LIVEKIT_PID_FILE" "LiveKit"
  local pid
  pid="$(managed_livekit_listener_pid || true)"
  if [[ -n "$pid" ]]; then
    stop_pid "$pid" "LiveKit"
  fi
  rm -f "$LIVEKIT_META_FILE"
}

ensure_brew_pkg() {
  local formula="$1"
  local binary="$2"
  if command -v "$binary" >/dev/null 2>&1; then
    return 0
  fi
  if ! command -v brew >/dev/null 2>&1; then
    echo "[native] ERROR: Homebrew is required to install ${formula}" >&2
    return 1
  fi
  echo "[native] Installing ${formula} via Homebrew"
  brew install "$formula"
}

ensure_soft_open_file_limit() {
  local requested="${1:-65536}"
  local current hard capped
  current="$(ulimit -n 2>/dev/null || true)"
  if [[ ! "$current" =~ ^[0-9]+$ ]]; then
    return 0
  fi
  if (( current >= requested )); then
    return 0
  fi

  if ulimit -Sn "$requested" >/dev/null 2>&1; then
    echo "[native] Raised max open files soft limit to ${requested}"
    return 0
  fi

  hard="$(ulimit -Hn 2>/dev/null || true)"
  if [[ "$hard" =~ ^[0-9]+$ ]] && (( hard > current )); then
    capped="$hard"
    if (( capped > requested )); then
      capped="$requested"
    fi
    if ulimit -Sn "$capped" >/dev/null 2>&1; then
      echo "[native] Raised max open files soft limit to ${capped}"
      return 0
    fi
  fi

  echo "[native] WARNING: max open files soft limit remains ${current}; MongoDB may fail under heavy index creation" >&2
}

ensure_livekit_binary() {
  if command -v livekit-server >/dev/null 2>&1; then
    echo "livekit-server"
    return 0
  fi
  if command -v livekit >/dev/null 2>&1; then
    echo "livekit"
    return 0
  fi
  ensure_brew_pkg livekit livekit >/dev/null
  if command -v livekit-server >/dev/null 2>&1; then
    echo "livekit-server"
    return 0
  fi
  if command -v livekit >/dev/null 2>&1; then
    echo "livekit"
    return 0
  fi
  echo "[native] ERROR: livekit binary not found after installation" >&2
  return 1
}

start_mongo() {
  if port_listening "$MONGO_PORT"; then
    echo "[native] MongoDB already listening on ${MONGO_PORT}"
    return 0
  fi
  ensure_brew_pkg mongodb/brew/mongodb-community@8.0 mongod
  ensure_soft_open_file_limit 65536
  echo "[native] Starting MongoDB on ${MONGO_HOST}:${MONGO_PORT}"
  nohup mongod \
    --bind_ip "$MONGO_HOST" \
    --port "$MONGO_PORT" \
    --dbpath "$MONGO_DATA_DIR" \
    --logpath "$MONGO_LOG_FILE" \
    --logappend \
    --setParameter diagnosticDataCollectionEnabled=false \
    >"$MONGO_LOG_FILE" 2>&1 &
  write_pid "$!" "$MONGO_PID_FILE"
  wait_for_port "$MONGO_PORT" "MongoDB"
}

meili_log_indicates_incompatible_data() {
  if [[ ! -f "$MEILI_LOG_FILE" ]]; then
    return 1
  fi
  grep -Eq \
    "failed to infer the version of the database|incompatible with your current engine version" \
    "$MEILI_LOG_FILE"
}

archive_incompatible_meili_data() {
  local timestamp archive_root source_dir archive_dir
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  archive_root="${PROFILE_STATE_DIR}/backups"
  mkdir -p "$archive_root"

  if [[ "$(basename "$MEILI_DATA_DIR")" == "data.ms" ]]; then
    source_dir="$(dirname "$MEILI_DATA_DIR")"
    archive_dir="${archive_root}/meili-data-incompatible-${timestamp}"
    mv "$source_dir" "$archive_dir"
    mkdir -p "$source_dir"
    MEILI_DATA_DIR="${source_dir}/data.ms"
  else
    source_dir="$MEILI_DATA_DIR"
    archive_dir="${archive_root}/meili-data-incompatible-${timestamp}"
    mv "$source_dir" "$archive_dir"
  fi

  mkdir -p "$MEILI_DATA_DIR"
  echo "[native] Archived incompatible Meilisearch data to ${archive_dir}"
}

start_meili() {
  start_meili_process() {
    rm -f "$MEILI_PID_FILE"
    : >"$MEILI_LOG_FILE"
    nohup "$(command -v meilisearch)" \
      --http-addr "${MEILI_HOST}:${MEILI_PORT}" \
      --master-key "$MEILI_MASTER_KEY" \
      --db-path "$MEILI_DATA_DIR" \
      --no-analytics \
      >"$MEILI_LOG_FILE" 2>&1 &
    write_pid "$!" "$MEILI_PID_FILE"
  }

  if port_listening "$MEILI_PORT"; then
    echo "[native] Meilisearch already listening on ${MEILI_PORT}"
    return 0
  fi
  ensure_brew_pkg meilisearch meilisearch
  echo "[native] Starting Meilisearch on ${MEILI_HOST}:${MEILI_PORT}"
  start_meili_process
  if wait_for_port "$MEILI_PORT" "Meilisearch"; then
    return 0
  fi

  if meili_log_indicates_incompatible_data; then
    echo "[native] Detected incompatible Meilisearch data format; archiving legacy data and retrying"
    stop_pid_file "$MEILI_PID_FILE" "Meilisearch"
    archive_incompatible_meili_data
    start_meili_process
    wait_for_port "$MEILI_PORT" "Meilisearch"
    return 0
  fi

  return 1
}

start_livekit() {
  if [[ "$NATIVE_STACK_SKIP_LIVEKIT" == "1" || "$NATIVE_STACK_SKIP_LIVEKIT" == "true" ]]; then
    echo "[native] Skipping native LiveKit during early bootstrap; launcher will own LiveKit startup"
    return 0
  fi
  if [[ "$VOICE_ENABLED" != "true" ]]; then
    echo "[native] Voice disabled; skipping native LiveKit"
    return 0
  fi
  if port_listening "$LIVEKIT_HTTP_PORT"; then
    local existing_pid
    existing_pid="$(managed_livekit_listener_pid || true)"
    if [[ -n "$existing_pid" ]]; then
      if livekit_meta_matches_expected && livekit_command_matches_expected "$existing_pid"; then
        echo "[native] LiveKit already listening on ${LIVEKIT_HTTP_PORT}"
        return 0
      fi
      echo "[native] Restarting LiveKit on ${LIVEKIT_HTTP_PORT} to apply updated network/runtime config"
      stop_pid "$existing_pid" "LiveKit"
      rm -f "$LIVEKIT_PID_FILE" "$LIVEKIT_META_FILE"
    else
      echo "[native] LiveKit already listening on ${LIVEKIT_HTTP_PORT}"
      return 0
    fi
  fi
  local livekit_bin
  livekit_bin="$(ensure_livekit_binary)"
  cat >"$LIVEKIT_CFG_FILE" <<EOF
port: ${LIVEKIT_HTTP_PORT}
rtc:
  tcp_port: ${LIVEKIT_TCP_PORT}
  udp_port: ${LIVEKIT_UDP_PORT}
EOF
  if [[ -n "$LIVEKIT_TURN_DOMAIN" && -n "$LIVEKIT_TURN_TLS_PORT" && -n "$LIVEKIT_TURN_CERT_FILE" && -n "$LIVEKIT_TURN_KEY_FILE" ]]; then
    cat >>"$LIVEKIT_CFG_FILE" <<EOF
turn:
  enabled: true
  domain: "${LIVEKIT_TURN_DOMAIN}"
  tls_port: ${LIVEKIT_TURN_TLS_PORT}
  cert_file: "${LIVEKIT_TURN_CERT_FILE}"
  key_file: "${LIVEKIT_TURN_KEY_FILE}"
EOF
  fi
  cat >>"$LIVEKIT_CFG_FILE" <<EOF
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
EOF
  echo "[native] Starting LiveKit on ${LIVEKIT_HTTP_PORT}"
  nohup "$livekit_bin" \
    --config "$LIVEKIT_CFG_FILE" \
    --node-ip "$LIVEKIT_NODE_IP" \
    >"$LIVEKIT_LOG_FILE" 2>&1 &
  write_pid "$!" "$LIVEKIT_PID_FILE"
  write_livekit_runtime_meta
  wait_for_port "$LIVEKIT_HTTP_PORT" "LiveKit"
}

case "${1:-}" in
  start)
    start_mongo
    start_meili
    start_livekit
    ;;
  stop)
    stop_livekit
    stop_pid_file "$MEILI_PID_FILE" "Meilisearch"
    if [[ -f "$MONGO_PID_FILE" ]]; then
      stop_pid_file "$MONGO_PID_FILE" "MongoDB"
    fi
    ;;
  *)
    echo "Usage: $0 <start|stop>" >&2
    exit 1
    ;;
esac
