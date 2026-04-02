#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

discover_private_repo_dir() {
  local workspace_root="$1"
  local repo_root="${2:-$workspace_root}"
  local candidate=""
  local candidates=(
    "$repo_root/private-companion-repo"
    "$workspace_root/private-companion-repo"
    "$workspace_root/private-companion-repo"
    "$workspace_root/.private-companion-repo"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PRIVATE_REPO_DIR="${VIVENTIUM_PRIVATE_REPO_DIR:-$(discover_private_repo_dir "$WORKSPACE_ROOT" "$PROJECT_ROOT" || true)}"
PRIVATE_HELPER_PATH="${PRIVATE_REPO_DIR:+$PRIVATE_REPO_DIR/viventium_v0_4/viventium-local-state-snapshot.sh}"

usage() {
  cat <<'USAGE'
Usage:
  ./viventium_v0_4/viventium-local-state-snapshot.sh [options]

This public wrapper delegates to a private companion helper when available.
Set VIVENTIUM_PRIVATE_REPO_DIR or clone the private helper into one of:
  - ./private-companion-repo
  - ../private-companion-repo
  - ../private-companion-repo
  - ../.private-companion-repo
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -n "$PRIVATE_HELPER_PATH" && -x "$PRIVATE_HELPER_PATH" ]]; then
  exec "$PRIVATE_HELPER_PATH" "$@"
fi

echo "Private local-state snapshot helper not found." >&2
usage >&2
exit 1
