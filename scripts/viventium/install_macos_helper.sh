#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/viventium/common.sh"
ensure_brew_paths_on_path

MODE="install"
LAUNCH_AFTER_INSTALL=1
APP_SUPPORT_DIR="${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}"
HELPER_PACKAGE_DIR="${VIVENTIUM_HELPER_PACKAGE_DIR:-$REPO_ROOT/apps/macos/ViventiumHelper}"
HELPER_BUILD_DIR="${VIVENTIUM_HELPER_BUILD_DIR:-$HELPER_PACKAGE_DIR/.build/release}"
HELPER_EXECUTABLE_NAME="ViventiumHelper"
BUILT_EXECUTABLE="${VIVENTIUM_HELPER_BUILT_EXECUTABLE:-$HELPER_BUILD_DIR/$HELPER_EXECUTABLE_NAME}"
HELPER_PREBUILT_DIR="${VIVENTIUM_HELPER_PREBUILT_DIR:-$HELPER_PACKAGE_DIR/prebuilt}"
HELPER_PREBUILT_EXECUTABLE="${VIVENTIUM_HELPER_PREBUILT_EXECUTABLE:-$HELPER_PREBUILT_DIR/${HELPER_EXECUTABLE_NAME}-universal}"
HELPER_PREBUILT_SOURCE_HASH_FILE="${VIVENTIUM_HELPER_PREBUILT_SOURCE_HASH_FILE:-$HELPER_PREBUILT_DIR/source.sha256}"
HELPER_APP_DIR="${VIVENTIUM_HELPER_APP_DIR:-$HOME/Applications}"
HELPER_APP_BUNDLE="${VIVENTIUM_HELPER_APP_BUNDLE:-$HELPER_APP_DIR/Viventium.app}"
LEGACY_HELPER_APP_BUNDLE="${VIVENTIUM_HELPER_LEGACY_APP_BUNDLE:-$HELPER_APP_DIR/Viventium Helper.app}"
HELPER_ICON_RESOURCE="${VIVENTIUM_HELPER_ICON_RESOURCE:-$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/Resources/Viventium.icns}"
LAUNCH_AGENT_DIR="${VIVENTIUM_HELPER_LAUNCH_AGENT_DIR:-$HOME/Library/LaunchAgents}"
LAUNCH_AGENT_PLIST="${VIVENTIUM_HELPER_LAUNCH_AGENT_PLIST:-$LAUNCH_AGENT_DIR/ai.viventium.helper.plist}"
HELPER_CONFIG_FILE="${VIVENTIUM_HELPER_CONFIG_FILE:-$APP_SUPPORT_DIR/helper-config.json}"
HELPER_LOG_FILE="${VIVENTIUM_HELPER_LOG_FILE:-$APP_SUPPORT_DIR/logs/viventium-helper.log}"
HELPER_SCRIPT_DIR="${VIVENTIUM_HELPER_SCRIPT_DIR:-$APP_SUPPORT_DIR/helper-scripts}"
HELPER_STACK_SCRIPT_COPY="${VIVENTIUM_HELPER_STACK_SCRIPT_COPY:-$HELPER_SCRIPT_DIR/viventium-librechat-start.sh}"
HELPER_STACK_WRAPPER="${VIVENTIUM_HELPER_STACK_WRAPPER:-$HELPER_SCRIPT_DIR/viventium-stack.sh}"
SKIP_BUILD="${VIVENTIUM_HELPER_SKIP_BUILD:-0}"
SKIP_LAUNCHCTL="${VIVENTIUM_HELPER_SKIP_LAUNCHCTL:-0}"
SKIP_LOGIN_ITEM="${VIVENTIUM_HELPER_SKIP_LOGIN_ITEM:-0}"
OSASCRIPT_TIMEOUT_SECONDS="${VIVENTIUM_HELPER_OSASCRIPT_TIMEOUT_SECONDS:-15}"

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    install|uninstall)
      MODE="$1"
      shift
      ;;
    --repo-root)
      REPO_ROOT="$2"
      HELPER_PACKAGE_DIR="${VIVENTIUM_HELPER_PACKAGE_DIR:-$REPO_ROOT/apps/macos/ViventiumHelper}"
      HELPER_BUILD_DIR="${VIVENTIUM_HELPER_BUILD_DIR:-$HELPER_PACKAGE_DIR/.build/release}"
      BUILT_EXECUTABLE="${VIVENTIUM_HELPER_BUILT_EXECUTABLE:-$HELPER_BUILD_DIR/$HELPER_EXECUTABLE_NAME}"
      shift 2
      ;;
    --app-support-dir)
      APP_SUPPORT_DIR="$2"
      HELPER_CONFIG_FILE="${VIVENTIUM_HELPER_CONFIG_FILE:-$APP_SUPPORT_DIR/helper-config.json}"
      HELPER_LOG_FILE="${VIVENTIUM_HELPER_LOG_FILE:-$APP_SUPPORT_DIR/logs/viventium-helper.log}"
      shift 2
      ;;
    --no-launch)
      LAUNCH_AFTER_INSTALL=0
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  exit 0
fi

