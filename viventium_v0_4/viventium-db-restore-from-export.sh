#!/usr/bin/env bash
# VIVENTIUM START
# Purpose: Restore local MongoDB from a local legacy export folder (no cloud access).
# Scope: LibreChat Mongo + rag-db Mongo, with optional schedules.sqlite replacement.
# VIVENTIUM END

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIBRECHAT_DIR="$SCRIPT_DIR/LibreChat"
ARTIFACTS_ROOT="${VIVENTIUM_ARTIFACTS_DIR:-$CORE_DIR/.viventium/artifacts}"
ARTIFACT_CATEGORY="db-restore-from-export"

VIVENTIUM_RUNTIME_PROFILE="${VIVENTIUM_RUNTIME_PROFILE:-isolated}"
if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
  DEFAULT_MONGO_PORT=27117
  DEFAULT_MONGO_CONTAINER="viventium-mongodb-isolated"
else
  DEFAULT_MONGO_PORT=27017
  DEFAULT_MONGO_CONTAINER="viventium-mongodb"
fi
VIVENTIUM_STATE_ROOT="${VIVENTIUM_STATE_ROOT:-$CORE_DIR/.viventium/runtime/$VIVENTIUM_RUNTIME_PROFILE}"
MONGO_CONTAINER_NAME="${VIVENTIUM_LOCAL_MONGO_CONTAINER:-$DEFAULT_MONGO_CONTAINER}"
MONGO_PORT="${VIVENTIUM_LOCAL_MONGO_PORT:-$DEFAULT_MONGO_PORT}"
MONGO_VOLUME_NAME="${VIVENTIUM_LOCAL_MONGO_VOLUME:-${MONGO_CONTAINER_NAME}-data}"
if [[ "$VIVENTIUM_RUNTIME_PROFILE" == "isolated" ]]; then
  VIVENTIUM_LOCAL_MONGO_DATA_PATH="${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-$VIVENTIUM_STATE_ROOT/mongo-data}"
fi
MONGO_IMAGE="${MONGO_IMAGE:-mongo:8.0.17}"

TMP_FILES=()
cleanup_tmp_files() {
  if [[ "${#TMP_FILES[@]}" -gt 0 ]]; then
    rm -f "${TMP_FILES[@]}" 2>/dev/null || true
  fi
}
trap cleanup_tmp_files EXIT

usage() {
  cat <<'USAGE'
viventium-db-restore-from-export.sh

Restore local DB state from a LOCAL export folder (no cloud calls).

USAGE:
  ./viventium_v0_4/viventium-db-restore-from-export.sh --export-dir <path> [options]

REQUIRED:
  --export-dir <path>     Export root containing databases/mongo/.../dump folders

OPTIONS:
  --yes                   Execute restore (default is dry-run)
  --dry-run               Force dry-run mode
  --no-drop               Restore without dropping collections first
  --out-dir <path>        Override artifacts run directory
  --with-schedules        Also replace local schedules sqlite DB
  --schedules-db <path>   Source schedules sqlite DB file
                          (optional with --with-schedules when export includes
                           databases/scheduler_mcp/sqlite_extracts)
  --local-schedules-db <path>
                          Target local schedules sqlite path
                          (default: \$VIVENTIUM_STATE_ROOT/scheduling/schedules.db)
  -h, --help              Show help

NOTES:
  - This script only uses local filesystem + local Docker.
  - No Azure or cloud endpoints are contacted.
USAGE
}

log() {
  printf '%s\n' "$*"
}

log_err() {
  printf '%s\n' "$*" >&2
}

