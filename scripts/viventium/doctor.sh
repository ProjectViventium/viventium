#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT_DEFAULT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/common.sh"
ensure_brew_paths_on_path

PYTHON_BIN="$(resolve_repo_python)"
PYTHON_BIN="$(ensure_python_requirements_file "$PYTHON_BIN" "$SCRIPT_DIR/requirements-installer.txt")"

CONFIG_FILE=""
RUNTIME_DIR=""
REPO_ROOT=""
LOCK_FILE=""
ALLOW_LOW_DISK="${VIVENTIUM_DOCTOR_ALLOW_LOW_DISK:-false}"
DOCKER_CHECK_TIMEOUT_SECONDS="${VIVENTIUM_DOCKER_CHECK_TIMEOUT_SECONDS:-15}"
PREFER_EXISTING_CHECKOUT_HEAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="${2:-}"
      shift 2
      ;;
    --runtime-dir)
      RUNTIME_DIR="${2:-}"
      shift 2
      ;;
    --repo-root)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --lock-file)
      LOCK_FILE="${2:-}"
      shift 2
      ;;
    --prefer-existing-checkout-head)
      PREFER_EXISTING_CHECKOUT_HEAD=1
      shift
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$CONFIG_FILE" || -z "$RUNTIME_DIR" || -z "$REPO_ROOT" || -z "$LOCK_FILE" ]]; then
  echo "Usage: doctor.sh --config <path> --runtime-dir <path> --repo-root <path> --lock-file <path>" >&2
  exit 1
fi

echo "[doctor] Platform: $(uname -s) $(uname -m)"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[doctor] WARN: macOS is the only supported public install target."
fi

for cmd in git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[doctor] ERROR: missing required command: $cmd" >&2
    exit 1
  fi
done

if ! command -v security >/dev/null 2>&1; then
  echo "[doctor] ERROR: macOS Keychain command not available" >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[doctor] ERROR: config not found: $CONFIG_FILE" >&2
  exit 1
fi

run_command_with_timeout() {
  local timeout_seconds="$1"
  shift

  "$PYTHON_BIN" - <<'PY' "$timeout_seconds" "$@"
import subprocess
import sys

timeout_seconds = int(sys.argv[1])
command = sys.argv[2:]

try:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_seconds)
except subprocess.TimeoutExpired:
    print(f"TIMEOUT after {timeout_seconds}s", file=sys.stderr)
    sys.exit(124)

if completed.stdout:
    print(completed.stdout, end="")
if completed.stderr:
    print(completed.stderr, end="", file=sys.stderr)
sys.exit(completed.returncode)
PY
}

load_doctor_config_flags() {
  local config_path="$1"
  local repo_root="$2"

  "$PYTHON_BIN" - "$config_path" "$repo_root" <<'PY'
from pathlib import Path
import shlex
import sys
import yaml

config_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
install_mode = str(config.get("install", {}).get("mode", "docker")).strip().lower()
voice_mode = str(config.get("voice", {}).get("mode", "disabled")).strip().lower()
integrations = config.get("integrations", {}) or {}
runtime = config.get("runtime", {}) or {}
personalization = runtime.get("personalization", {}) or {}
selected = {
    "INSTALL_MODE": install_mode or "docker",
    "VOICE_MODE": voice_mode or "disabled",
    "ENABLE_TELEGRAM": "1" if integrations.get("telegram", {}).get("enabled") else "0",
    "ENABLE_GOOGLE_WORKSPACE": "1" if integrations.get("google_workspace", {}).get("enabled") else "0",
    "ENABLE_MS365": "1" if integrations.get("ms365", {}).get("enabled") else "0",
    "ENABLE_SKYVERN": "1" if integrations.get("skyvern", {}).get("enabled") else "0",
    "ENABLE_OPENCLAW": "1" if integrations.get("openclaw", {}).get("enabled") else "0",
    "ENABLE_CONVERSATION_RECALL": "1" if personalization.get("default_conversation_recall", False) else "0",
    "ENABLE_RUN_CODE_DEFAULT": "1" if (integrations.get("code_interpreter", {}) or {}).get("enabled") else "0",
    "ENABLE_WEB_SEARCH_DEFAULT": "1" if (integrations.get("web_search", {}) or {}).get("enabled") else "0",
}
for key, value in selected.items():
    print(f"{key}={shlex.quote(value)}")
PY
}

