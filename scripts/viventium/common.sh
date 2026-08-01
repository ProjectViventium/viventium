#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  local mongodb_arch=""
  local node_arch=""
  mongodb_arch="$(uname -m 2>/dev/null || true)"
  node_arch="$mongodb_arch"
  prepend_path_if_dir "${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}/runtime-tools/mongodb/8.0.23/${mongodb_arch}/bin"
  prepend_path_if_dir "/opt/homebrew/bin"
  prepend_path_if_dir "/opt/homebrew/sbin"
  prepend_path_if_dir "/usr/local/bin"
  prepend_path_if_dir "/usr/local/sbin"
  prepend_path_if_dir "/opt/homebrew/opt/node@24/bin"
  prepend_path_if_dir "/usr/local/opt/node@24/bin"
  prepend_path_if_dir "${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}/runtime-tools/node/24.16.0/${node_arch}/bin"
  prepend_path_if_dir "/opt/homebrew/opt/pnpm@10/bin"
  prepend_path_if_dir "/usr/local/opt/pnpm@10/bin"
  prepend_path_if_dir "/opt/homebrew/opt/python@3.12/libexec/bin"
  prepend_path_if_dir "/usr/local/opt/python@3.12/libexec/bin"
  prepend_path_if_dir "/Applications/Docker.app/Contents/Resources/bin"
  prepend_path_if_dir "/Applications/Docker.app/Contents/MacOS"
  prepend_path_if_dir "$HOME/Applications/Docker.app/Contents/Resources/bin"
  prepend_path_if_dir "$HOME/Applications/Docker.app/Contents/MacOS"
  export PATH
}

validate_viventium_app_support_root() {
  local candidate="${1:-}"
  local protected=""
  local prefix=""
  local part=""
  local nearest=""
  local parts=()

  [[ "$candidate" == /* ]] || return 1
  [[ "$candidate" != "/" ]] || return 1
  [[ "$candidate" != */ ]] || return 1
  [[ "$candidate" != *"//"* ]] || return 1
  [[ "$candidate" != *"/../"* && "$candidate" != */.. ]] || return 1
  [[ "$candidate" != *"/./"* && "$candidate" != */. ]] || return 1

  for protected in \
    "${HOME:-}" \
    "${HOME:-}/Documents" \
    "${HOME:-}/Desktop" \
    "${HOME:-}/Downloads" \
    "${HOME:-}/Library" \
    "${HOME:-}/Library/Application Support"
  do
    [[ -n "$protected" && "$candidate" != "$protected" ]] || return 1
  done

  protected="${REPO_ROOT:-}"
  if [[ -n "$protected" ]]; then
    case "$candidate/" in
      "$protected/"*) return 1 ;;
    esac
  fi
  protected="${WORKSPACE_ROOT:-}"
  [[ -z "$protected" || "$candidate" != "$protected" ]] || return 1

  IFS='/' read -r -a parts <<<"${candidate#/}"
  for part in "${parts[@]}"; do
    [[ -n "$part" ]] || continue
    prefix="$prefix/$part"
    [[ ! -L "$prefix" ]] || return 1
  done

  nearest="$candidate"
  while [[ ! -e "$nearest" && ! -L "$nearest" ]]; do
    nearest="$(dirname "$nearest")"
  done
  [[ -d "$nearest" && ! -L "$nearest" ]] || return 1
  [[ -O "$nearest" ]] || return 1
}

ensure_app_support_layout() {
  local app_support_dir="$1"
  local directory=""
  if ! validate_viventium_app_support_root "$app_support_dir"; then
    echo "Refusing an unsafe Viventium App Support root." >&2
    return 1
  fi
  for directory in \
    "$app_support_dir" \
    "$app_support_dir/runtime" \
    "$app_support_dir/state" \
    "$app_support_dir/state/continuity" \
    "$app_support_dir/snapshots" \
    "$app_support_dir/logs"
  do
    if [[ -L "$directory" || ( -e "$directory" && ! -d "$directory" ) ]]; then
      echo "Viventium App Support contains an unsafe managed directory" >&2
      return 1
    fi
    (
      umask 077
      mkdir -p "$directory"
    )
    if [[ -L "$directory" || ! -d "$directory" ]]; then
      echo "Viventium App Support directory could not be secured" >&2
      return 1
    fi
    chmod 700 "$directory"
  done
}

