#!/usr/bin/env bash
set -euo pipefail

CONFIG_HOME=""
SNAPSHOT_DIR=""
APPLY_TELEGRAM=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-home)
      CONFIG_HOME="${2:-}"
      shift 2
      ;;
    --snapshot-dir)
      SNAPSHOT_DIR="${2:-}"
      shift 2
      ;;
    --apply-telegram)
      APPLY_TELEGRAM=true
      shift
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$CONFIG_HOME" ]]; then
  echo "Missing --config-home" >&2
  exit 1
fi

if [[ -z "$SNAPSHOT_DIR" ]]; then
  latest_file="$CONFIG_HOME/snapshots/LATEST_PATH"
  if [[ -f "$latest_file" ]]; then
    SNAPSHOT_DIR="$(cat "$latest_file")"
  else
    echo "No snapshot provided and no LATEST_PATH found under $CONFIG_HOME/snapshots" >&2
    exit 1
  fi
fi

if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  echo "Snapshot directory not found: $SNAPSHOT_DIR" >&2
  exit 1
fi

echo "[restore] Inspecting snapshot: $SNAPSHOT_DIR"
find "$SNAPSHOT_DIR" -maxdepth 2 -type f | sort

if [[ "$APPLY_TELEGRAM" == "true" && -d "$SNAPSHOT_DIR/telegram/user_configs" ]]; then
  target="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/viventium_v0_4/telegram-viventium/TelegramVivBot/user_configs"
  mkdir -p "$target"
  cp -R "$SNAPSHOT_DIR/telegram/user_configs"/. "$target/"
  echo "[restore] Telegram user configs restored to $target"
fi

echo "[restore] Manual restore follow-ups:"
echo "  - Mongo archives: use viventium_v0_4/viventium-db-restore-from-export.sh"
echo "  - Skyvern dump: import $SNAPSHOT_DIR/skyvern/skyvern.postgres.sql.gz into the Skyvern Postgres container"
echo "  - Rebuild runtime files: bin/viventium compile-config"