die() {
  log_err "error: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

set_latest_run_pointer() {
  local run_dir="$1"
  local category_dir="$ARTIFACTS_ROOT/$ARTIFACT_CATEGORY"
  local pointer_path="$category_dir/LATEST_PATH"
  local resolved_run_dir="$run_dir"

  mkdir -p "$category_dir"
  if [[ -d "$run_dir" ]]; then
    resolved_run_dir="$(cd "$run_dir" && pwd -P)"
  fi
  printf '%s\n' "$resolved_run_dir" > "$pointer_path"
}

read_env_kv_if_unset() {
  local env_file="$1"
  local key="$2"
  if [[ -n "${!key:-}" ]]; then
    return 0
  fi
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    line="${line%%#*}"
    line="$(printf '%s' "$line" | xargs 2>/dev/null || printf '%s' "$line")"
    [[ -z "$line" ]] && continue

    if [[ "$line" =~ ^${key}=(.*)$ ]]; then
      local value="${BASH_REMATCH[1]}"
      value="${value#\"}"; value="${value%\"}"
      value="${value#\'}"; value="${value%\'}"
      export "$key=$value"
      return 0
    fi
  done < "$env_file"
  return 0
}

ensure_mongo_container_running() {
  local running
  running="$(docker ps -q --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null || true)"
  if [[ -n "$running" ]]; then
    return 0
  fi

  local existing
  existing="$(docker ps -aq --filter "name=^/${MONGO_CONTAINER_NAME}$" 2>/dev/null || true)"
  if [[ -n "$existing" ]]; then
    log "[restore] starting existing Mongo container: ${MONGO_CONTAINER_NAME}"
    docker start "$MONGO_CONTAINER_NAME" >/dev/null
    return 0
  fi

  log "[restore] local Mongo container not found; creating ${MONGO_CONTAINER_NAME}"
  local mongo_mount="${MONGO_VOLUME_NAME}:/data/db"
  if [[ -n "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-}" ]]; then
    mkdir -p "$VIVENTIUM_LOCAL_MONGO_DATA_PATH"
    mongo_mount="${VIVENTIUM_LOCAL_MONGO_DATA_PATH}:/data/db"
  fi
  docker run -d \
    --name "$MONGO_CONTAINER_NAME" \
    --label "viventium.stack=viventium_v0_4" \
    --label "viventium.service=mongodb" \
    -p "127.0.0.1:${MONGO_PORT}:27017" \
    -v "$mongo_mount" \
    "$MONGO_IMAGE" \
    --bind_ip_all >/dev/null
}

mongo_ping_container() {
  docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet --eval 'db.runCommand({ping:1})' >/dev/null 2>&1
}

wait_for_mongo_container() {
  local retries=30
  for _ in $(seq 1 "$retries"); do
    if mongo_ping_container; then
      return 0
    fi
    sleep 1
  done
  return 1
}

write_collection_counts() {
  local db_name="$1"
  local out_file="$2"
  {
    echo -e "collection\tcount"
    docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet --eval "
      const d=db.getSiblingDB('${db_name}');
      const names=d.getCollectionNames().sort();
      for (const n of names) print(n+'\t'+d.getCollection(n).countDocuments());
    "
  } > "$out_file"
}

normalize_local_icon_urls() {
  docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet LibreChat --eval "
    const hosts = ['https://chat.viventium.ai', 'http://chat.viventium.ai'];
    const escapeRegex = (s) => s.replace(/[.*+?^\\\${}()|[\\]\\\\]/g, '\\\\$&');
    const collections = ['conversations', 'messages'];

    for (const collName of collections) {
      const coll = db.getCollection(collName);
      let modifiedTotal = 0;
      for (const host of hosts) {
        const re = new RegExp('^' + escapeRegex(host) + '/images/');
        const result = coll.updateMany(
          { iconURL: re },
          [
            {
              \$set: {
                iconURL: {
                  \$replaceOne: {
                    input: '\$iconURL',
                    find: host,
                    replacement: '',
                  },
                },
              },
            },
          ],
        );
        modifiedTotal += result?.modifiedCount ?? 0;
      }
      print(collName + '\t' + modifiedTotal);
    }
  "
}

build_schedules_db_from_extracts() {
  local extract_dir="$1"
  local out_db="$2"

  local schema_file="$extract_dir/schema.sql"
  local tasks_csv="$extract_dir/scheduled_tasks.csv"
  local counts_file="$extract_dir/table_counts.tsv"

  [[ -f "$schema_file" ]] || die "missing scheduler schema file: $schema_file"
  [[ -f "$tasks_csv" ]] || die "missing scheduler tasks csv: $tasks_csv"

  rm -f "$out_db"

  {
    sed '1s/^scheduled_tasks|//' "$schema_file"
    echo ';'
  } | sqlite3 "$out_db"

  sqlite3 "$out_db" <<SQL
.mode csv
.import --skip 1 "$tasks_csv" scheduled_tasks
SQL

  if [[ -f "$counts_file" ]]; then
    local expected
    expected="$(awk -F'\t' '$1=="scheduled_tasks" {print $2}' "$counts_file" | head -n1 || true)"
    local actual
    actual="$(sqlite3 "$out_db" 'select count(*) from scheduled_tasks;' 2>/dev/null || true)"
    if [[ -n "$expected" && -n "$actual" && "$expected" != "$actual" ]]; then
      die "scheduler extract import count mismatch (expected=${expected}, actual=${actual})"
    fi
  fi
}

ACTION_DRY_RUN="true"
DROP_BEFORE_RESTORE="true"
EXPORT_DIR=""
OUT_DIR=""
WITH_SCHEDULES="false"
SCHEDULES_DB_SOURCE=""
DEFAULT_LOCAL_SCHEDULES_DB="$VIVENTIUM_STATE_ROOT/scheduling/schedules.db"
LOCAL_SCHEDULES_DB="${SCHEDULING_MCP_DB_PATH:-${SCHEDULING_DB_PATH:-$DEFAULT_LOCAL_SCHEDULES_DB}}"
SCHEDULER_SQLITE_EXTRACT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --export-dir)
      EXPORT_DIR="${2:-}"
      shift 2
      ;;
    --export-dir=*)
      EXPORT_DIR="${1#*=}"
      shift
      ;;
    --yes)
      ACTION_DRY_RUN="false"
      shift
      ;;
    --dry-run)
      ACTION_DRY_RUN="true"
      shift
      ;;
    --no-drop)
      DROP_BEFORE_RESTORE="false"
      shift
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --out-dir=*)
      OUT_DIR="${1#*=}"
      shift
      ;;
    --with-schedules)
      WITH_SCHEDULES="true"
      shift
      ;;
    --schedules-db)
      SCHEDULES_DB_SOURCE="${2:-}"
      shift 2
      ;;
    --schedules-db=*)
      SCHEDULES_DB_SOURCE="${1#*=}"
      shift
      ;;
    --local-schedules-db)
      LOCAL_SCHEDULES_DB="${2:-}"
      shift 2
      ;;
    --local-schedules-db=*)
      LOCAL_SCHEDULES_DB="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "$EXPORT_DIR" ]] || die "--export-dir is required"