mkdir -p "$APP_SUPPORT_DIR" "$APP_SUPPORT_DIR/logs" "$HELPER_APP_DIR" "$LAUNCH_AGENT_DIR"

write_helper_config() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - <<PY
import json
from pathlib import Path

path = Path(r"""$HELPER_CONFIG_FILE""")
path.parent.mkdir(parents=True, exist_ok=True)
existing = {}
if path.exists():
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        existing = {}

config = dict(existing)
config.update(
    {
        "repoRoot": r"""$REPO_ROOT""",
        "appSupportDir": r"""$APP_SUPPORT_DIR""",
        "showInStatusBar": bool(existing.get("showInStatusBar", True)),
    }
)
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
}

write_helper_launcher_scripts() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - <<PY
from pathlib import Path
import shlex

repo_root = Path(r"""$REPO_ROOT""").resolve()
app_support_dir = Path(r"""$APP_SUPPORT_DIR""").resolve()
helper_script_dir = Path(r"""$HELPER_SCRIPT_DIR""").resolve()
stack_script_copy = Path(r"""$HELPER_STACK_SCRIPT_COPY""").resolve()
stack_wrapper = Path(r"""$HELPER_STACK_WRAPPER""").resolve()
source_script = repo_root / "viventium_v0_4" / "viventium-librechat-start.sh"
bin_viventium = repo_root / "bin" / "viventium"

helper_script_dir.mkdir(parents=True, exist_ok=True)
for stale_script in helper_script_dir.glob("*.command"):
    try:
        stale_script.unlink()
    except FileNotFoundError:
        pass
for stale_script in helper_script_dir.glob("helper-detached-*.sh"):
    try:
        stale_script.unlink()
    except FileNotFoundError:
        pass

stack_script_copy.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
stack_script_copy.chmod(0o755)

runtime_env = app_support_dir / "runtime" / "runtime.env"
runtime_local_env = app_support_dir / "runtime" / "runtime.local.env"

def q(value: Path | str) -> str:
    return shlex.quote(str(value))

dollar = chr(36)

wrapper = f"""#!/usr/bin/env bash
set -euo pipefail
export VIVENTIUM_HELPER_V0_ROOT={q(repo_root / "viventium_v0_4")}
export VIVENTIUM_HELPER_CORE_ROOT={q(repo_root)}
export VIVENTIUM_HELPER_WORKSPACE_ROOT={q(repo_root.parent)}
export VIVENTIUM_APP_SUPPORT_DIR={q(app_support_dir)}
export VIVENTIUM_ENV_FILE={q(runtime_env)}
export VIVENTIUM_ENV_LOCAL_FILE={q(runtime_local_env)}
if [[ "{dollar}{{1:-}}" == "--stop" ]]; then
  shift
  exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} stop "{dollar}@"
fi
export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1
export VIVENTIUM_DETACHED_START=true
exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} launch "{dollar}@"
"""

stack_wrapper.write_text(wrapper, encoding="utf-8")
stack_wrapper.chmod(0o755)
PY
}

