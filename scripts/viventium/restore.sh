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
TARGET_CONFIG_HOME_EXPLICIT=false
TARGET_REPO_ROOT=""
TARGET_MONGO_URI=""
TARGET_MONGO_DATA_PATH=""
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
  --target-config-home <path> Empty independent App Support target for restore.
  --target-repo-root <path>   Fresh independent Viventium checkout that will own restored uploads.
  --target-mongo-uri <uri>    Empty credential-free loopback Mongo database for the independent target.
  --target-mongo-data-path <path>
                              Owner-only independent Mongo data directory. Supplying it makes the
                              restored target restartable with the same pinned persistence store.
  --config-home <path>        Legacy alias for --target-config-home.
  --snapshot-dir <path>       Snapshot directory to inspect.
  --apply-telegram            Reserved; channel credentials always require reauthentication.
  --allow-older-snapshot      Reserved; unchecksummed legacy age metadata is not trusted.
  --mark-recall-stale         Compatibility flag; transactional restore always marks Recall stale.
  --validate-only             Validate bundle completeness and hashes without changing target state.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-home)
      CONFIG_HOME="${2:-}"
      CONFIG_HOME_EXPLICIT=true
      TARGET_CONFIG_HOME_EXPLICIT=true
      shift 2
      ;;
    --target-config-home)
      TARGET_CONFIG_HOME="${2:-}"
      TARGET_CONFIG_HOME_EXPLICIT=true
      shift 2
      ;;
    --target-repo-root)
      TARGET_REPO_ROOT="${2:-}"
      shift 2
      ;;
    --target-mongo-uri)
      TARGET_MONGO_URI="${2:-}"
      shift 2
      ;;
    --target-mongo-data-path)
      TARGET_MONGO_DATA_PATH="${2:-}"
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
  BUNDLE_RECOVERABLE="$("$VALIDATION_PYTHON" - "$BUNDLE_VALIDATION_JSON" <<'PY'
import json
import sys
print("true" if json.loads(sys.argv[1]).get("recoverable") is True else "false")
PY
)"
  if [[ "$BUNDLE_RECOVERABLE" == "true" ]]; then
    echo "Complete bundle structure, logical data, and transactional restore contract validation passed; target state was not changed."
  else
    echo "Bundle structure and payload-integrity validation passed, but this legacy candidate is not independently restore-ready; target state was not changed."
  fi
  exit 0
fi

if [[ "$APPLY_TELEGRAM" == "true" || "$ALLOW_OLDER_SNAPSHOT" == "true" ]]; then
  echo "[restore] Legacy channel/age apply options are not accepted; credentials require reauthentication and bundle hashes are authoritative." >&2
  echo "[restore] Target state was not changed." >&2
  exit 4
fi
if [[ "$TARGET_CONFIG_HOME_EXPLICIT" != "true" || -z "$TARGET_REPO_ROOT" || -z "$TARGET_MONGO_URI" ]]; then
  echo "[restore] Apply requires an explicit empty independent App Support target, fresh target checkout, and empty loopback Mongo database." >&2
  echo "[restore] Target state was not changed." >&2
  exit 4
fi

RESTORE_ARGS=(
  restore
  --snapshot-dir "$SNAPSHOT_DIR"
  --target-config-home "$CONFIG_HOME"
  --target-repo-root "$TARGET_REPO_ROOT"
  --target-mongo-uri "$TARGET_MONGO_URI"
)
if [[ -n "$TARGET_MONGO_DATA_PATH" ]]; then
  RESTORE_ARGS+=(--target-mongo-data-path "$TARGET_MONGO_DATA_PATH")
fi
exec "$VALIDATION_PYTHON" "$REPO_ROOT/scripts/viventium/continuity_bundle.py" "${RESTORE_ARGS[@]}"