path_is_git_repo_root() {
  local candidate="${1:-}"
  [[ -n "$candidate" && -d "$candidate" ]] || return 1
  local git_root=""
  git_root="$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$git_root" ]] || return 1
  [[ "$(cd "$candidate" && pwd -P)" == "$(cd "$git_root" && pwd -P)" ]]
}

canonicalize_existing_dir() {
  local candidate="${1:-}"
  [[ -n "$candidate" && -d "$candidate" ]] || return 1
  (
    cd "$candidate" >/dev/null 2>&1 && pwd -P
  )
}

path_is_within_dir() {
  local candidate="${1:-}"
  local parent_dir="${2:-}"
  local normalized_candidate=""
  local normalized_parent=""

  normalized_candidate="$(canonicalize_existing_dir "$candidate" 2>/dev/null || true)"
  normalized_parent="$(canonicalize_existing_dir "$parent_dir" 2>/dev/null || true)"
  [[ -n "$normalized_candidate" && -n "$normalized_parent" ]] || return 1

  case "${normalized_candidate}/" in
    "${normalized_parent}/"*)
      return 0
      ;;
  esac
  return 1
}

path_is_viventium_runtime_repo_root() {
  local candidate="${1:-}"
  [[ -n "$candidate" && -d "$candidate" ]] || return 1
  [[ -x "$candidate/bin/viventium" ]] || return 1
  [[ -f "$candidate/scripts/viventium/common.sh" ]] || return 1
  [[ -f "$candidate/viventium_v0_4/viventium-librechat-start.sh" ]] || return 1
}

repo_root_uses_macos_protected_folder_access() {
  local repo_root="${1:-}"
  [[ "$(uname -s)" == "Darwin" ]] || return 1

  local protected_root=""
  for protected_root in "$HOME/Documents" "$HOME/Desktop" "$HOME/Downloads"; do
    if path_is_within_dir "$repo_root" "$protected_root"; then
      return 0
    fi
  done
  return 1
}

default_public_install_repo_root() {
  printf '%s\n' "${VIVENTIUM_PUBLIC_INSTALL_DIR:-${VIVENTIUM_INSTALL_DIR:-$HOME/viventium}}"
}

active_runtime_checkout_file() {
  local app_support_dir="${1:-${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}}"
  printf '%s\n' "$app_support_dir/state/active-checkout.json"
}

active_runtime_checkout_repo_root() {
  local app_support_dir="${1:-${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}}"
  local state_file=""
  state_file="$(active_runtime_checkout_file "$app_support_dir")"
  [[ -f "$state_file" ]] || return 1

  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$state_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

repo_root = str(payload.get("repoRoot") or "").strip()
if not repo_root:
    raise SystemExit(1)

candidate = Path(repo_root).expanduser()
if not candidate.is_dir():
    raise SystemExit(1)

print(candidate.resolve())
PY
}

active_runtime_checkout_allows_protected_folder_access() {
  local app_support_dir="${1:-${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}}"
  local state_file=""
  state_file="$(active_runtime_checkout_file "$app_support_dir")"
  [[ -f "$state_file" ]] || return 1

  local python_bin
  python_bin="$(resolve_repo_python)"
  local allowed=""
  allowed="$("$python_bin" - "$state_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("false")
    raise SystemExit(0)

print("true" if payload.get("allowProtectedFolderAccess") is True else "false")
PY
)"
  [[ "$allowed" == "true" ]]
}

