#!/usr/bin/env bash
# === VIVENTIUM START ===
# Legacy voice-stack compatibility entrypoint.
#
# The reviewed runtime, immutable LiveKit server selection, and modern
# Viventium playground policy are owned by viventium-librechat-start.sh.
# This wrapper must not duplicate installation or startup behavior.
#
# Usage: ./viventium-start-all.sh [--no-playground] [--help]
# === VIVENTIUM END ===

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANONICAL_LAUNCHER="${SCRIPT_DIR}/viventium-librechat-start.sh"

usage() {
  cat <<'EOF'
Usage: ./viventium-start-all.sh [options]

Legacy compatibility options:
  --no-playground  Start without the browser voice playground
  --help           Show this help

This wrapper delegates to viventium-librechat-start.sh and explicitly selects
the modern Viventium playground. Use the canonical launcher directly for all
other supported settings.
EOF
}

forwarded_args=(--modern-playground)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-playground)
      forwarded_args+=(--skip-playground)
      shift
      ;;
    --build|--clean|--install-deps)
      printf 'Error: %s is no longer supported by the legacy launcher.\n' "$1" >&2
      printf 'Use %s and its reviewed options instead.\n' "$CANONICAL_LAUNCHER" >&2
      exit 64
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      printf 'Error: unknown legacy launcher option: %s\n' "$1" >&2
      printf 'Use %s --help for the supported runtime options.\n' "$CANONICAL_LAUNCHER" >&2
      exit 64
      ;;
  esac
done

if [[ ! -x "$CANONICAL_LAUNCHER" ]]; then
  printf 'Error: canonical Viventium launcher is missing or not executable: %s\n' \
    "$CANONICAL_LAUNCHER" >&2
  exit 1
fi

printf 'Legacy launcher: delegating to the reviewed modern Viventium runtime.\n' >&2
exec "$CANONICAL_LAUNCHER" "${forwarded_args[@]}"
