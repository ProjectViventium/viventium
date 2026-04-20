#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "/opt/homebrew/bin"
  prepend_path_if_dir "/opt/homebrew/sbin"
  prepend_path_if_dir "/usr/local/bin"
  prepend_path_if_dir "/usr/local/sbin"
  prepend_path_if_dir "/opt/homebrew/opt/node@20/bin"
  prepend_path_if_dir "/usr/local/opt/node@20/bin"
  prepend_path_if_dir "/opt/homebrew/opt/python@3.12/libexec/bin"
  prepend_path_if_dir "/usr/local/opt/python@3.12/libexec/bin"
  prepend_path_if_dir "/Applications/Docker.app/Contents/Resources/bin"
  prepend_path_if_dir "/Applications/Docker.app/Contents/MacOS"
  prepend_path_if_dir "$HOME/Applications/Docker.app/Contents/Resources/bin"
  prepend_path_if_dir "$HOME/Applications/Docker.app/Contents/MacOS"
  export PATH
}

ensure_app_support_layout() {
  local app_support_dir="$1"
  mkdir -p "$app_support_dir"
  mkdir -p "$app_support_dir/runtime"
  mkdir -p "$app_support_dir/state"
  mkdir -p "$app_support_dir/snapshots"
  mkdir -p "$app_support_dir/logs"
}

path_is_git_repo_root() {
  local candidate="${1:-}"
  [[ -n "$candidate" && -d "$candidate" ]] || return 1
  local git_root=""
  git_root="$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$git_root" ]] || return 1
  [[ "$(cd "$candidate" && pwd -P)" == "$(cd "$git_root" && pwd -P)" ]]
}