active_runtime_checkout_matches_repo_root() {
  local app_support_dir="${1:-}"
  local repo_root="${2:-}"
  local active_repo=""
  [[ -n "$app_support_dir" && -n "$repo_root" ]] || return 1
  active_repo="$(active_runtime_checkout_repo_root "$app_support_dir" 2>/dev/null || true)"
  [[ -n "$active_repo" ]] || return 1
  [[ "$(canonicalize_existing_dir "$active_repo" 2>/dev/null || true)" == "$(canonicalize_existing_dir "$repo_root" 2>/dev/null || true)" ]]
}

active_runtime_checkout_allows_repo_root() {
  local app_support_dir="${1:-}"
  local repo_root="${2:-}"
  active_runtime_checkout_matches_repo_root "$app_support_dir" "$repo_root" &&
    active_runtime_checkout_allows_protected_folder_access "$app_support_dir"
}

resolve_helper_runtime_repo_root() {
  local repo_root="${1:-}"
  local app_support_dir="${2:-${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}}"
  local override="${VIVENTIUM_HELPER_RUNTIME_REPO_ROOT:-}"
  local candidate=""

  candidate="$(active_runtime_checkout_repo_root "$app_support_dir" 2>/dev/null || true)"
  if [[ -n "$candidate" ]] && path_is_viventium_runtime_repo_root "$candidate"; then
    if ! repo_root_uses_macos_protected_folder_access "$candidate" ||
      active_runtime_checkout_allows_protected_folder_access "$app_support_dir"; then
      canonicalize_existing_dir "$candidate"
      return 0
    fi
  fi

  if [[ -n "$override" ]] && path_is_viventium_runtime_repo_root "$override"; then
    canonicalize_existing_dir "$override"
    return 0
  fi

  if [[ -n "$repo_root" ]] && ! repo_root_uses_macos_protected_folder_access "$repo_root"; then
    canonicalize_existing_dir "$repo_root" 2>/dev/null || printf '%s\n' "$repo_root"
    return 0
  fi

  candidate="$(default_public_install_repo_root)"
  if [[ -n "$candidate" ]] && path_is_viventium_runtime_repo_root "$candidate" && ! repo_root_uses_macos_protected_folder_access "$candidate"; then
    canonicalize_existing_dir "$candidate"
    return 0
  fi

  canonicalize_existing_dir "$repo_root" 2>/dev/null || printf '%s\n' "$repo_root"
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
    command -v "$candidate" >/dev/null 2>&1 || continue
    python_runs_inline_script "$candidate" || continue
    printf '%s\n' "$candidate"
    return 0
  done

  echo "Unable to locate a usable Python interpreter." >&2
  return 1
}

resolve_existing_product_python() {
  local required_module="${1:-}"
  local preferred="${VIVENTIUM_PYTHON_BIN:-}"
  local bootstrap_python="$(bootstrap_python_root)/bin/python3"
  local fallback=""
  local candidate=""
  local candidates=()

  [[ -n "$preferred" ]] && candidates+=("$preferred")
  candidates+=("$bootstrap_python")
  fallback="$(resolve_repo_python 2>/dev/null || true)"
  [[ -n "$fallback" ]] && candidates+=("$fallback")

  for candidate in "${candidates[@]}"; do
    if [[ "$candidate" == */* ]]; then
      [[ -x "$candidate" ]] || continue
    elif ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    python_runs_inline_script "$candidate" || continue
    if [[ -n "$required_module" ]] && ! python_has_module "$candidate" "$required_module"; then
      continue
    fi
    printf '%s\n' "$candidate"
    return 0
  done

  return 1
}

bootstrap_python_root() {
  local app_support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
  printf '%s\n' "${VIVENTIUM_BOOTSTRAP_PYTHON_ROOT:-$app_support_dir/state/bootstrap-python}"
}

prepare_bootstrap_python_parent() {
  local root=""
  local app_support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
  root="$(bootstrap_python_root)"

  if [[ -z "${VIVENTIUM_BOOTSTRAP_PYTHON_ROOT:-}" ]]; then
    [[ "$root" == "$app_support_dir/state/bootstrap-python" ]] || return 1
    ensure_app_support_layout "$app_support_dir"
  fi
}

validate_bootstrap_python_root() {
  local root="${1:-}"
  local parent=""
  local logical_parent=""
  local physical_parent=""

  [[ "$root" == /* ]] || return 1
  [[ "$root" != *"/../"* && "$root" != */.. && "$root" != *"/./"* && "$root" != */. ]] || return 1
  [[ "$(basename "$root")" == "bootstrap-python" ]] || return 1
  [[ ! -L "$root" ]] || return 1

  parent="$(dirname "$root")"
  [[ -d "$parent" && ! -L "$parent" && -O "$parent" ]] || return 1
  logical_parent="$(cd -L "$parent" 2>/dev/null && pwd)" || return 1
  physical_parent="$(cd -P "$parent" 2>/dev/null && pwd)" || return 1
  [[ "$logical_parent" == "$physical_parent" ]] || return 1
  [[ "$root" == "$logical_parent/bootstrap-python" ]] || return 1
}

