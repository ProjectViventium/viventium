#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
COMMON_SH="$PROJECT_ROOT/scripts/viventium/common.sh"

if [[ -f "$COMMON_SH" ]]; then
  # shellcheck source=/dev/null
  source "$COMMON_SH"
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

APP_SUPPORT_DIR="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
PRIVATE_REPO_DIR="${VIVENTIUM_PRIVATE_REPO_DIR:-$(discover_private_repo_dir "$WORKSPACE_ROOT" "$PROJECT_ROOT" || true)}"
PRIVATE_HELPER_PATH="${PRIVATE_REPO_DIR:+$PRIVATE_REPO_DIR/viventium_v0_4/viventium-local-state-snapshot.sh}"

usage() {
  cat <<'USAGE'
Usage:
  ./viventium_v0_4/viventium-local-state-snapshot.sh [options]

This public wrapper always writes a metadata-only continuity manifest under the selected snapshot
root. When a private companion helper is available, it is invoked first to add the bounded
secret-bearing payload into the same snapshot root.

Options:
  --output-root <path>   Snapshot root. Defaults to ~/Library/Application Support/Viventium/snapshots
  -h, --help             Show this help text.
USAGE
}

find_latest_snapshot_dir() {
  local output_root="$1"
  local latest_file="$output_root/LATEST_PATH"
  if [[ -f "$latest_file" ]]; then
    local latest_path=""
    latest_path="$(tr -d '\r' <"$latest_file" | head -n 1)"
    if [[ -n "$latest_path" && -d "$latest_path" ]]; then
      printf '%s\n' "$latest_path"
      return 0
    fi
  fi

  local candidate=""
  candidate="$(
    find "$output_root" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort | tail -n 1 || true
  )"
  if [[ -n "$candidate" && -d "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

create_manifest_only_snapshot_dir() {
  local output_root="$1"
  local timestamp=""
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local snapshot_dir="$output_root/$timestamp"
  mkdir -p "$snapshot_dir"
  printf '%s\n' "$snapshot_dir" >"$output_root/LATEST_PATH"
  printf '%s\n' "$snapshot_dir"
}

write_continuity_manifest() {
  local snapshot_dir="$1"
  local manifest_path="$snapshot_dir/continuity-manifest.json"
  local runtime_dir="${VIVENTIUM_RUNTIME_DIR:-$APP_SUPPORT_DIR/runtime}"
  python3 "$PROJECT_ROOT/scripts/viventium/continuity_audit.py" capture \
    --repo-root "$PROJECT_ROOT" \
    --app-support-dir "$APP_SUPPORT_DIR" \
    --runtime-dir "$runtime_dir" \
    --label "snapshot" \
    --output "$manifest_path" >/dev/null
  printf '%s\n' "$manifest_path"
}

OUTPUT_ROOT="$APP_SUPPORT_DIR/snapshots"
ORIGINAL_ARGS=("$@")
PARSE_ARGS=("$@")

index=0
while [[ $index -lt ${#PARSE_ARGS[@]} ]]; do
  arg="${PARSE_ARGS[$index]}"
  case "$arg" in
    --output-root)
      if [[ $((index + 1)) -ge ${#PARSE_ARGS[@]} ]]; then
        echo "Missing value for --output-root" >&2
        exit 1
      fi
      OUTPUT_ROOT="${PARSE_ARGS[$((index + 1))]}"
      index=$((index + 2))
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      index=$((index + 1))
      ;;
  esac
done

mkdir -p "$OUTPUT_ROOT"

if [[ -n "$PRIVATE_HELPER_PATH" && -x "$PRIVATE_HELPER_PATH" ]]; then
  "$PRIVATE_HELPER_PATH" "${ORIGINAL_ARGS[@]}"
fi

SNAPSHOT_DIR="$(find_latest_snapshot_dir "$OUTPUT_ROOT" || true)"
if [[ -z "$SNAPSHOT_DIR" ]]; then
  SNAPSHOT_DIR="$(create_manifest_only_snapshot_dir "$OUTPUT_ROOT")"
fi

MANIFEST_PATH="$(write_continuity_manifest "$SNAPSHOT_DIR")"
if declare -F public_safe_path_label >/dev/null 2>&1; then
  echo "Continuity manifest written to $(public_safe_path_label "$MANIFEST_PATH")"
else
  echo "Continuity manifest written."
fi

if [[ ! -x "$PRIVATE_HELPER_PATH" ]]; then
  echo "No private companion snapshot helper detected; captured metadata-only continuity snapshot." >&2
fi