public_safe_path_label() {
  local candidate="${1:-}"
  [[ -n "$candidate" ]] || return 1
  if [[ "$candidate" == "$HOME" ]]; then
    printf '%s\n' "~"
    return 0
  fi
  case "$candidate" in
    "$HOME"/*)
      printf '~/%s\n' "${candidate#"$HOME"/}"
      return 0
      ;;
  esac
  local base=""
  base="$(basename "$candidate")"
  if [[ -n "$base" && "$base" != "/" && "$base" != "." ]]; then
    printf '<local>/%s\n' "$base"
  else
    printf '%s\n' "<local>"
  fi
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
    if path_is_git_repo_root "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

discover_private_curated_dir() {
  local private_repo_dir="${1:-}"
  if [[ -z "$private_repo_dir" ]]; then
    return 1
  fi

  local candidate="$private_repo_dir/curated"
  if [[ -d "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

discover_private_backup_root() {
  local app_support_dir="$1"
  local private_repo_dir="${2:-}"
  if [[ -n "$private_repo_dir" ]]; then
    printf '%s\n' "$private_repo_dir/backups/local-state"
    return 0
  fi
  printf '%s\n' "$app_support_dir/snapshots"
}

continuity_state_dir() {
  local app_support_dir="$1"
  local runtime_profile="${2:-isolated}"
  printf '%s\n' "$app_support_dir/state/runtime/${runtime_profile}/continuity"
}

continuity_audit_dir() {
  local app_support_dir="$1"
  printf '%s\n' "$app_support_dir/state/continuity"
}

recall_rebuild_required_file() {
  local app_support_dir="$1"
  local runtime_profile="${2:-isolated}"
  printf '%s\n' "$(continuity_state_dir "$app_support_dir" "$runtime_profile")/recall-rebuild-required.json"
}

python_has_module() {
  local python_bin="$1"
  local module_name="$2"
  "$python_bin" - <<PY >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("$module_name") else 1)
PY
}

python_runs_inline_script() {
  local python_bin="$1"
  "$python_bin" - <<'PY' >/dev/null 2>&1
print("ok")
PY
}

resolve_repo_python() {
  local preferred="${VIVENTIUM_PYTHON_BIN:-}"
  local candidate=""
  local candidates=()
  if [[ -n "$preferred" ]]; then
    candidates+=("$preferred")
  fi
  candidates+=(python3.12 python3.11 python3.10 python3 python)

  for candidate in "${candidates[@]}"; do
    if [[ -z "$candidate" ]]; then
      continue
    fi
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  for candidate in "${candidates[@]}"; do
    if [[ -z "$candidate" ]]; then
      continue
    fi
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "Unable to locate a usable Python interpreter." >&2
  return 1
}

bootstrap_python_root() {
  local app_support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
  printf '%s\n' "${VIVENTIUM_BOOTSTRAP_PYTHON_ROOT:-$app_support_dir/state/bootstrap-python}"
}

create_bootstrap_python() {
  local base_python="$1"
  local root
  root="$(bootstrap_python_root)"
  local python_bin="$root/bin/python3"

  if [[ -x "$python_bin" ]]; then
    if python_runs_inline_script "$python_bin"; then
      printf '%s\n' "$python_bin"
      return 0
    fi
    rm -rf "$root"
  fi

  mkdir -p "$(dirname "$root")"
  if ! "$base_python" -m venv "$root" >/dev/null 2>&1; then
    echo "Failed to create the Viventium bootstrap Python environment." >&2
    return 1
  fi
  if [[ -x "$python_bin" ]]; then
    printf '%s\n' "$python_bin"
  else
    printf '%s\n' "$base_python"
  fi
}

python_uses_bootstrap_root() {
  local python_bin="$1"
  local root
  root="$(bootstrap_python_root)"
  case "$python_bin" in
    "$root"/*)
      return 0
      ;;
  esac
  return 1
}

ensure_python_module() {
  local python_bin="$1"
  local module_name="$2"
  local package_name="${3:-$module_name}"
  local target_python="$python_bin"

  if python_has_module "$target_python" "$module_name"; then
    printf '%s\n' "$target_python"
    return 0
  fi

  target_python="$(create_bootstrap_python "$python_bin")" || return 1
  if [[ ! -x "$target_python" ]]; then
    target_python="$python_bin"
  fi

  if ! python_runs_inline_script "$target_python"; then
    echo "Selected Python interpreter cannot execute inline scripts: $target_python" >&2
    return 1
  fi

  if python_has_module "$target_python" "$module_name"; then
    printf '%s\n' "$target_python"
    return 0
  fi

  if ! "$target_python" -m pip --version >/dev/null 2>&1; then
    "$target_python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  local user_flag=""
  if ! python_uses_bootstrap_root "$target_python"; then
    user_flag="--user"
  fi

  if [[ -n "$user_flag" ]]; then
    if ! "$target_python" -m pip install "$user_flag" "$package_name" >/dev/null 2>&1; then
      if ! "$target_python" -m pip install "$user_flag" --break-system-packages "$package_name" >/dev/null 2>&1; then
        echo "Failed to install required Python package: $package_name" >&2
        return 1
      fi
    fi
  elif ! "$target_python" -m pip install "$package_name" >/dev/null 2>&1; then
    if ! "$target_python" -m pip install --break-system-packages "$package_name" >/dev/null 2>&1; then
      echo "Failed to install required Python package: $package_name" >&2
      return 1
    fi
  fi

  if ! python_has_module "$target_python" "$module_name"; then
    return 1
  fi

  printf '%s\n' "$target_python"
}

ensure_python_requirements_file() {
  local python_bin="$1"
  local requirements_file="$2"
  local target_python="$python_bin"
  local stamp_path=""

  [[ -f "$requirements_file" ]] || {
    echo "Installer requirements file not found: $requirements_file" >&2
    return 1
  }

  target_python="$(create_bootstrap_python "$python_bin")" || return 1
  if [[ ! -x "$target_python" ]]; then
    target_python="$python_bin"
  fi

  if ! python_runs_inline_script "$target_python"; then
    echo "Selected Python interpreter cannot execute inline scripts: $target_python" >&2
    return 1
  fi

  if ! "$target_python" -m pip --version >/dev/null 2>&1; then
    "$target_python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  stamp_path="$(bootstrap_python_root)/requirements.sha256"
  local requirements_hash=""
  requirements_hash="$(shasum -a 256 "$requirements_file" | awk '{print $1}')"
  if [[ -f "$stamp_path" && "$(cat "$stamp_path" 2>/dev/null || true)" == "$requirements_hash" ]]; then
    printf '%s\n' "$target_python"
    return 0
  fi

  local user_flag=""
  if ! python_uses_bootstrap_root "$target_python"; then
    user_flag="--user"
  fi

  if [[ -n "$user_flag" ]]; then
    if ! "$target_python" -m pip install "$user_flag" -r "$requirements_file" >/dev/null 2>&1; then
      if ! "$target_python" -m pip install "$user_flag" --break-system-packages -r "$requirements_file" >/dev/null 2>&1; then
        echo "Failed to install required Python packages from: $requirements_file" >&2
        return 1
      fi
    fi
  elif ! "$target_python" -m pip install -r "$requirements_file" >/dev/null 2>&1; then
    if ! "$target_python" -m pip install --break-system-packages -r "$requirements_file" >/dev/null 2>&1; then
      echo "Failed to install required Python packages from: $requirements_file" >&2
      return 1
    fi
  fi

  printf '%s\n' "$requirements_hash" >"$stamp_path"
  printf '%s\n' "$target_python"
}

viventium_port_listener_active() {
  local port="$1"
  [[ -n "$port" ]] || return 1

  local python_bin="${VIVENTIUM_PYTHON_BIN:-$(command -v python3 2>/dev/null || true)}"
  local host="${VIVENTIUM_PORT_CHECK_HOST:-localhost}"
  local timeout_seconds="${VIVENTIUM_PORT_CHECK_TIMEOUT_SECONDS:-1}"

  if [[ -n "$python_bin" ]]; then
    "$python_bin" - "$host" "$port" "$timeout_seconds" <<'PY' 2>/dev/null
import socket
import sys

host = str(sys.argv[1]).strip() or "localhost"
port = int(sys.argv[2])
try:
    timeout_seconds = max(0.2, float(sys.argv[3]))
except Exception:
    timeout_seconds = 1.0

seen = set()
for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
    host,
    port,
    type=socket.SOCK_STREAM,
):
    key = (family, sockaddr)
    if key in seen:
        continue
    seen.add(key)
    sock = socket.socket(family, socktype, proto)
    sock.settimeout(timeout_seconds)
    try:
        if sock.connect_ex(sockaddr) == 0:
            raise SystemExit(0)
    except Exception:
        pass
    finally:
        sock.close()

raise SystemExit(1)
PY
    return $?
  fi

  if command -v nc >/dev/null 2>&1; then
    if nc -z -w "$timeout_seconds" "$host" "$port" >/dev/null 2>&1; then
      return 0
    fi
    if nc -z -G "$timeout_seconds" "$host" "$port" >/dev/null 2>&1; then
      return 0
    fi
  fi

  return 1
}