bootstrap_python_lock_dir() {
  local root
  root="$(bootstrap_python_root)"
  printf '%s.lock\n' "$root"
}

bootstrap_python_process_start() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  ps -p "$pid" -o lstart= 2>/dev/null |
    tr -s '[:space:]' ' ' |
    sed 's/^ //; s/ $//'
}

bootstrap_python_path_mtime() {
  local path="${1:-}"
  stat -f '%m' "$path" 2>/dev/null || stat -c '%Y' "$path" 2>/dev/null
}

bootstrap_python_lock_value() {
  local owner_file="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$owner_file"
}

clear_stale_bootstrap_python_lock() {
  local lock_dir="$1"
  local owner_file="$lock_dir/owner"
  local lock_pid=""
  local lock_start=""
  local current_start=""
  local lock_mtime=""
  local now=""
  local candidate=""

  [[ -d "$lock_dir" && ! -L "$lock_dir" && -O "$lock_dir" ]] || return 1

  if [[ -f "$owner_file" && ! -L "$owner_file" && -O "$owner_file" ]]; then
    lock_pid="$(bootstrap_python_lock_value "$owner_file" pid 2>/dev/null || true)"
    lock_start="$(bootstrap_python_lock_value "$owner_file" start 2>/dev/null || true)"
    if [[ "$lock_pid" =~ ^[0-9]+$ && -n "$lock_start" ]]; then
      current_start="$(bootstrap_python_process_start "$lock_pid" 2>/dev/null || true)"
      if [[ -n "$current_start" && "$current_start" == "$lock_start" ]]; then
        return 1
      fi
    fi
  else
    lock_mtime="$(bootstrap_python_path_mtime "$lock_dir" 2>/dev/null || true)"
    now="$(date +%s)"
    [[ "$lock_mtime" =~ ^[0-9]+$ && $((now - lock_mtime)) -ge 2 ]] || return 1
  fi

  rm -f -- "$owner_file" "$lock_dir/pid"
  for candidate in "$lock_dir"/owner.tmp.*; do
    [[ -f "$candidate" && ! -L "$candidate" && -O "$candidate" ]] || continue
    rm -f -- "$candidate"
  done
  rmdir "$lock_dir" 2>/dev/null
}