write_launch_agent_plist() {
  cat >"$LAUNCH_AGENT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.viventium.helper</string>
  <key>ProgramArguments</key>
  <array>
    <string>$HELPER_APP_BUNDLE/Contents/MacOS/$HELPER_EXECUTABLE_NAME</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$HOME</string>
  <key>RunAtLoad</key>
  <true/>
  <key>LimitLoadToSessionType</key>
  <array>
    <string>Aqua</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$PATH</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$HELPER_LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$HELPER_LOG_FILE</string>
</dict>
</plist>
PLIST
}

register_login_item() {
  [[ "$SKIP_LOGIN_ITEM" == "1" ]] && return 1
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$OSASCRIPT_TIMEOUT_SECONDS" "$HELPER_APP_BUNDLE" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
bundle_path = sys.argv[2].replace("\\", "\\\\").replace('"', '\\"')
script = f"""tell application "System Events"
  if exists login item "Viventium" then
    delete login item "Viventium"
  end if
  make login item at end with properties {{name:"Viventium", path:"{bundle_path}", hidden:true}}
end tell
"""

try:
    completed = subprocess.run(
        ["/usr/bin/osascript"],
        input=script,
        text=True,
        timeout=timeout,
    )
except subprocess.TimeoutExpired:
    sys.stderr.write(f"[viventium] Login-item registration timed out after {timeout:.0f}s; falling back to LaunchAgent\n")
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
}

unregister_login_item() {
  [[ "$SKIP_LOGIN_ITEM" == "1" ]] && return 0
  /usr/bin/osascript <<APPLESCRIPT
tell application "System Events"
  if exists login item "Viventium" then
    delete login item "Viventium"
  end if
end tell
APPLESCRIPT
}

cleanup_legacy_terminal_helper_launchers() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$APP_SUPPORT_DIR" "$HELPER_SCRIPT_DIR" "$LAUNCH_AGENT_DIR" "$OSASCRIPT_TIMEOUT_SECONDS" <<'PY'
import os
import shutil
import subprocess
import sys
from pathlib import Path

app_support_dir = Path(sys.argv[1]).resolve()
helper_script_dir = Path(sys.argv[2]).resolve()
launch_agent_dir = Path(sys.argv[3]).resolve()
timeout = float(sys.argv[4])

legacy_command_markers = (
    "helper-terminal-run.command",
    "helper-detached-start.pid.command",
    "helper-detached-stop.pid.command",
)
legacy_history_markers = tuple(
    str(helper_script_dir / marker)
    for marker in legacy_command_markers
)
legacy_history_markers += tuple(
    marker.replace(" ", "\\ ")
    for marker in legacy_history_markers
)

for stale_script in helper_script_dir.glob("*.command"):
    try:
        stale_script.unlink()
    except FileNotFoundError:
        pass


