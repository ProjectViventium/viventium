#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_SH="$REPO_ROOT/scripts/viventium/common.sh"

if [[ -f "$COMMON_SH" ]]; then
  # shellcheck source=/dev/null
  source "$COMMON_SH"
fi

CONFIG_HOME=""
SNAPSHOT_DIR=""
APPLY_TELEGRAM=false
ALLOW_OLDER_SNAPSHOT=false
MARK_RECALL_STALE=false

usage() {
  cat <<'USAGE'
Usage:
  scripts/viventium/restore.sh --config-home <path> [options]

Options:
  --snapshot-dir <path>       Snapshot directory to inspect.
  --apply-telegram            Restore Telegram user configs from the snapshot.
  --allow-older-snapshot      Allow applying a snapshot whose continuity state is older than live.
  --mark-recall-stale         Write the recall rebuild-required marker after restore follow-through.
USAGE
}

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
    --allow-older-snapshot)
      ALLOW_OLDER_SNAPSHOT=true
      shift
      ;;
    --mark-recall-stale)
      MARK_RECALL_STALE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
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

RUNTIME_DIR="${VIVENTIUM_RUNTIME_DIR:-$CONFIG_HOME/runtime}"
RUNTIME_ENV="$RUNTIME_DIR/runtime.env"
RUNTIME_PROFILE="${VIVENTIUM_RUNTIME_PROFILE:-$(awk -F= '/^VIVENTIUM_RUNTIME_PROFILE=/{print $2}' "$RUNTIME_ENV" 2>/dev/null | head -n 1 || true)}"
if [[ -z "$RUNTIME_PROFILE" ]]; then
  RUNTIME_PROFILE="isolated"
fi

if declare -F continuity_audit_dir >/dev/null 2>&1; then
  AUDIT_DIR="$(continuity_audit_dir "$CONFIG_HOME")"
else
  AUDIT_DIR="$CONFIG_HOME/state/continuity"
fi
mkdir -p "$AUDIT_DIR"

if declare -F recall_rebuild_required_file >/dev/null 2>&1; then
  RECALL_MARKER_FILE="$(recall_rebuild_required_file "$CONFIG_HOME" "$RUNTIME_PROFILE")"
else
  RECALL_MARKER_FILE="$CONFIG_HOME/state/runtime/$RUNTIME_PROFILE/continuity/recall-rebuild-required.json"
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LIVE_MANIFEST="$AUDIT_DIR/restore-live-$TIMESTAMP.json"
COMPARISON_PATH="$AUDIT_DIR/restore-compare-$TIMESTAMP.json"
SNAPSHOT_MANIFEST="$SNAPSHOT_DIR/continuity-manifest.json"
SNAPSHOT_LABEL="$SNAPSHOT_DIR"
LIVE_MANIFEST_LABEL="$LIVE_MANIFEST"
COMPARISON_LABEL="$COMPARISON_PATH"
RECALL_MARKER_LABEL="$RECALL_MARKER_FILE"
if declare -F public_safe_path_label >/dev/null 2>&1; then
  SNAPSHOT_LABEL="$(public_safe_path_label "$SNAPSHOT_DIR")"
  LIVE_MANIFEST_LABEL="$(public_safe_path_label "$LIVE_MANIFEST")"
  COMPARISON_LABEL="$(public_safe_path_label "$COMPARISON_PATH")"
  RECALL_MARKER_LABEL="$(public_safe_path_label "$RECALL_MARKER_FILE")"
fi

SNAPSHOT_FILE_COUNT="$(
  find "$SNAPSHOT_DIR" -type f 2>/dev/null | wc -l | tr -d ' '
)"
echo "[restore] Inspecting snapshot root: $SNAPSHOT_LABEL"
echo "[restore] Snapshot payload summary: ${SNAPSHOT_FILE_COUNT:-0} files"

python3 "$REPO_ROOT/scripts/viventium/continuity_audit.py" capture \
  --repo-root "$REPO_ROOT" \
  --app-support-dir "$CONFIG_HOME" \
  --runtime-dir "$RUNTIME_DIR" \
  --label "restore-live" \
  --output "$LIVE_MANIFEST" >/dev/null