acquire_bootstrap_python_lock() {
  local root
  root="$(bootstrap_python_root)"
  local lock_dir=""
  local owner_temporary=""
  local process_start=""
  local created=""
  local current_pid="${BASHPID:-$$}"
  local attempt=0

  if ! validate_bootstrap_python_root "$root"; then
    echo "Refusing an unsafe Viventium bootstrap Python root." >&2
    return 1
  fi

  lock_dir="$(bootstrap_python_lock_dir)"
  [[ ! -L "$lock_dir" ]] || {
    echo "Refusing a symlinked Viventium bootstrap Python lock." >&2
    return 1
  }

  while ! mkdir -m 700 "$lock_dir" 2>/dev/null; do
    [[ -d "$lock_dir" && ! -L "$lock_dir" && -O "$lock_dir" ]] || {
      echo "Viventium bootstrap Python lock path is unsafe." >&2
      return 1
    }
    if clear_stale_bootstrap_python_lock "$lock_dir"; then
      continue
    fi
    attempt=$((attempt + 1))
    if (( attempt >= 300 )); then
      echo "Timed out waiting for the Viventium bootstrap Python lock." >&2
      return 1
    fi
    sleep 0.1
  done

  VIVENTIUM_BOOTSTRAP_LOCK_TOKEN="$current_pid.$(date +%s).$RANDOM.$RANDOM"
  process_start="$(bootstrap_python_process_start "$current_pid")" || return 1
  created="$(date +%s)"
  owner_temporary="$lock_dir/owner.tmp.$current_pid"
  (
    umask 077
    {
      printf 'pid=%s\n' "$current_pid"
      printf 'start=%s\n' "$process_start"
      printf 'token=%s\n' "$VIVENTIUM_BOOTSTRAP_LOCK_TOKEN"
      printf 'created=%s\n' "$created"
    } >"$owner_temporary"
  )
  chmod 600 "$owner_temporary"
  mv "$owner_temporary" "$lock_dir/owner"
  export VIVENTIUM_BOOTSTRAP_LOCK_TOKEN
}

release_bootstrap_python_lock() {
  local lock_dir=""
  local owner_file=""
  local recorded_pid=""
  local recorded_start=""
  local recorded_token=""
  local current_start=""
  local current_pid="${BASHPID:-$$}"
  lock_dir="$(bootstrap_python_lock_dir)"
  owner_file="$lock_dir/owner"
  [[ -d "$lock_dir" && ! -L "$lock_dir" && -O "$lock_dir" ]] || return 0
  [[ -f "$owner_file" && ! -L "$owner_file" && -O "$owner_file" ]] || return 0
  recorded_pid="$(bootstrap_python_lock_value "$owner_file" pid 2>/dev/null || true)"
  recorded_start="$(bootstrap_python_lock_value "$owner_file" start 2>/dev/null || true)"
  recorded_token="$(bootstrap_python_lock_value "$owner_file" token 2>/dev/null || true)"
  current_start="$(bootstrap_python_process_start "$current_pid" 2>/dev/null || true)"
  [[ "$recorded_pid" == "$current_pid" ]] || return 0
  [[ -n "$current_start" && "$recorded_start" == "$current_start" ]] || return 0
  [[ -n "${VIVENTIUM_BOOTSTRAP_LOCK_TOKEN:-}" &&
    "$recorded_token" == "$VIVENTIUM_BOOTSTRAP_LOCK_TOKEN" ]] || return 0
  rm -f -- "$owner_file"
  rmdir "$lock_dir" 2>/dev/null || true
  unset VIVENTIUM_BOOTSTRAP_LOCK_TOKEN
}

with_bootstrap_python_lock() (
  acquire_bootstrap_python_lock || exit 1
  trap 'release_bootstrap_python_lock' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  "$@"
)

remove_bootstrap_python_temporary_tree() {
  local root="$1"
  local temporary_path="${2:-}"
  case "$temporary_path" in
    "$root.build."*|"$root.previous."*)
      rm -rf -- "$temporary_path"
      ;;
    "")
      ;;
    *)
      echo "Refusing to remove an unexpected Viventium bootstrap Python path." >&2
      return 1
      ;;
  esac
}

