#!/usr/bin/env bash
set -euo pipefail

MODEL_REPO="${MLX_MODEL_REPO:-mlx-community/gemma-4-26b-a4b-it-4bit}"
HOST="${MLX_HOST:-0.0.0.0}"
PORT="${MLX_PORT:-8484}"

pick_python() {
  local candidate=""
  for candidate in python3.14 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("mlx_lm") else 1)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Unable to find a Python runtime with mlx_lm installed." >&2
  echo "Expected one of: python3.14, python3, python." >&2
  exit 1
fi

MODEL_PATH="$("$PYTHON_BIN" - "$MODEL_REPO" <<'PY'
from huggingface_hub import scan_cache_dir
from pathlib import Path
import sys

repo_id = sys.argv[1]
cache = scan_cache_dir()

for repo in cache.repos:
    if repo.repo_id != repo_id:
        continue
    refs_dir = Path(repo.repo_path) / "refs"
    if refs_dir.exists():
        main_ref = refs_dir / "main"
        if main_ref.exists():
            revision = main_ref.read_text(encoding="utf-8").strip()
            snapshot = Path(repo.repo_path) / "snapshots" / revision
            if snapshot.exists():
                print(snapshot)
                raise SystemExit(0)
    revisions = list(repo.revisions)
    if revisions:
        print(revisions[0].snapshot_path)
        raise SystemExit(0)

raise SystemExit(1)
PY
)" || {
  echo "Cached MLX model not found for ${MODEL_REPO}." >&2
  echo "Download it first, then rerun this script." >&2
  exit 1
}

export HF_HUB_OFFLINE=1

echo "Starting MLX server"
echo "  python: ${PYTHON_BIN}"
echo "  model:  ${MODEL_REPO}"
echo "  path:   ${MODEL_PATH}"
echo "  url:    http://localhost:${PORT}/v1"

exec "$PYTHON_BIN" -m mlx_lm server \
  --model "$MODEL_PATH" \
  --port "$PORT" \
  --host "$HOST"
