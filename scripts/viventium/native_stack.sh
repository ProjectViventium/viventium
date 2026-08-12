#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/viventium/common.sh"

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
MONGODB_NATIVE_VERSION="8.0.23"
MONGODB_NATIVE_TEAM_ID="4XWMY46275"
MONGODB_NATIVE_BINARY="${APP_SUPPORT_DIR}/runtime-tools/mongodb/${MONGODB_NATIVE_VERSION}/$(uname -m)/bin/mongod"

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
NATIVE_STACK_SKIP_MEILI="${VIVENTIUM_NATIVE_STACK_SKIP_MEILI:-0}"
VOICE_ENABLED="${VIVENTIUM_VOICE_ENABLED:-true}"

mkdir -p "$NATIVE_STATE_DIR" "$NATIVE_LOG_DIR" "$PROFILE_STATE_DIR" "$MONGO_DATA_DIR" "$MEILI_DATA_DIR" "$LIVEKIT_CFG_DIR"

port_listening() {
  local port="$1"
  viventium_port_listener_active "$port"
}

resolve_unique_listener_pid() {
  local port="$1"
  local pid=""
  local selected_pid=""
  local count=0

  if ! command -v lsof >/dev/null 2>&1; then
    echo "[native] ERROR: cannot resolve listener ownership on port ${port} because lsof is unavailable" >&2
    return 1
  fi

  while IFS= read -r pid; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    count=$((count + 1))
    selected_pid="$pid"
  done < <(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)

  if [[ "$count" -eq 0 ]]; then
    echo "[native] ERROR: port ${port} reported active but no listener PID could be resolved" >&2
    return 1
  fi
  if [[ "$count" -ne 1 ]]; then
    echo "[native] ERROR: port ${port} has multiple listener PIDs; refusing ambiguous ownership" >&2
    return 1
  fi
  printf '%s\n' "$selected_pid"
}

process_command_line() {
  local pid="$1"
  # BSD/macOS ps truncates long argv output to the display width unless -ww is
  # requested. Runtime-owned data paths occur late in the MongoDB and
  # Meilisearch argv, so truncated output makes a valid PID look foreign.
  ps -ww -p "$pid" -o command= 2>/dev/null || true
}

process_executable_identity() {
  local pid="$1"
  # macOS truncates `comm` to MAXCOMLEN even with -ww. These managed service
  # basenames fit within `ucomm`, which avoids depending on the truncated path.
  ps -ww -p "$pid" -o ucomm= 2>/dev/null |
    head -n 1 |
    sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || true
}

process_executable_basename_matches() {
  local pid="$1"
  local expected_basename="$2"
  local executable_identity executable_basename
  executable_identity="$(process_executable_identity "$pid")"
  [[ -n "$executable_identity" ]] || return 1
  executable_basename="${executable_identity##*/}"
  [[ "$executable_basename" == "$expected_basename" ]]
}

canonical_existing_path() {
  local candidate="$1"
  [[ -e "$candidate" ]] || return 1
  if command -v realpath >/dev/null 2>&1; then
    realpath "$candidate" 2>/dev/null
    return $?
  fi

  local candidate_dir candidate_name
  candidate_dir="$(dirname "$candidate")"
  candidate_name="$(basename "$candidate")"
  (cd "$candidate_dir" >/dev/null 2>&1 && printf '%s/%s\n' "$(pwd -P)" "$candidate_name")
}

process_executable_path() {
  local pid="$1"
  local output=""
  local record=""
  local process_count=0
  local current_process_matches=0
  local primary_path=""

  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  output="$(lsof -a -p "$pid" -d txt -Fn 2>/dev/null)" || return 1

  while IFS= read -r record; do
    case "$record" in
      p*)
        process_count=$((process_count + 1))
        if [[ "${record#p}" == "$pid" ]]; then
          current_process_matches=1
        else
          current_process_matches=0
        fi
        ;;
      n*)
        if [[ "$current_process_matches" == "1" && -z "$primary_path" ]]; then
          primary_path="${record#n}"
        fi
        ;;
    esac
  done <<<"$output"

  [[ "$process_count" -eq 1 && -n "$primary_path" ]] || return 1
  canonical_existing_path "$primary_path"
}