def scrub_legacy_helper_history(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    lines = text.splitlines(keepends=True)
    filtered = [line for line in lines if not any(marker in line for marker in legacy_history_markers)]
    if filtered == lines:
        return
    try:
        path.write_text("".join(filtered), encoding="utf-8")
    except OSError:
        return


for history_path in (Path.home() / ".zsh_history",):
    scrub_legacy_helper_history(history_path)

zsh_sessions_dir = Path.home() / ".zsh_sessions"
if zsh_sessions_dir.exists():
    for history_path in zsh_sessions_dir.glob("*"):
        if history_path.suffix not in {".history", ".historynew", ".session"}:
            continue
        scrub_legacy_helper_history(history_path)


def terminal_saved_state_contains_legacy_marker(saved_state_dir: Path) -> bool:
    if not saved_state_dir.exists():
        return False
    marker_bytes = [
        marker.encode("utf-8")
        for marker in (*legacy_command_markers, *legacy_history_markers)
    ]
    for candidate in saved_state_dir.rglob("*"):
        if not candidate.is_file():
            continue
        try:
            payload = candidate.read_bytes()
        except OSError:
            continue
        if any(marker in payload for marker in marker_bytes):
            return True
    return False


terminal_saved_state_dir = (
    Path.home() / "Library" / "Saved Application State" / "com.apple.Terminal.savedState"
)
if terminal_saved_state_contains_legacy_marker(terminal_saved_state_dir):
    shutil.rmtree(terminal_saved_state_dir, ignore_errors=True)

for plist_path in launch_agent_dir.glob("*.plist"):
    try:
        text = plist_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    if str(helper_script_dir) not in text and not any(marker in text for marker in legacy_command_markers):
        continue
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    try:
        plist_path.unlink()
    except FileNotFoundError:
        pass

escaped_helper_dir = (
    str(helper_script_dir)
    .replace("\\", "\\\\")
    .replace('"', '\\"')
)
script = f'''tell application "System Events"
  repeat with li in every login item
    set shouldDelete to false
    try
      set liPath to POSIX path of (path of li as alias)
      if liPath contains "{escaped_helper_dir}" then
        set shouldDelete to true
      end if
    end try
    if shouldDelete then
      delete li
    end if
  end repeat
end tell
'''
try:
    subprocess.run(
        ["/usr/bin/osascript"],
        input=script,
        text=True,
        timeout=timeout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
except subprocess.TimeoutExpired:
    pass
PY
  pkill -f "$APP_SUPPORT_DIR/helper-scripts/.*\\.command" >/dev/null 2>&1 || true
}

helper_source_hash() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_PACKAGE_DIR" <<'PY'
import hashlib
import sys
from pathlib import Path

helper_dir = Path(sys.argv[1])
paths = [
    helper_dir / "Package.swift",
    helper_dir / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift",
    helper_dir / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist",
]

digest = hashlib.sha256()
for path in paths:
    digest.update(path.relative_to(helper_dir).as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")

print(digest.hexdigest())
PY
}

prebuilt_helper_matches_sources() {
  [[ -x "$HELPER_PREBUILT_EXECUTABLE" ]] || return 1
  [[ -f "$HELPER_PREBUILT_SOURCE_HASH_FILE" ]] || return 1

  local expected_hash
  local actual_hash
  expected_hash="$(tr -d '[:space:]' < "$HELPER_PREBUILT_SOURCE_HASH_FILE")"
  actual_hash="$(helper_source_hash)"
  [[ -n "$expected_hash" && "$expected_hash" == "$actual_hash" ]]
}

use_prebuilt_helper() {
  mkdir -p "$HELPER_BUILD_DIR"
  cp "$HELPER_PREBUILT_EXECUTABLE" "$BUILT_EXECUTABLE"
  chmod +x "$BUILT_EXECUTABLE"
  echo "[viventium] Using prebuilt helper fallback from $HELPER_PREBUILT_EXECUTABLE" >&2
}

build_helper() {
  if [[ "$SKIP_BUILD" == "1" ]]; then
    [[ -x "$BUILT_EXECUTABLE" ]] || {
      echo "Missing built helper executable: $BUILT_EXECUTABLE" >&2
      exit 1
    }
    return 0
  fi
  local python_bin
  local swiftpm_timeout_seconds
  python_bin="$(resolve_repo_python)"
  swiftpm_timeout_seconds="${VIVENTIUM_HELPER_SWIFTPM_TIMEOUT_SECONDS:-60}"
  rm -f "$HELPER_PACKAGE_DIR/.build/workspace-state.json"
  if "$python_bin" - "$swiftpm_timeout_seconds" "$HELPER_PACKAGE_DIR" "$HELPER_EXECUTABLE_NAME" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
helper_package_dir = sys.argv[2]
helper_name = sys.argv[3]

try:
    completed = subprocess.run(
        ["swift", "build", "-c", "release", "--product", helper_name],
        cwd=helper_package_dir,
        timeout=timeout,
    )
except subprocess.TimeoutExpired:
    sys.stderr.write(f"[viventium] SwiftPM helper build timed out after {timeout:.0f}s\n")
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
  then
    return 0
  fi

  local sdk_path
  local swiftc_bin
  local target_triple
  local compile_timeout_seconds
  sdk_path="$(xcrun --show-sdk-path)"
  swiftc_bin="$(xcrun --find swiftc)"
  target_triple="$(uname -m)-apple-macosx13.0"
  compile_timeout_seconds="${VIVENTIUM_HELPER_DIRECT_COMPILE_TIMEOUT_SECONDS:-600}"
  mkdir -p "$HELPER_BUILD_DIR"
  if prebuilt_helper_matches_sources; then
    use_prebuilt_helper
    return 0
  fi

  echo "[viventium] SwiftPM helper build failed; retrying with direct swiftc compile" >&2
  if "$python_bin" - "$compile_timeout_seconds" "$swiftc_bin" "$sdk_path" "$target_triple" \
    "$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/ViventiumHelperApp.swift" "$BUILT_EXECUTABLE" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
swiftc_bin, sdk_path, target_triple, source_path, output_path = sys.argv[2:]
command = [
    swiftc_bin,
    "-parse-as-library",
    "-sdk",
    sdk_path,
    "-target",
    target_triple,
    source_path,
    "-o",
    output_path,
]

try:
    completed = subprocess.run(command, timeout=timeout)
except subprocess.TimeoutExpired:
    sys.stderr.write(f"[viventium] Direct helper compile timed out after {timeout:.0f}s\n")
    raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
  then
    return 0
  fi

  if [[ -f "$HELPER_PREBUILT_SOURCE_HASH_FILE" ]]; then
    echo "[viventium] Prebuilt helper fallback exists but does not match current helper sources" >&2
  else
    echo "[viventium] No matching prebuilt helper fallback found" >&2
  fi

  return 1
}

install_bundle() {
  local contents_dir="$HELPER_APP_BUNDLE/Contents"
  local macos_dir="$contents_dir/MacOS"
  local resources_dir="$contents_dir/Resources"
  rm -rf "$LEGACY_HELPER_APP_BUNDLE"
  rm -rf "$HELPER_APP_BUNDLE"
  mkdir -p "$macos_dir"
  mkdir -p "$resources_dir"
  cp "$BUILT_EXECUTABLE" "$macos_dir/$HELPER_EXECUTABLE_NAME"
  chmod +x "$macos_dir/$HELPER_EXECUTABLE_NAME"
  cp "$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/Resources/Info.plist" "$contents_dir/Info.plist"
  if [[ -f "$HELPER_ICON_RESOURCE" ]]; then
    cp "$HELPER_ICON_RESOURCE" "$resources_dir/Viventium.icns"
  fi
}

stop_existing_helper() {
  pkill -f "$LEGACY_HELPER_APP_BUNDLE/Contents/MacOS/$HELPER_EXECUTABLE_NAME" >/dev/null 2>&1 || true
  pkill -f "$HELPER_APP_BUNDLE/Contents/MacOS/$HELPER_EXECUTABLE_NAME" >/dev/null 2>&1 || true
}

bootstrap_launch_agent() {
  [[ "$SKIP_LAUNCHCTL" == "1" ]] && return 0
  [[ "$LAUNCH_AFTER_INSTALL" == "1" ]] || return 0
  launchctl bootout "gui/$UID" "$LAUNCH_AGENT_PLIST" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID" "$LAUNCH_AGENT_PLIST"
  if [[ "$LAUNCH_AFTER_INSTALL" == "1" ]]; then
    launchctl kickstart -k "gui/$UID/ai.viventium.helper" >/dev/null 2>&1 || true
  fi
}

remove_launch_agent() {
  [[ "$SKIP_LAUNCHCTL" == "1" ]] || launchctl bootout "gui/$UID" "$LAUNCH_AGENT_PLIST" >/dev/null 2>&1 || true
  rm -f "$LAUNCH_AGENT_PLIST"
}

launch_helper_app() {
  if [[ "$LAUNCH_AFTER_INSTALL" == "1" ]]; then
    /usr/bin/open -g "$HELPER_APP_BUNDLE"
  fi
}

case "$MODE" in
install)
    cleanup_legacy_terminal_helper_launchers
    build_helper
    install_bundle
    write_helper_config
    write_helper_launcher_scripts
    stop_existing_helper
    unregister_login_item || true
    remove_launch_agent
    register_login_item || {
      write_launch_agent_plist
      bootstrap_launch_agent
    }
    launch_helper_app
    ;;
  uninstall)
    cleanup_legacy_terminal_helper_launchers
    unregister_login_item || true
    remove_launch_agent
    stop_existing_helper
    rm -rf "$LEGACY_HELPER_APP_BUNDLE"
    rm -rf "$HELPER_APP_BUNDLE"
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 1
    ;;
esac
