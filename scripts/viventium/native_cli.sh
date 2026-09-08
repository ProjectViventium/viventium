#!/bin/sh
set -eu

release_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
support_dir="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"

run_native() {
  command_name="$1"
  shift
  exec "$release_root/bin/viventium-native-$command_name" \
    --app-support-dir "$support_dir" "$@"
}

case "${1:-}" in
  life)
    shift
    exec "$release_root/runtime/python/bin/python3" -E -s -B \
      "$release_root/runtime/scripts/life_setup.py" \
      --config-file "$support_dir/config.yaml" --state-dir "$support_dir/state" "$@"
    ;;
  launch)
    shift
    "$release_root/bin/viventium-native-start" --app-support-dir "$support_dir" "$@"
    /usr/bin/open "http://127.0.0.1:3190" >/dev/null 2>&1 || true
    ;;
  start|stop|status|doctor|password-reset-link|provider-auth|snapshot|restore|uninstall)
    command_name="$1"
    shift
    run_native "$command_name" "$@"
    ;;
  *)
    echo "Usage: viventium {life|launch|start|stop|status|doctor|password-reset-link|provider-auth|snapshot|restore|uninstall}" >&2
    echo "Native updates require a newly verified signed Bootstrap; Custom Settings Install remains a source-installer choice." >&2
    exit 2
    ;;
esac