mongo_executable_matches_expected() {
  local pid="$1"
  if [[ "${VIVENTIUM_INSTALL_EXPERIENCE:-legacy}" == "express" ]]; then
    local running_path pinned_path
    running_path="$(process_executable_path "$pid")" || return 1
    pinned_path="$(canonical_existing_path "$MONGODB_NATIVE_BINARY")" || return 1
    [[ "$running_path" == "$pinned_path" ]]
    return
  fi
  process_executable_basename_matches "$pid" "mongod"
}

command_line_has_option_value() {
  local command_line="$1"
  local option="$2"
  local expected_value="$3"
  [[ " $command_line " == *" $option $expected_value "* ]]
}

canonical_existing_dir() {
  local candidate="$1"
  (cd "$candidate" >/dev/null 2>&1 && pwd -P)
}

mongo_process_matches_expected() {
  local pid="$1"
  local command_line expected_data_dir
  command_line="$(process_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1
  expected_data_dir="$(canonical_existing_dir "$MONGO_DATA_DIR")" || return 1
  mongo_executable_matches_expected "$pid" || return 1
  command_line_has_option_value "$command_line" "--port" "$MONGO_PORT" || return 1
  command_line_has_option_value "$command_line" "--dbpath" "$expected_data_dir"
}

meili_process_matches_expected() {
  local pid="$1"
  local command_line expected_data_dir
  command_line="$(process_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1
  expected_data_dir="$(canonical_existing_dir "$MEILI_DATA_DIR")" || return 1
  process_executable_basename_matches "$pid" "meilisearch" || return 1
  command_line_has_option_value "$command_line" "--http-addr" "${MEILI_HOST}:${MEILI_PORT}" || return 1
  command_line_has_option_value "$command_line" "--db-path" "$expected_data_dir"
}

mongo_listener_data_dir() {
  if ! command -v mongosh >/dev/null 2>&1; then
    return 1
  fi

  local mongo_admin_uri="mongodb://${MONGO_HOST}:${MONGO_PORT}/admin?directConnection=true&serverSelectionTimeoutMS=3000"
  mongosh "$mongo_admin_uri" --quiet --eval '
const result = db.adminCommand({ getCmdLineOpts: 1 });
if (!result.ok || !result.parsed || !result.parsed.storage || !result.parsed.storage.dbPath) {
  quit(2);
}
print(result.parsed.storage.dbPath);
' 2>/dev/null | tail -n 1
}

mongo_listener_matches_expected() {
  local listener_pid="${1:-}"
  if [[ "${VIVENTIUM_INSTALL_EXPERIENCE:-legacy}" == "express" ]]; then
    express_mongo_listener_matches_expected "$listener_pid"
    return $?
  fi

  local listener_data_dir expected_data_dir canonical_listener_data_dir
  listener_data_dir="$(mongo_listener_data_dir)" || return 1
  [[ -n "$listener_data_dir" ]] || return 1
  expected_data_dir="$(canonical_existing_dir "$MONGO_DATA_DIR")" || return 1
  canonical_listener_data_dir="$(canonical_existing_dir "$listener_data_dir")" || return 1
  [[ "$canonical_listener_data_dir" == "$expected_data_dir" ]]
}