create_bootstrap_python_unlocked() {
  local base_python="$1"
  local root="$2"
  local preferred="${VIVENTIUM_PYTHON_BIN:-}"
  local python_bin="$root/bin/python3"
  local candidate=""
  local resolved_candidate=""
  local seen_candidates="|"
  local staging_root=""
  local staging_python=""
  local previous_root=""
  local candidates=()

  if [[ -x "$python_bin" ]]; then
    if python_runs_inline_script "$python_bin" &&
      "$python_bin" -m pip --version >/dev/null 2>&1
    then
      printf '%s\n' "$python_bin"
      return 0
    fi
  fi

  candidates+=("$base_python")
  [[ -n "$preferred" ]] && candidates+=("$preferred")
  candidates+=(python3.12 python3.11 python3.10 python3 python)

  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    resolved_candidate="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$resolved_candidate" ]] || continue
    case "$seen_candidates" in
      *"|$resolved_candidate|"*) continue ;;
    esac
    seen_candidates="${seen_candidates}${resolved_candidate}|"
    python_runs_inline_script "$candidate" || continue

    staging_root="$(mktemp -d "$root.build.XXXXXX")" || return 1
    chmod 700 "$staging_root"
    staging_python="$staging_root/bin/python3"
    if "$candidate" -m venv "$staging_root" >/dev/null 2>&1 &&
      [[ -x "$staging_python" ]] &&
      python_runs_inline_script "$staging_python" &&
      "$staging_python" -m pip --version >/dev/null 2>&1
    then
      if [[ -e "$root" ]]; then
        previous_root="$(mktemp -d "$root.previous.XXXXXX")" || {
          remove_bootstrap_python_temporary_tree "$root" "$staging_root"
          return 1
        }
        rmdir "$previous_root"
        if ! mv "$root" "$previous_root"; then
          remove_bootstrap_python_temporary_tree "$root" "$staging_root"
          return 1
        fi
      fi
      if ! mv "$staging_root" "$root"; then
        [[ -n "$previous_root" && -e "$previous_root" ]] && mv "$previous_root" "$root" 2>/dev/null || true
        remove_bootstrap_python_temporary_tree "$root" "$staging_root"
        return 1
      fi
      remove_bootstrap_python_temporary_tree "$root" "$previous_root"
      printf '%s\n' "$python_bin"
      return 0
    fi
    remove_bootstrap_python_temporary_tree "$root" "$staging_root"
    staging_root=""
  done

  echo "Failed to create a usable Viventium bootstrap Python environment with the available interpreters." >&2
  return 1
}

create_bootstrap_python() {
  local base_python="$1"
  local root
  root="$(bootstrap_python_root)"

  prepare_bootstrap_python_parent || return 1
  if ! validate_bootstrap_python_root "$root"; then
    echo "Refusing an unsafe Viventium bootstrap Python root." >&2
    return 1
  fi
  with_bootstrap_python_lock create_bootstrap_python_unlocked "$base_python" "$root"
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

ensure_python_module_unlocked() {
  local target_python="$1"
  local module_name="$2"
  local package_name="$3"

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

  if python_uses_bootstrap_root "$target_python"; then
    with_bootstrap_python_lock \
      ensure_python_module_unlocked "$target_python" "$module_name" "$package_name"
  else
    ensure_python_module_unlocked "$target_python" "$module_name" "$package_name"
  fi
}

ensure_python_requirements_file_unlocked() {
  local target_python="$1"
  local requirements_file="$2"
  local stamp_path=""
  local stamp_temporary=""

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

  stamp_temporary="${stamp_path}.tmp.$$"
  printf '%s\n' "$requirements_hash" >"$stamp_temporary"
  mv "$stamp_temporary" "$stamp_path"
  printf '%s\n' "$target_python"
}

ensure_python_requirements_file() {
  local python_bin="$1"
  local requirements_file="$2"
  local target_python="$python_bin"

  [[ -f "$requirements_file" ]] || {
    echo "Installer requirements file not found: $requirements_file" >&2
    return 1
  }

  target_python="$(create_bootstrap_python "$python_bin")" || return 1
  if [[ ! -x "$target_python" ]]; then
    target_python="$python_bin"
  fi

  if python_uses_bootstrap_root "$target_python"; then
    with_bootstrap_python_lock \
      ensure_python_requirements_file_unlocked "$target_python" "$requirements_file"
  else
    ensure_python_requirements_file_unlocked "$target_python" "$requirements_file"
  fi
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
