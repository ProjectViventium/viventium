#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR=""
case "$SCRIPT_PATH" in
  ""|-|bash|sh|stdin|/dev/fd/*|/proc/self/fd/*)
    ;;
  *)
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" 2>/dev/null && pwd || true)"
    ;;
esac

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/bin/viventium" && -x "$SCRIPT_DIR/bin/viventium" ]]; then
  exec "$SCRIPT_DIR/bin/viventium" install "$@"
fi

REPO_URL="${VIVENTIUM_REPO_URL:-https://github.com/ProjectViventium/viventium.git}"
INSTALL_DIR="${VIVENTIUM_INSTALL_DIR:-${VIVENTIUM_INSTALL_ROOT:-$HOME/viventium}}"
BRANCH="${VIVENTIUM_REPO_BRANCH:-main}"

mkdir -p "$(dirname "$INSTALL_DIR")"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  git clone --depth 1 --single-branch --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

exec "$INSTALL_DIR/bin/viventium" install "$@"
