#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_SH="$REPO_ROOT/scripts/viventium/common.sh"

if [[ -f "$COMMON_SH" ]]; then
  # shellcheck source=/dev/null
  source "$COMMON_SH"
fi

CONFIG_HOME="${VIVENTIUM_DEFAULT_CONFIG_HOME:-${VIVENTIUM_APP_SUPPORT_DIR:-}}"
CONFIG_HOME_EXPLICIT=false
TARGET_CONFIG_HOME=""
SNAPSHOT_DIR=""
APPLY_TELEGRAM=false
ALLOW_OLDER_SNAPSHOT=false
MARK_RECALL_STALE=false
VALIDATE_ONLY=false
VALIDATION_PYTHON="${VIVENTIUM_PYTHON_BIN:-python3}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/viventium/restore.sh --target-config-home <path> [options]

Options:
  --target-config-home <path> Independent App Support target for restore. Defaults to the selected App Support path.
  --config-home <path>        Legacy alias for --target-config-home.
  --snapshot-dir <path>       Snapshot directory to inspect.
  --apply-telegram            Reserved; currently refused without changing channel state.
  --allow-older-snapshot      Reserved; unchecksummed legacy age metadata is not trusted.
  --mark-recall-stale         Reserved; currently refused without changing target state.
  --validate-only             Validate bundle completeness and hashes without changing target state.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-home)
      CONFIG_HOME="${2:-}"
      CONFIG_HOME_EXPLICIT=true
      shift 2
      ;;
    --target-config-home)
      TARGET_CONFIG_HOME="${2:-}"
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
    --validate-only)
      VALIDATE_ONLY=true
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

if [[ -n "$TARGET_CONFIG_HOME" && "$CONFIG_HOME_EXPLICIT" == "true" && "$TARGET_CONFIG_HOME" != "$CONFIG_HOME" ]]; then
  echo "Use either --target-config-home or --config-home, not two different restore targets." >&2
  exit 1
fi
if [[ -n "$TARGET_CONFIG_HOME" ]]; then
  CONFIG_HOME="$TARGET_CONFIG_HOME"
fi
if [[ -z "$CONFIG_HOME" ]]; then
  echo "Missing --target-config-home" >&2
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
  echo "Snapshot directory was not found; select an existing verified Viventium bundle." >&2
  exit 1
fi

if [[ -f "$SNAPSHOT_DIR/.viventium-metadata-only" ]]; then
  echo "Selected snapshot is a metadata-only continuity audit, not a recoverable backup; restore is refused." >&2
  echo "Review available snapshots and rerun with --snapshot-dir pointing to a complete bundle candidate." >&2
  exit 1
fi

OVERLAP_STATUS="$("$VALIDATION_PYTHON" - "$SNAPSHOT_DIR" "$CONFIG_HOME" <<'PY'
import os
import sys

snapshot = os.path.realpath(sys.argv[1])
target = os.path.realpath(sys.argv[2])
common = os.path.commonpath([snapshot, target])
print("unsafe" if common in {snapshot, target} else "separate")
PY
)"
if [[ "$OVERLAP_STATUS" != "separate" ]]; then
  echo "Snapshot and restore target overlap; restore is refused before changing target state." >&2
  exit 3
fi

BUNDLE_VALIDATION_STATUS=0
BUNDLE_VALIDATION_JSON="$(
  "$VALIDATION_PYTHON" "$REPO_ROOT/scripts/viventium/continuity_bundle.py" validate \
    --snapshot-dir "$SNAPSHOT_DIR" \
    --json
)" || BUNDLE_VALIDATION_STATUS=$?
if [[ "$BUNDLE_VALIDATION_STATUS" -ne 0 ]]; then
  BUNDLE_VALIDATION_MESSAGE="$(
    "$VALIDATION_PYTHON" - "$BUNDLE_VALIDATION_JSON" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError):
    print("bundle validation did not return readable status")
else:
    print(str(payload.get("message") or "bundle validation failed"))
PY
  )"
  echo "Selected snapshot is not a structurally valid complete Viventium bundle candidate: $BUNDLE_VALIDATION_MESSAGE." >&2
  echo "Restore was refused before creating or changing target state." >&2
  exit "$BUNDLE_VALIDATION_STATUS"
fi
if [[ "$VALIDATE_ONLY" == "true" ]]; then
  echo "Complete bundle structure and payload-integrity validation passed; target state was not changed and independent recovery is not proven."
  exit 0
fi

if [[ "$APPLY_TELEGRAM" == "true" || "$ALLOW_OLDER_SNAPSHOT" == "true" || "$MARK_RECALL_STALE" == "true" ]]; then
  echo "[restore] Requested apply options are unavailable until the transactional restore engine is implemented." >&2
fi
echo "[restore] PARTIAL: bundle validation passed, but the public apply engine is not implemented; target state was not changed." >&2
exit 4
