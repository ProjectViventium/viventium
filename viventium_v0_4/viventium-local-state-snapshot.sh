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
PYTHON_BIN="${VIVENTIUM_PYTHON_BIN:-python3}"

usage() {
  cat <<'USAGE'
Usage:
  ./viventium_v0_4/viventium-local-state-snapshot.sh [options]

This public wrapper first attempts a complete, secret-excluding logical snapshot of canonical
config, Mongo history/memory/agents, uploaded files, and schedules. Provider/channel credentials
are never exported and must be reconnected after restore. If complete capture prerequisites are
unavailable, it writes an honest metadata-only continuity audit instead.

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
  local snapshot_dir=""
  snapshot_dir="$(mktemp -d "$output_root/${timestamp}-metadata.XXXXXX")"
  chmod 700 "$snapshot_dir" >/dev/null 2>&1 || true
  printf '%s\n' "metadata-only" >"$snapshot_dir/.viventium-metadata-only"
  chmod 600 "$snapshot_dir/.viventium-metadata-only" >/dev/null 2>&1 || true
  printf '%s\n' "$snapshot_dir"
}

publish_latest_snapshot_path() {
  local snapshot_dir="$1"
  local output_root="$2"
  local pointer_tmp=""
  pointer_tmp="$(mktemp "$output_root/.LATEST_PATH.XXXXXX")"
  chmod 600 "$pointer_tmp" >/dev/null 2>&1 || true
  printf '%s\n' "$snapshot_dir" >"$pointer_tmp"
  mv -f "$pointer_tmp" "$output_root/LATEST_PATH"
}

snapshot_dir_is_within_output_root() {
  local snapshot_dir="$1"
  local output_root="$2"
  local resolved_snapshot=""
  local resolved_output_root=""
  [[ -d "$snapshot_dir" && -d "$output_root" ]] || return 1
  resolved_snapshot="$(cd "$snapshot_dir" && pwd -P)"
  resolved_output_root="$(cd "$output_root" && pwd -P)"
  [[ "$resolved_snapshot" == "$resolved_output_root"/* ]]
}

snapshot_dir_is_structurally_valid_complete_bundle() {
  local snapshot_dir="$1"
  "$PYTHON_BIN" "$PROJECT_ROOT/scripts/viventium/continuity_bundle.py" validate \
    --snapshot-dir "$snapshot_dir" \
    --json >/dev/null 2>&1
}

write_continuity_manifest() {
  local snapshot_dir="$1"
  local manifest_path="$snapshot_dir/continuity-manifest.json"
  local runtime_dir="${VIVENTIUM_RUNTIME_DIR:-$APP_SUPPORT_DIR/runtime}"
  "$PYTHON_BIN" "$PROJECT_ROOT/scripts/viventium/continuity_audit.py" capture \
    --repo-root "$PROJECT_ROOT" \
    --app-support-dir "$APP_SUPPORT_DIR" \
    --runtime-dir "$runtime_dir" \
    --label "snapshot" \
    --output "$manifest_path" >/dev/null || return $?
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

PREVIOUS_SNAPSHOT_DIR="$(find_latest_snapshot_dir "$OUTPUT_ROOT" || true)"
SNAPSHOT_DIR=""
SNAPSHOT_KIND="metadata-only"
if [[ -n "$PRIVATE_HELPER_PATH" && -x "$PRIVATE_HELPER_PATH" ]]; then
  "$PRIVATE_HELPER_PATH" "${ORIGINAL_ARGS[@]}"
  PRIVATE_SNAPSHOT_DIR="$(find_latest_snapshot_dir "$OUTPUT_ROOT" || true)"
  if [[ -z "$PRIVATE_SNAPSHOT_DIR" || "$PRIVATE_SNAPSHOT_DIR" == "$PREVIOUS_SNAPSHOT_DIR" ]]; then
    echo "Private snapshot helper did not record a new snapshot; preserving prior snapshots and capturing a new metadata-only audit." >&2
  elif ! snapshot_dir_is_within_output_root "$PRIVATE_SNAPSHOT_DIR" "$OUTPUT_ROOT" || \
    ! snapshot_dir_is_structurally_valid_complete_bundle "$PRIVATE_SNAPSHOT_DIR"; then
    echo "Private snapshot helper did not create a structurally valid complete bundle; preserving prior snapshots and capturing a new metadata-only audit." >&2
  else
    SNAPSHOT_DIR="$PRIVATE_SNAPSHOT_DIR"
    SNAPSHOT_KIND="private-helper"
  fi
fi

if [[ -z "$SNAPSHOT_DIR" ]]; then
  PUBLIC_CAPTURE_STATUS=0
  PUBLIC_CAPTURE_JSON="$(
    "$PYTHON_BIN" "$PROJECT_ROOT/scripts/viventium/continuity_bundle.py" capture \
      --repo-root "$PROJECT_ROOT" \
      --app-support-dir "$APP_SUPPORT_DIR" \
      --runtime-dir "${VIVENTIUM_RUNTIME_DIR:-$APP_SUPPORT_DIR/runtime}" \
      --output-root "$OUTPUT_ROOT" \
      --json
  )" || PUBLIC_CAPTURE_STATUS=$?
  if [[ "$PUBLIC_CAPTURE_STATUS" -eq 0 ]]; then
    SNAPSHOT_DIR="$(
      "$PYTHON_BIN" - "$PUBLIC_CAPTURE_JSON" <<'PY'
import json
import sys
print(json.loads(sys.argv[1])["snapshotDir"])
PY
    )"
    if snapshot_dir_is_within_output_root "$SNAPSHOT_DIR" "$OUTPUT_ROOT" && \
      snapshot_dir_is_structurally_valid_complete_bundle "$SNAPSHOT_DIR"; then
      SNAPSHOT_KIND="public-complete"
    else
      echo "Public complete snapshot did not pass final containment and integrity validation; creating metadata-only evidence." >&2
      SNAPSHOT_DIR=""
    fi
  else
    echo "Complete snapshot prerequisites are unavailable; creating metadata-only continuity evidence." >&2
  fi
fi

if [[ -z "$SNAPSHOT_DIR" ]]; then
  SNAPSHOT_DIR="$(create_manifest_only_snapshot_dir "$OUTPUT_ROOT")"
fi

MANIFEST_PATH="$(write_continuity_manifest "$SNAPSHOT_DIR")"
if [[ "$SNAPSHOT_KIND" != "metadata-only" ]] && ! snapshot_dir_is_structurally_valid_complete_bundle "$SNAPSHOT_DIR"; then
  echo "Complete snapshot failed final post-audit validation; LATEST_PATH was not changed." >&2
  exit 4
fi
publish_latest_snapshot_path "$SNAPSHOT_DIR" "$OUTPUT_ROOT"
if declare -F public_safe_path_label >/dev/null 2>&1; then
  echo "Continuity manifest written to $(public_safe_path_label "$MANIFEST_PATH")"
else
  echo "Continuity manifest written."
fi

if [[ "$SNAPSHOT_KIND" == "metadata-only" ]]; then
  echo "Captured a metadata-only continuity audit. No recoverable backup payload was created." >&2
else
  echo "Captured a complete continuity snapshot. Account and channel reauthentication is required after restore." >&2
fi
