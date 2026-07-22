#!/bin/sh
set -eu
entrypoint_name="${0##*/}"
command_name="${entrypoint_name#viventium-native-}"
release_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
unset PYTHONHOME PYTHONPATH PYTHONSTARTUP PYTHONUSERBASE
export PYTHONNOUSERSITE=1
exec "$release_root/runtime/python/bin/python3" -E -s -B \
  "$release_root/runtime/scripts/native_runtime.py" "$command_name" "$@"