echo "[restore] Live continuity audit: $LIVE_MANIFEST_LABEL"

# Legacy snapshots may legitimately predate continuity manifests. Treat that as an operator-visible
# warning, not an automatic hard failure, unless a real older-surface comparison proves rollback.
COMPARE_STATUS="warning"
if [[ -f "$SNAPSHOT_MANIFEST" ]]; then
  python3 "$REPO_ROOT/scripts/viventium/continuity_audit.py" compare \
    --snapshot-manifest "$SNAPSHOT_MANIFEST" \
    --live-manifest "$LIVE_MANIFEST" \
    --output "$COMPARISON_PATH" >/dev/null
  COMPARE_STATUS="$(
    python3 - "$COMPARISON_PATH" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload.get("status") or "warning")
PY
)"
  echo "[restore] Continuity comparison: $COMPARISON_LABEL"
  python3 - "$COMPARISON_PATH" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
older = payload.get("olderSurfaces") or []
warnings = payload.get("warnings") or []
errors = payload.get("errors") or []
status = payload.get("status") or "warning"
print(f"[restore] Continuity status: {status}")
if older:
    print("[restore] Older snapshot surfaces: " + ", ".join(older))
for warning in warnings:
    print(f"[restore] Warning: {warning}")
for error in errors:
    print(f"[restore] Error: {error}")
PY
  if [[ "$COMPARE_STATUS" == "error" && "$ALLOW_OLDER_SNAPSHOT" != "true" ]]; then
    echo "[restore] Refusing to apply an older continuity snapshot without --allow-older-snapshot." >&2
    exit 1
  fi
else
  echo "[restore] No continuity manifest found in the snapshot; age comparison is unavailable." >&2
fi

if [[ "$APPLY_TELEGRAM" == "true" && -d "$SNAPSHOT_DIR/telegram/user_configs" ]]; then
  target="${VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR:-$REPO_ROOT/viventium_v0_4/telegram-viventium/TelegramVivBot/user_configs}"
  backup_dir="$AUDIT_DIR/restore-backups/$TIMESTAMP/telegram-user_configs"
  backup_dir_label="$backup_dir"
  target_label="$target"
  if declare -F public_safe_path_label >/dev/null 2>&1; then
    backup_dir_label="$(public_safe_path_label "$backup_dir")"
    target_label="$(public_safe_path_label "$target")"
  fi
  if [[ -d "$target" ]]; then
    mkdir -p "$backup_dir"
    if ! cp -R "$target"/. "$backup_dir/" 2>/dev/null; then
      echo "[restore] Failed to back up current Telegram user configs to $backup_dir_label" >&2
      exit 1
    fi
    echo "[restore] Backed up current Telegram user configs to $backup_dir_label"
  fi
  mkdir -p "$target"
  cp -R "$SNAPSHOT_DIR/telegram/user_configs"/. "$target/"
  echo "[restore] Telegram user configs restored to $target_label"
fi

if [[ "$MARK_RECALL_STALE" == "true" ]]; then
  mkdir -p "$(dirname "$RECALL_MARKER_FILE")"
  python3 - "$RECALL_MARKER_FILE" "$SNAPSHOT_LABEL" "$TIMESTAMP" <<'PY'
import json
import sys
from pathlib import Path

marker_path = Path(sys.argv[1])
snapshot_label = sys.argv[2]
captured_at = sys.argv[3]
payload = {
    "schemaVersion": 1,
    "reason": "restore-follow-through",
    "snapshotLabel": snapshot_label,
    "capturedAt": captured_at,
}
marker_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  echo "[restore] Wrote recall rebuild-required marker to $RECALL_MARKER_LABEL"
fi

echo "[restore] Manual restore follow-ups:"
echo "  - Mongo archives: use viventium_v0_4/viventium-db-restore-from-export.sh"
echo "  - Skyvern dump: import <selected snapshot>/skyvern/skyvern.postgres.sql.gz into the Skyvern Postgres container"
echo "  - Rebuild runtime files: bin/viventium compile-config"
echo "  - If you restore Mongo or recall-derived state, rerun this command with --mark-recall-stale before trusting vector-backed recall"