[[ -d "$EXPORT_DIR" ]] || die "export directory not found: $EXPORT_DIR"

require_cmd docker
require_cmd sqlite3

LIBRE_DUMP_DIR="$EXPORT_DIR/databases/mongo/librechat/dump/LibreChat"
RAG_DUMP_DIR="$EXPORT_DIR/databases/mongo/rag/dump/rag-db"

[[ -d "$LIBRE_DUMP_DIR" ]] || die "missing LibreChat dump directory: $LIBRE_DUMP_DIR"
[[ -d "$RAG_DUMP_DIR" ]] || die "missing rag-db dump directory: $RAG_DUMP_DIR"

if [[ "$WITH_SCHEDULES" == "true" ]]; then
  if [[ -n "$SCHEDULES_DB_SOURCE" ]]; then
    [[ -f "$SCHEDULES_DB_SOURCE" ]] || die "schedules db not found: $SCHEDULES_DB_SOURCE"
  else
    SCHEDULER_SQLITE_EXTRACT_DIR="$EXPORT_DIR/databases/scheduler_mcp/sqlite_extracts"
    if [[ ! -d "$SCHEDULER_SQLITE_EXTRACT_DIR" ]]; then
      die "--with-schedules requires --schedules-db <path> or export scheduler extracts at $SCHEDULER_SQLITE_EXTRACT_DIR"
    fi
    [[ -f "$SCHEDULER_SQLITE_EXTRACT_DIR/schema.sql" ]] || die "missing scheduler extract schema: $SCHEDULER_SQLITE_EXTRACT_DIR/schema.sql"
    [[ -f "$SCHEDULER_SQLITE_EXTRACT_DIR/scheduled_tasks.csv" ]] || die "missing scheduler extract csv: $SCHEDULER_SQLITE_EXTRACT_DIR/scheduled_tasks.csv"
  fi
fi

if [[ -z "$OUT_DIR" ]]; then
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  OUT_DIR="$ARTIFACTS_ROOT/$ARTIFACT_CATEGORY/runs/$ts"
fi

log "[restore] export_dir=$EXPORT_DIR"
log "[restore] out_dir=$OUT_DIR"
log "[restore] dry_run=$ACTION_DRY_RUN drop=$DROP_BEFORE_RESTORE"
log "[restore] mongo_container=$MONGO_CONTAINER_NAME"
if [[ "$WITH_SCHEDULES" == "true" ]]; then
  if [[ -n "$SCHEDULES_DB_SOURCE" ]]; then
    log "[restore] schedules_source=$SCHEDULES_DB_SOURCE"
  else
    log "[restore] schedules_source=export sqlite_extracts ($SCHEDULER_SQLITE_EXTRACT_DIR)"
  fi
  log "[restore] schedules_target=$LOCAL_SCHEDULES_DB"
fi

if [[ "$ACTION_DRY_RUN" == "true" ]]; then
  log "[dry-run] would backup local Mongo (LibreChat + rag-db)"
  log "[dry-run] would restore LibreChat from: $LIBRE_DUMP_DIR"
  log "[dry-run] would restore rag-db from: $RAG_DUMP_DIR"
  if [[ "$WITH_SCHEDULES" == "true" ]]; then
    if [[ -n "$SCHEDULES_DB_SOURCE" ]]; then
      log "[dry-run] would copy schedules DB: $SCHEDULES_DB_SOURCE -> $LOCAL_SCHEDULES_DB"
    else
      log "[dry-run] would build schedules DB from: $SCHEDULER_SQLITE_EXTRACT_DIR"
      log "[dry-run] would copy generated schedules DB -> $LOCAL_SCHEDULES_DB"
    fi
  fi
  exit 0