express_mongo_listener_matches_expected() {
  local pid="${1:-}"
  if [[ -z "$pid" ]]; then
    [[ -f "$MONGO_PID_FILE" ]] || return 1
    pid="$(tr -d '[:space:]' <"$MONGO_PID_FILE" 2>/dev/null || true)"
  fi
  local command_line expected_data_dir
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1 || return 1
  command_line="$(process_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1
  expected_data_dir="$(canonical_existing_dir "$MONGO_DATA_DIR")" || return 1
  mongo_executable_matches_expected "$pid" || return 1
  command_line_has_option_value "$command_line" "--port" "$MONGO_PORT" || return 1
  command_line_has_option_value "$command_line" "--dbpath" "$expected_data_dir" || return 1
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
  local temp_path="${path}.tmp.$$"
  (
    umask 077
    printf '%s\n' "$pid" >"$temp_path"
  )
  mv -f "$temp_path" "$path"
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

stop_pid_file_if_matches() {
  local path="$1"
  local label="$2"
  local matcher="$3"
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  local pid
  pid="$(tr -d '[:space:]' <"$path" || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1; then
    if "$matcher" "$pid"; then
      stop_pid "$pid" "$label"
    else
      echo "[native] WARNING: Skipping stale ${label} PID ${pid}; process identity does not match this runtime" >&2
    fi
  fi
  rm -f "$path"
}

write_livekit_runtime_meta() {
  local turn_domain="${LIVEKIT_TURN_DOMAIN:-}"
  local turn_tls_port="${LIVEKIT_TURN_TLS_PORT:-}"
  local turn_cert_file="${LIVEKIT_TURN_CERT_FILE:-}"
  local turn_key_file="${LIVEKIT_TURN_KEY_FILE:-}"
  cat >"$LIVEKIT_META_FILE" <<EOF
LIVEKIT_NODE_IP=${LIVEKIT_NODE_IP}
LIVEKIT_HTTP_PORT=${LIVEKIT_HTTP_PORT}
LIVEKIT_TCP_PORT=${LIVEKIT_TCP_PORT}
LIVEKIT_UDP_PORT=${LIVEKIT_UDP_PORT}
LIVEKIT_TURN_DOMAIN=${turn_domain}
LIVEKIT_TURN_TLS_PORT=${turn_tls_port}
LIVEKIT_TURN_CERT_FILE=${turn_cert_file}
LIVEKIT_TURN_KEY_FILE=${turn_key_file}
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
  local expected_turn_domain="${LIVEKIT_TURN_DOMAIN:-}"
  local expected_turn_tls_port="${LIVEKIT_TURN_TLS_PORT:-}"
  local expected_turn_cert_file="${LIVEKIT_TURN_CERT_FILE:-}"
  local expected_turn_key_file="${LIVEKIT_TURN_KEY_FILE:-}"
  [[ "$actual_node_ip" == "$LIVEKIT_NODE_IP" ]] &&
    [[ "$actual_http_port" == "$LIVEKIT_HTTP_PORT" ]] &&
    [[ "$actual_tcp_port" == "$LIVEKIT_TCP_PORT" ]] &&
    [[ "$actual_udp_port" == "$LIVEKIT_UDP_PORT" ]] &&
    [[ "$actual_turn_domain" == "$expected_turn_domain" ]] &&
    [[ "$actual_turn_tls_port" == "$expected_turn_tls_port" ]] &&
    [[ "$actual_turn_cert_file" == "$expected_turn_cert_file" ]] &&
    [[ "$actual_turn_key_file" == "$expected_turn_key_file" ]]
}

livekit_command_matches_expected() {
  local pid="$1"
  local command_line
  command_line="$(process_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1
  if ! process_executable_basename_matches "$pid" "livekit-server" &&
    ! process_executable_basename_matches "$pid" "livekit"; then
    return 1
  fi
  command_line_has_option_value "$command_line" "--config" "$LIVEKIT_CFG_FILE" || return 1
  command_line_has_option_value "$command_line" "--node-ip" "$LIVEKIT_NODE_IP" || return 1
}

managed_livekit_listener_pid() {
  local pid=""

  if [[ -f "$LIVEKIT_PID_FILE" ]]; then
    pid="$(tr -d '[:space:]' <"$LIVEKIT_PID_FILE" || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1 && livekit_command_matches_expected "$pid"; then
      printf '%s\n' "$pid"
      return 0
    fi
  fi

  while read -r pid; do
    [[ -n "$pid" ]] || continue
    if livekit_command_matches_expected "$pid"; then
      printf '%s\n' "$pid"
      return 0
    fi
  done < <(pgrep -f "$LIVEKIT_CFG_FILE" 2>/dev/null || true)

  return 1
}

stop_livekit() {
  stop_pid_file_if_matches "$LIVEKIT_PID_FILE" "LiveKit" livekit_command_matches_expected
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

verify_express_mongod_binary() {
  local binary="$MONGODB_NATIVE_BINARY"
  if [[ ! -x "$binary" ]]; then
    echo "[native] ERROR: pinned MongoDB ${MONGODB_NATIVE_VERSION} runtime is missing; rerun bin/viventium preflight --apply before starting Easy Install." >&2
    return 1
  fi
  if ! /usr/bin/codesign --verify --strict --verbose=2 "$binary" >/dev/null 2>&1; then
    echo "[native] ERROR: pinned MongoDB runtime failed code-signature verification; rerun the preserve-data repair flow." >&2
    return 1
  fi
  local signing_details=""
  signing_details="$(/usr/bin/codesign -dv --verbose=4 "$binary" 2>&1 || true)"
  if ! printf '%s\n' "$signing_details" | grep -Fq "TeamIdentifier=${MONGODB_NATIVE_TEAM_ID}"; then
    echo "[native] ERROR: pinned MongoDB runtime publisher does not match the approved MongoDB Team ID." >&2
    return 1
  fi
  local version_output=""
  version_output="$("$binary" --version 2>/dev/null || true)"
  if ! printf '%s\n' "$version_output" | grep -Fq "db version v${MONGODB_NATIVE_VERSION}"; then
    echo "[native] ERROR: pinned MongoDB runtime version does not match ${MONGODB_NATIVE_VERSION}." >&2
    return 1
  fi
}

select_mongod_binary() {
  if [[ "${VIVENTIUM_INSTALL_EXPERIENCE:-legacy}" == "express" ]]; then
    if ! verify_express_mongod_binary; then
      echo "[native] ERROR: Easy Install will not fall back to Homebrew or an unverified PATH mongod; repair the pinned MongoDB runtime first." >&2
      return 1
    fi
    printf '%s\n' "$MONGODB_NATIVE_BINARY"
    return 0
  fi

  ensure_brew_pkg mongodb/brew/mongodb-community@8.0 mongod >&2 || return 1
  command -v mongod
}

start_mongo() {
  local mongod_binary=""
  if port_listening "$MONGO_PORT"; then
    local listener_pid=""
    if [[ "${VIVENTIUM_INSTALL_EXPERIENCE:-legacy}" == "express" ]] && ! verify_express_mongod_binary; then
      return 1
    fi
    if ! listener_pid="$(resolve_unique_listener_pid "$MONGO_PORT")"; then
      echo "[native] ERROR: MongoDB port ${MONGO_PORT} cannot be attributed to one process; refusing ambiguous listener ownership." >&2
      return 1
    fi
    if ! mongo_process_matches_expected "$listener_pid" ||
      ! mongo_listener_matches_expected "$listener_pid"; then
      echo "[native] ERROR: MongoDB port ${MONGO_PORT} is already in use, but its data directory does not match the configured Viventium data directory; refusing to use an unexpected persistence store." >&2
      return 1
    fi
    write_pid "$listener_pid" "$MONGO_PID_FILE"
    echo "[native] MongoDB already listening on ${MONGO_PORT}; verified configured persistence identity and adopted listener PID ${listener_pid}"
    return 0
  fi
  mongod_binary="$(select_mongod_binary)" || return 1
  ensure_soft_open_file_limit 65536
  echo "[native] Starting MongoDB on ${MONGO_HOST}:${MONGO_PORT}"
  nohup "$mongod_binary" \
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
    local listener_pid=""
    if ! listener_pid="$(resolve_unique_listener_pid "$MEILI_PORT")"; then
      echo "[native] ERROR: Meilisearch port ${MEILI_PORT} cannot be attributed to one process; refusing ambiguous listener ownership." >&2
      return 1
    fi
    if ! meili_process_matches_expected "$listener_pid"; then
      echo "[native] ERROR: Meilisearch port ${MEILI_PORT} is owned by a foreign process or persistence path; refusing to adopt it." >&2
      return 1
    fi
    write_pid "$listener_pid" "$MEILI_PID_FILE"
    echo "[native] Meilisearch already listening on ${MEILI_PORT}; verified configured persistence identity and adopted listener PID ${listener_pid}"
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
  local skip_livekit="${NATIVE_STACK_SKIP_LIVEKIT:-0}"
  local turn_domain="${LIVEKIT_TURN_DOMAIN:-}"
  local turn_tls_port="${LIVEKIT_TURN_TLS_PORT:-}"
  local turn_cert_file="${LIVEKIT_TURN_CERT_FILE:-}"
  local turn_key_file="${LIVEKIT_TURN_KEY_FILE:-}"
  if [[ "$skip_livekit" == "1" || "$skip_livekit" == "true" ]]; then
    echo "[native] Skipping native LiveKit during early bootstrap; launcher will own LiveKit startup"
    return 0
  fi
  if [[ "$VOICE_ENABLED" != "true" ]]; then
    echo "[native] Voice disabled; skipping native LiveKit"
    return 0
  fi
  if port_listening "$LIVEKIT_HTTP_PORT"; then
    local existing_pid=""
    if ! existing_pid="$(resolve_unique_listener_pid "$LIVEKIT_HTTP_PORT")"; then
      echo "[native] ERROR: LiveKit port ${LIVEKIT_HTTP_PORT} cannot be attributed to one process; refusing ambiguous listener ownership." >&2
      return 1
    fi
    if ! livekit_command_matches_expected "$existing_pid"; then
      echo "[native] ERROR: LiveKit port ${LIVEKIT_HTTP_PORT} is owned by a foreign process; refusing to adopt it." >&2
      return 1
    fi
    if livekit_meta_matches_expected; then
      write_pid "$existing_pid" "$LIVEKIT_PID_FILE"
      echo "[native] LiveKit already listening on ${LIVEKIT_HTTP_PORT}; verified runtime identity and adopted listener PID ${existing_pid}"
      return 0
    fi
    echo "[native] Restarting LiveKit on ${LIVEKIT_HTTP_PORT} to apply updated network/runtime config"
    stop_pid "$existing_pid" "LiveKit"
    rm -f "$LIVEKIT_PID_FILE" "$LIVEKIT_META_FILE"
  fi
  local livekit_bin
  livekit_bin="$(ensure_livekit_binary)"
  cat >"$LIVEKIT_CFG_FILE" <<EOF
port: ${LIVEKIT_HTTP_PORT}
rtc:
  tcp_port: ${LIVEKIT_TCP_PORT}
  udp_port: ${LIVEKIT_UDP_PORT}
EOF
  if [[ -n "$turn_domain" && -n "$turn_tls_port" && -n "$turn_cert_file" && -n "$turn_key_file" ]]; then
    cat >>"$LIVEKIT_CFG_FILE" <<EOF
turn:
  enabled: true
  domain: "${turn_domain}"
  tls_port: ${turn_tls_port}
  cert_file: "${turn_cert_file}"
  key_file: "${turn_key_file}"
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
    if [[ "$NATIVE_STACK_SKIP_MEILI" != "1" ]]; then
      start_meili
    fi
    start_livekit
    ;;
  stop)
    stop_livekit
    stop_pid_file_if_matches "$MEILI_PID_FILE" "Meilisearch" meili_process_matches_expected
    if [[ -f "$MONGO_PID_FILE" ]]; then
      stop_pid_file_if_matches "$MONGO_PID_FILE" "MongoDB" mongo_process_matches_expected
    fi
    ;;
  *)
    echo "Usage: $0 <start|stop>" >&2
    exit 1
    ;;
esac