doctor_env_exports="$(load_doctor_config_flags "$CONFIG_FILE" "$REPO_ROOT")"
if [[ -z "$doctor_env_exports" ]]; then
  echo "[doctor] ERROR: failed to derive install flags from $CONFIG_FILE" >&2
  exit 1
fi
eval "$doctor_env_exports"

if [[ "$INSTALL_MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "[doctor] ERROR: Docker mode selected but docker is not installed" >&2
    exit 1
  fi
  docker_check_output="$(
    run_command_with_timeout "$DOCKER_CHECK_TIMEOUT_SECONDS" docker ps 2>&1
  )" || docker_check_status=$?
  docker_check_status="${docker_check_status:-0}"
  if [[ "$docker_check_status" != "0" ]]; then
    if [[ "$docker_check_status" == "124" ]]; then
      echo "[doctor] ERROR: Docker mode selected but the docker daemon probe timed out after ${DOCKER_CHECK_TIMEOUT_SECONDS}s." >&2
      echo "[doctor] INFO: Start or restart Docker Desktop and retry." >&2
    else
      echo "[doctor] ERROR: Docker mode selected but the docker daemon is not reachable." >&2
    fi
    if [[ -n "${docker_check_output:-}" ]]; then
      echo "[doctor] Docker probe output:" >&2
      echo "$docker_check_output" >&2
    fi
    exit 1
  fi
  echo "[doctor] Docker: available"
else
  for cmd in brew node npm pnpm uv; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      echo "[doctor] ERROR: native mode requires $cmd" >&2
      exit 1
    fi
  done
  node_major="$(node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')"
  if [[ "$node_major" != "20" ]]; then
    echo "[doctor] ERROR: native mode requires the validated node@20 runtime; found $(node -v 2>/dev/null || echo unknown)." >&2
    echo "[doctor] INFO: Run 'bin/viventium upgrade' to install/use node@20 before starting again." >&2
    exit 1
  fi
  if [[ "$ENABLE_SKYVERN" == "1" ]]; then
    echo "[doctor] WARN: Skyvern is enabled in config, but native local runs may still keep Skyvern disabled unless the launcher is allowed to use its container-backed path."
  fi
  docker_required_features=()
  [[ "$ENABLE_MS365" == "1" ]] && docker_required_features+=("MS365")
  [[ "$ENABLE_CONVERSATION_RECALL" == "1" ]] && docker_required_features+=("Conversation Recall")
  [[ "$ENABLE_RUN_CODE_DEFAULT" == "1" ]] && docker_required_features+=("Code Interpreter")
  [[ "$ENABLE_WEB_SEARCH_DEFAULT" == "1" ]] && docker_required_features+=("Web Search")
  [[ "$ENABLE_SKYVERN" == "1" ]] && docker_required_features+=("Skyvern")

  if (( ${#docker_required_features[@]} > 0 )); then
    docker_feature_summary="$(printf '%s, ' "${docker_required_features[@]}")"
    docker_feature_summary="${docker_feature_summary%, }"
    if ! command -v docker >/dev/null 2>&1; then
      echo "[doctor] ERROR: native mode expects Docker-backed local services for: ${docker_feature_summary}." >&2
      echo "[doctor] INFO: Install Docker Desktop or disable those features before this native run." >&2
      exit 1
    fi
    docker_check_output="$(
      run_command_with_timeout "$DOCKER_CHECK_TIMEOUT_SECONDS" docker ps 2>&1
    )" || docker_check_status=$?
    docker_check_status="${docker_check_status:-0}"
    if [[ "$docker_check_status" != "0" ]]; then
      if [[ "$docker_check_status" == "124" ]]; then
        echo "[doctor] ERROR: Docker-backed local services (${docker_feature_summary}) did not respond within ${DOCKER_CHECK_TIMEOUT_SECONDS}s." >&2
      else
        echo "[doctor] ERROR: Docker-backed local services (${docker_feature_summary}) are enabled, but Docker Desktop is not running." >&2
      fi
      if [[ -n "${docker_check_output:-}" ]]; then
        echo "[doctor] Docker probe output:" >&2
        echo "$docker_check_output" >&2
      fi
      exit 1
    fi
  fi
  echo "[doctor] Native prerequisites: available"
fi

disk_line="$(df -Pk "$RUNTIME_DIR" | awk 'NR==2 {print $4}')"
if [[ -n "$disk_line" && "$disk_line" =~ ^[0-9]+$ ]]; then
  free_kib="$disk_line"
  free_gib="$("$PYTHON_BIN" - <<'PY' "$free_kib"
import sys
free_kib = int(sys.argv[1])
print(f"{free_kib / (1024 * 1024):.1f}")
PY
)"
  if (( free_kib < 6 * 1024 * 1024 )); then
    if [[ "$ALLOW_LOW_DISK" == "true" ]]; then
      echo "[doctor] WARN: only ${free_gib} GiB free on the target volume; proceeding because VIVENTIUM_DOCTOR_ALLOW_LOW_DISK=true."
    else
      echo "[doctor] ERROR: only ${free_gib} GiB free on the target volume; at least 6.0 GiB is required for a reliable first boot." >&2
      exit 1
    fi
  elif (( free_kib < 10 * 1024 * 1024 )); then
    echo "[doctor] WARN: only ${free_gib} GiB free on the target volume; first boot installs may be slow or fail under disk pressure."
  fi
fi

"$PYTHON_BIN" "$SCRIPT_DIR/config_compiler.py" \
  --config "$CONFIG_FILE" \
  --output-dir "$RUNTIME_DIR" \
  --dry-run >/dev/null

echo "[doctor] Config compiles successfully."

DOCTOR_TMP_COMPILE_DIR="$(mktemp -d "$RUNTIME_DIR/.doctor-compile.XXXXXX")"
cleanup_doctor_tmp() {
  rm -rf "$DOCTOR_TMP_COMPILE_DIR"
}
trap cleanup_doctor_tmp EXIT

"$PYTHON_BIN" "$SCRIPT_DIR/config_compiler.py" \
  --config "$CONFIG_FILE" \
  --output-dir "$DOCTOR_TMP_COMPILE_DIR" >/dev/null

"$PYTHON_BIN" - <<'PY' "$DOCTOR_TMP_COMPILE_DIR/runtime.env" "$DOCTOR_TMP_COMPILE_DIR/librechat.yaml"
from pathlib import Path
import re
import sys

runtime_env_path = Path(sys.argv[1])
librechat_yaml_path = Path(sys.argv[2])

env_keys = set()
for raw_line in runtime_env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _ = line.split("=", 1)
    env_keys.add(key)

placeholders = set(re.findall(r"\$\{([A-Z0-9_]+)\}", librechat_yaml_path.read_text(encoding="utf-8")))
missing = sorted(key for key in placeholders if key not in env_keys)
if missing:
    print(
        "[doctor] ERROR: generated librechat.yaml references unresolved env vars: "
        + ", ".join(missing),
        file=sys.stderr,
    )
    sys.exit(1)
PY

echo "[doctor] Generated config placeholders resolve against runtime.env."

bootstrap_args=(
  --repo-root "$REPO_ROOT"
  --lock-file "$LOCK_FILE"
  --config "$CONFIG_FILE"
  --validate-only
)
if [[ "$PREFER_EXISTING_CHECKOUT_HEAD" == "1" ]]; then
  bootstrap_args+=(--prefer-existing-checkout-head)
fi
"$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/bootstrap_components.py" \
  "${bootstrap_args[@]}" >/dev/null

if [[ "$PREFER_EXISTING_CHECKOUT_HEAD" == "1" ]]; then
  echo "[doctor] Selected components passed bootstrap validation for the current local runtime checkout mode."
else
  echo "[doctor] Selected components are present at the pinned refs."
fi