fi

mkdir -p "$OUT_DIR"
printf '%s\n' "$EXPORT_DIR" > "$OUT_DIR/export_dir.txt"

if [[ -f "$EXPORT_DIR/databases/mongo/librechat/collection_counts.tsv" ]]; then
  cp "$EXPORT_DIR/databases/mongo/librechat/collection_counts.tsv" "$OUT_DIR/source_librechat_counts.tsv"
fi
if [[ -f "$EXPORT_DIR/databases/mongo/rag/collection_counts.tsv" ]]; then
  cp "$EXPORT_DIR/databases/mongo/rag/collection_counts.tsv" "$OUT_DIR/source_rag_counts.tsv"
fi

ensure_mongo_container_running
wait_for_mongo_container || die "Mongo container did not become ready: $MONGO_CONTAINER_NAME"

write_collection_counts "LibreChat" "$OUT_DIR/local_before_librechat_counts.tsv"
write_collection_counts "rag-db" "$OUT_DIR/local_before_rag_counts.tsv"

TMP_BACKUP="/tmp/viv_local_backup_$(date -u +%Y%m%dT%H%M%SZ)"
TMP_SOURCE="/tmp/viv_source_dump_$(date -u +%Y%m%dT%H%M%SZ)"

docker exec "$MONGO_CONTAINER_NAME" sh -lc "rm -rf '$TMP_BACKUP' '$TMP_SOURCE' && mkdir -p '$TMP_BACKUP' '$TMP_SOURCE'"
docker exec "$MONGO_CONTAINER_NAME" mongodump --db LibreChat --out "$TMP_BACKUP"
docker exec "$MONGO_CONTAINER_NAME" mongodump --db rag-db --out "$TMP_BACKUP"
mkdir -p "$OUT_DIR/local_before_dump"
docker cp "$MONGO_CONTAINER_NAME:$TMP_BACKUP/." "$OUT_DIR/local_before_dump/"

docker cp "$LIBRE_DUMP_DIR" "$MONGO_CONTAINER_NAME:$TMP_SOURCE/LibreChat"
docker cp "$RAG_DUMP_DIR" "$MONGO_CONTAINER_NAME:$TMP_SOURCE/rag-db"

RESTORE_ARGS=(--drop)
if [[ "$DROP_BEFORE_RESTORE" != "true" ]]; then
  RESTORE_ARGS=()
fi

docker exec "$MONGO_CONTAINER_NAME" mongorestore "${RESTORE_ARGS[@]}" --db LibreChat "$TMP_SOURCE/LibreChat"
docker exec "$MONGO_CONTAINER_NAME" mongorestore "${RESTORE_ARGS[@]}" --db rag-db "$TMP_SOURCE/rag-db"

{
  echo -e "collection\tmodified_count"
  normalize_local_icon_urls
} > "$OUT_DIR/local_iconurl_normalization.tsv"

write_collection_counts "LibreChat" "$OUT_DIR/local_after_librechat_counts.tsv"
write_collection_counts "rag-db" "$OUT_DIR/local_after_rag_counts.tsv"

if [[ "$WITH_SCHEDULES" == "true" ]]; then
  effective_schedules_source="$SCHEDULES_DB_SOURCE"
  if [[ -z "$effective_schedules_source" ]]; then
    generated_schedules_db="/tmp/viv_scheduler_export_$(date -u +%Y%m%dT%H%M%SZ).db"
    TMP_FILES+=("$generated_schedules_db")
    build_schedules_db_from_extracts "$SCHEDULER_SQLITE_EXTRACT_DIR" "$generated_schedules_db"
    effective_schedules_source="$generated_schedules_db"
    cp "$generated_schedules_db" "$OUT_DIR/source_schedules_from_extracts.db"
  fi

  mkdir -p "$(dirname "$LOCAL_SCHEDULES_DB")"
  if [[ -f "$LOCAL_SCHEDULES_DB" ]]; then
    cp "$LOCAL_SCHEDULES_DB" "$OUT_DIR/local_before_schedules.db"
  fi
  cp "$effective_schedules_source" "$LOCAL_SCHEDULES_DB"
  sqlite3 "$LOCAL_SCHEDULES_DB" 'select count(*) from scheduled_tasks;' > "$OUT_DIR/local_after_schedules_count.txt" 2>/dev/null || true
fi

docker exec "$MONGO_CONTAINER_NAME" sh -lc "rm -rf '$TMP_BACKUP' '$TMP_SOURCE'"

set_latest_run_pointer "$OUT_DIR"
log "[restore] latest pointer: $ARTIFACTS_ROOT/$ARTIFACT_CATEGORY/LATEST_PATH"
log "[restore] done"
log "[restore] run dir: $OUT_DIR"
