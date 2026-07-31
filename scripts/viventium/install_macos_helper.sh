#!/usr/bin/env bash
set -Eeuo pipefail

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
HELPER_BUNDLE_IDENTIFIER="${VIVENTIUM_HELPER_BUNDLE_IDENTIFIER:-ai.viventium.helper}"
BUILT_EXECUTABLE="${VIVENTIUM_HELPER_BUILT_EXECUTABLE:-$HELPER_BUILD_DIR/$HELPER_EXECUTABLE_NAME}"
HELPER_PREBUILT_DIR="${VIVENTIUM_HELPER_PREBUILT_DIR:-$HELPER_PACKAGE_DIR/prebuilt}"
HELPER_PREBUILT_EXECUTABLE="${VIVENTIUM_HELPER_PREBUILT_EXECUTABLE:-$HELPER_PREBUILT_DIR/${HELPER_EXECUTABLE_NAME}-universal}"
HELPER_PREBUILT_SOURCE_HASH_FILE="${VIVENTIUM_HELPER_PREBUILT_SOURCE_HASH_FILE:-$HELPER_PREBUILT_DIR/source.sha256}"
HELPER_PREBUILT_BINARY_HASH_FILE="${VIVENTIUM_HELPER_PREBUILT_BINARY_HASH_FILE:-$HELPER_PREBUILT_DIR/binary.sha256}"
HELPER_APP_DIR="${VIVENTIUM_HELPER_APP_DIR:-$HOME/Applications}"
HELPER_APP_BUNDLE="${VIVENTIUM_HELPER_APP_BUNDLE:-$HELPER_APP_DIR/Viventium.app}"
LEGACY_HELPER_APP_BUNDLE="${VIVENTIUM_HELPER_LEGACY_APP_BUNDLE:-$HELPER_APP_DIR/Viventium Helper.app}"
HELPER_ICON_RESOURCE="${VIVENTIUM_HELPER_ICON_RESOURCE:-$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/Resources/Viventium.icns}"
LAUNCH_AGENT_DIR="${VIVENTIUM_HELPER_LAUNCH_AGENT_DIR:-$HOME/Library/LaunchAgents}"
LAUNCH_AGENT_PLIST="${VIVENTIUM_HELPER_LAUNCH_AGENT_PLIST:-$LAUNCH_AGENT_DIR/ai.viventium.helper.plist}"
HELPER_CONFIG_FILE="${VIVENTIUM_HELPER_CONFIG_FILE:-$APP_SUPPORT_DIR/helper-config.json}"
HELPER_LOG_FILE="${VIVENTIUM_HELPER_LOG_FILE:-$APP_SUPPORT_DIR/logs/viventium-helper.log}"
HELPER_SCRIPT_DIR="${VIVENTIUM_HELPER_SCRIPT_DIR:-$APP_SUPPORT_DIR/helper-scripts}"
HELPER_INSTALL_RECEIPT="$APP_SUPPORT_DIR/state/helper-install-in-progress.json"
HELPER_STACK_SCRIPT_COPY="${VIVENTIUM_HELPER_STACK_SCRIPT_COPY:-$HELPER_SCRIPT_DIR/viventium-librechat-start.sh}"
HELPER_STACK_WRAPPER="${VIVENTIUM_HELPER_STACK_WRAPPER:-$HELPER_SCRIPT_DIR/viventium-stack.sh}"
HELPER_TRANSACTION_TOOL="$REPO_ROOT/scripts/viventium/helper_bundle_transaction.py"
HELPER_RUNTIME_REPO_ROOT="${VIVENTIUM_HELPER_RUNTIME_REPO_ROOT:-$REPO_ROOT}"
SKIP_BUILD="${VIVENTIUM_HELPER_SKIP_BUILD:-0}"
FORCE_LOCAL_BUILD="${VIVENTIUM_HELPER_FORCE_LOCAL_BUILD:-0}"
SKIP_CODESIGN="${VIVENTIUM_HELPER_SKIP_CODESIGN:-0}"
SKIP_LAUNCHCTL="${VIVENTIUM_HELPER_SKIP_LAUNCHCTL:-0}"
SKIP_LOGIN_ITEM="${VIVENTIUM_HELPER_SKIP_LOGIN_ITEM:-0}"
OSASCRIPT_TIMEOUT_SECONDS="${VIVENTIUM_HELPER_OSASCRIPT_TIMEOUT_SECONDS:-15}"
HELPER_OWNER_MARKER_RELATIVE="Contents/Resources/viventium-owner.json"
HELPER_TRANSACTION_PYTHON=""
HELPER_DESTINATION_STATE=""
HELPER_STAGE_STATE=""
STAGED_APP_BUNDLE=""
PRESERVE_HELPER_CONFIG=0
RECOVERY_BUNDLE_ONLY=0

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
      HELPER_INSTALL_RECEIPT="$APP_SUPPORT_DIR/state/helper-install-in-progress.json"
      shift 2
      ;;
    --no-launch)
      LAUNCH_AFTER_INSTALL=0
      shift
      ;;
    --preserve-helper-config)
      PRESERVE_HELPER_CONFIG=1
      shift
      ;;
    --recovery-bundle-only)
      RECOVERY_BUNDLE_ONLY=1
      PRESERVE_HELPER_CONFIG=1
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

if [[ "$MODE" == "install" &&
  "${VIVENTIUM_HELPER_RECOVERY_ARM:-0}" != "1" &&
  -e "$APP_SUPPORT_DIR/state/continuity/first-upgrade-bridge.json" ]]
then
  BRIDGE_PYTHON="$(resolve_repo_python)"
  if ! "$BRIDGE_PYTHON" "$REPO_ROOT/scripts/viventium/first_upgrade_bridge.py" \
    finalize-after-commit \
    --repo-root "$REPO_ROOT" \
    --app-support-dir "$APP_SUPPORT_DIR" \
    --config-file "${VIVENTIUM_CONFIG_FILE:-$APP_SUPPORT_DIR/config.yaml}" \
    --runtime-dir "${VIVENTIUM_RUNTIME_DIR:-$APP_SUPPORT_DIR/runtime}" \
    --lock-file "${VIVENTIUM_COMPONENTS_LOCK_FILE:-$REPO_ROOT/components.lock.json}" \
    >/dev/null
  then
    echo "[viventium] First-upgrade post-commit finalization failed closed before helper replacement." >&2
    exit 1
  fi
fi

prepare_helper_app_destination() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_APP_DIR" "$HELPER_APP_BUNDLE" "$LEGACY_HELPER_APP_BUNDLE" \
    "$HELPER_BUNDLE_IDENTIFIER" "$HELPER_EXECUTABLE_NAME" <<'PY'
import json
import os
import plistlib
import stat
import sys
from pathlib import Path

app_dir = Path(os.path.abspath(os.path.expanduser(sys.argv[1])))
bundles = [Path(os.path.abspath(os.path.expanduser(value))) for value in sys.argv[2:4]]
bundle_identifier = sys.argv[4]
executable_name = sys.argv[5]
uid = os.getuid()

if any(bundle.parent != app_dir for bundle in bundles):
    raise SystemExit("[viventium] Refusing helper path outside the validated Applications directory")

def real_owned_directory(path: Path, label: str) -> None:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != uid:
        raise SystemExit(f"[viventium] Refusing unsafe {label}: {path}")

if os.path.lexists(app_dir):
    real_owned_directory(app_dir, "helper Applications directory")
else:
    raise SystemExit(f"[viventium] Helper Applications directory disappeared after capture: {app_dir}")

for bundle in bundles:
    if not os.path.lexists(bundle):
        continue
    metadata = os.lstat(bundle)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != uid:
        raise SystemExit(f"[viventium] Refusing to replace or remove unsafe helper bundle: {bundle}")
    for directory in (
        bundle / "Contents",
        bundle / "Contents" / "MacOS",
        bundle / "Contents" / "Resources",
    ):
        real_owned_directory(directory, "helper bundle directory")
    info = bundle / "Contents" / "Info.plist"
    executable = bundle / "Contents" / "MacOS" / executable_name
    for path, label in ((info, "Info.plist"), (executable, "executable")):
        try:
            child = os.lstat(path)
        except FileNotFoundError as error:
            raise SystemExit(f"[viventium] Refusing unrelated application without helper {label}: {bundle}") from error
        if stat.S_ISLNK(child.st_mode) or not stat.S_ISREG(child.st_mode) or child.st_uid != uid:
            raise SystemExit(f"[viventium] Refusing unsafe helper {label}: {bundle}")
    try:
        with info.open("rb") as handle:
            installed_identifier = plistlib.load(handle).get("CFBundleIdentifier")
    except (OSError, plistlib.InvalidFileException) as error:
        raise SystemExit(f"[viventium] Refusing application with invalid helper Info.plist: {bundle}") from error
    if installed_identifier != bundle_identifier:
        raise SystemExit(f"[viventium] Refusing to replace or remove unrelated application: {bundle}")
    marker = bundle / "Contents" / "Resources" / "viventium-owner.json"
    if os.path.lexists(marker):
        marker_metadata = os.lstat(marker)
        if (
            stat.S_ISLNK(marker_metadata.st_mode)
            or not stat.S_ISREG(marker_metadata.st_mode)
            or marker_metadata.st_uid != uid
        ):
            raise SystemExit(f"[viventium] Refusing unsafe helper ownership marker: {bundle}")
        try:
            owner = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"[viventium] Refusing invalid helper ownership marker: {bundle}") from error
        if owner.get("product") != bundle_identifier or owner.get("schema_version") != 1:
            raise SystemExit(f"[viventium] Refusing unrecognized helper ownership marker: {bundle}")
    # A marker-free bundle with the exact historical bundle ID and executable is
    # the one supported legacy migration shape. No other application is touched.
PY
}

HELPER_RUNTIME_REPO_ROOT="$(resolve_helper_runtime_repo_root "$REPO_ROOT" "$APP_SUPPORT_DIR")"
HELPER_RUNTIME_ALLOW_PROTECTED=0
if active_runtime_checkout_allows_repo_root "$APP_SUPPORT_DIR" "$HELPER_RUNTIME_REPO_ROOT"; then
  HELPER_RUNTIME_ALLOW_PROTECTED=1
fi
if [[ "$HELPER_RUNTIME_REPO_ROOT" != "$REPO_ROOT" ]]; then
  if active_runtime_checkout_matches_repo_root "$APP_SUPPORT_DIR" "$HELPER_RUNTIME_REPO_ROOT"; then
    echo "[viventium] Using configured helper runtime checkout: $HELPER_RUNTIME_REPO_ROOT" >&2
  else
    echo "[viventium] Using public-safe helper runtime checkout: $HELPER_RUNTIME_REPO_ROOT" >&2
  fi
fi
if repo_root_uses_macos_protected_folder_access "$HELPER_RUNTIME_REPO_ROOT" && [[ "$HELPER_RUNTIME_ALLOW_PROTECTED" != "1" ]]; then
  echo "[viventium] Refusing to bind the macOS helper to a protected-folder checkout." >&2
  echo "[viventium] Install or update Viventium from $(public_safe_path_label "$(default_public_install_repo_root)") or run bin/viventium runtime-checkout use <path> --allow-protected-folder for an explicit developer checkout." >&2
  exit 1
fi
if repo_root_uses_macos_protected_folder_access "$HELPER_RUNTIME_REPO_ROOT" && [[ "$HELPER_RUNTIME_ALLOW_PROTECTED" == "1" ]]; then
  echo "[viventium] Binding helper to explicit developer checkout inside a macOS protected folder: $HELPER_RUNTIME_REPO_ROOT" >&2
fi

HELPER_TRANSACTION_PYTHON="$(resolve_repo_python)"

recover_prior_helper_bundle_transaction() {
  [[ -e "$HELPER_INSTALL_RECEIPT" ]] || return 0
  if [[ -L "$HELPER_INSTALL_RECEIPT" || ! -f "$HELPER_INSTALL_RECEIPT" ]]; then
    echo "[viventium] Refusing unsafe helper-install recovery receipt." >&2
    return 1
  fi
  local prior_destination_state=""
  local prior_stage_state=""
  prior_destination_state="$(
    "$HELPER_TRANSACTION_PYTHON" - "$HELPER_INSTALL_RECEIPT" destinationState <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload.get(sys.argv[2])
if not isinstance(value, dict):
    raise SystemExit(3)
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
PY
  )" || true
  prior_stage_state="$(
    "$HELPER_TRANSACTION_PYTHON" - "$HELPER_INSTALL_RECEIPT" stageState <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload.get(sys.argv[2])
if not isinstance(value, dict):
    raise SystemExit(3)
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
PY
  )" || true
  if [[ -z "$prior_destination_state" || -z "$prior_stage_state" ]]; then
    return 0
  fi

  echo "[viventium] Recovering a previously interrupted helper bundle transaction." >&2
  if ! "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" commit-persisted \
    --destination-state "$prior_destination_state" \
    --stage-state "$prior_stage_state" >/dev/null 2>&1
  then
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" rollback-persisted \
      --destination-state "$prior_destination_state" \
      --stage-state "$prior_stage_state"
  fi
}

recover_prior_helper_bundle_transaction
HELPER_DESTINATION_STATE="$(
  "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" capture \
    --root "$HELPER_APP_DIR" \
    --current-name "$(basename "$HELPER_APP_BUNDLE")" \
    --legacy-name "$(basename "$LEGACY_HELPER_APP_BUNDLE")" \
    --bundle-identifier "$HELPER_BUNDLE_IDENTIFIER" \
    --executable-name "$HELPER_EXECUTABLE_NAME" \
    --create-root
)"
prepare_helper_app_destination
mkdir -p "$APP_SUPPORT_DIR" "$APP_SUPPORT_DIR/logs" "$LAUNCH_AGENT_DIR"
HELPER_SCHEDULING_COMPONENT_DIR="${VIVENTIUM_HELPER_SCHEDULING_COMPONENT_DIR:-$APP_SUPPORT_DIR/runtime/components/scheduling-cortex}"

write_helper_install_receipt() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_INSTALL_RECEIPT" "$HELPER_RUNTIME_REPO_ROOT" \
    "${HELPER_DESTINATION_STATE:-}" "${HELPER_STAGE_STATE:-}" <<'PY'
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

path = Path(sys.argv[1])
repo_root = sys.argv[2]
destination_state = sys.argv[3]
stage_state = sys.argv[4]
path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "schemaVersion": 1,
    "status": "forward_recovery_required",
    "repoRoot": repo_root,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
}
if destination_state and stage_state:
    payload["destinationState"] = json.loads(destination_state)
    payload["stageState"] = json.loads(stage_state)
descriptor, temporary_name = tempfile.mkstemp(
    prefix=f".{path.name}.",
    dir=path.parent,
)
temporary = Path(temporary_name)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
finally:
    temporary.unlink(missing_ok=True)
PY
}

qa_kill_helper_install_if_requested() {
  local phase="${1:-}"
  if [[ "${VIVENTIUM_QA_KILL_HELPER_INSTALL_AFTER:-}" == "$phase" ]]; then
    kill -KILL "$$"
  fi
}

clear_helper_install_receipt() {
  rm -f -- "$HELPER_INSTALL_RECEIPT"
}

write_helper_config() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_CONFIG_FILE" "$HELPER_RUNTIME_REPO_ROOT" "$APP_SUPPORT_DIR" \
    "$HELPER_RUNTIME_ALLOW_PROTECTED" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
repo_root = sys.argv[2]
app_support_dir = sys.argv[3]
allow_protected = sys.argv[4] == "1"
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
        "repoRoot": repo_root,
        "appSupportDir": app_support_dir,
        "allowProtectedRepoRoot": allow_protected,
        "showInStatusBar": bool(existing.get("showInStatusBar", True)),
    }
)
payload = (json.dumps(config, indent=2) + "\n").encode("utf-8")
descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
temporary = Path(temporary_name)
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
PY
}

verify_preserved_helper_config() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_CONFIG_FILE" "$HELPER_RUNTIME_REPO_ROOT" \
    "$APP_SUPPORT_DIR" <<'PY'
import json
import os
from pathlib import Path
import stat
import sys

path = Path(os.path.abspath(os.path.expanduser(sys.argv[1])))
expected_repo = Path(os.path.abspath(os.path.expanduser(sys.argv[2])))
expected_support = Path(os.path.abspath(os.path.expanduser(sys.argv[3])))
metadata = os.lstat(path)
if (
    stat.S_ISLNK(metadata.st_mode)
    or not stat.S_ISREG(metadata.st_mode)
    or metadata.st_uid != os.getuid()
    or stat.S_IMODE(metadata.st_mode) & 0o077
):
    raise SystemExit("[viventium] Preserved helper config is unsafe")
payload = json.loads(path.read_text(encoding="utf-8"))
configured_repo = Path(
    os.path.abspath(os.path.expanduser(str(payload.get("repoRoot") or "")))
)
configured_support = Path(
    os.path.abspath(os.path.expanduser(str(payload.get("appSupportDir") or "")))
)
if configured_repo != expected_repo or configured_support != expected_support:
    raise SystemExit(
        "[viventium] Preserved helper config does not own this runtime"
    )
PY
}

clear_committed_telegram_recovery_pointer() {
  [[ "${VIVENTIUM_HELPER_RECOVERY_ARM:-0}" != "1" ]] || return 0
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" "$SCRIPT_DIR/telegram_runtime_component.py" clear-recovery \
    --app-support-dir "$APP_SUPPORT_DIR" >/dev/null
}

install_scheduler_runtime_component() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_RUNTIME_REPO_ROOT" "$APP_SUPPORT_DIR" \
    "$HELPER_SCHEDULING_COMPONENT_DIR" <<'PY'
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

repo_root = Path(os.path.abspath(os.path.expanduser(sys.argv[1])))
app_support_dir = Path(os.path.abspath(os.path.expanduser(sys.argv[2])))
target = Path(os.path.abspath(os.path.expanduser(sys.argv[3])))
source = (
    repo_root
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "MCPs"
    / "scheduling-cortex"
)
expected_target = app_support_dir / "runtime" / "components" / "scheduling-cortex"

if target != expected_target:
    raise SystemExit("[viventium] Refusing Scheduler runtime component outside App Support")
try:
    source_resolved = source.resolve(strict=True)
    repo_resolved = repo_root.resolve(strict=True)
except FileNotFoundError as error:
    raise SystemExit("[viventium] Missing Scheduling Cortex runtime source") from error
try:
    source_resolved.relative_to(repo_resolved)
except ValueError as error:
    raise SystemExit("[viventium] Refusing Scheduling Cortex source outside runtime checkout") from error
if source.is_symlink() or not source.is_dir():
    raise SystemExit("[viventium] Scheduling Cortex runtime source must be a real directory")

required_files = ("pyproject.toml", "uv.lock")
for filename in required_files:
    candidate = source / filename
    if candidate.is_symlink() or not candidate.is_file():
        raise SystemExit(f"[viventium] Missing safe Scheduling Cortex runtime file: {filename}")
package_source = source / "scheduling_cortex"
if package_source.is_symlink() or not package_source.is_dir():
    raise SystemExit("[viventium] Missing safe Scheduling Cortex Python package")
shared_source = repo_root / "viventium_v0_4" / "shared"
workbench_source = (
    repo_root
    / "viventium_v0_4"
    / "prompt-workbench"
    / "backend"
    / "prompt_workbench"
)
prompt_registry_source = repo_root / "scripts" / "viventium" / "prompt_registry.py"
source_of_truth = (
    repo_root
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
)
prompts_source = source_of_truth / "prompts"
for candidate, label in (
    (shared_source, "shared runtime"),
    (workbench_source, "Prompt Workbench runtime"),
    (prompts_source, "prompt registry"),
):
    if candidate.is_symlink() or not candidate.is_dir():
        raise SystemExit(f"[viventium] Missing safe Scheduling Cortex {label} support")
for candidate, label in (
    (prompt_registry_source, "prompt registry compiler"),
    (source_of_truth / "local.viventium-agents.yaml", "agent source of truth"),
    (source_of_truth / "local.librechat.yaml", "LibreChat source of truth"),
):
    if candidate.is_symlink() or not candidate.is_file():
        raise SystemExit(f"[viventium] Missing safe Scheduling Cortex {label}")

target.parent.mkdir(parents=True, exist_ok=True)
if target.parent.is_symlink():
    raise SystemExit("[viventium] Refusing symlinked Scheduler runtime component directory")
if os.path.lexists(target):
    metadata = os.lstat(target)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise SystemExit("[viventium] Refusing unsafe existing Scheduler runtime component")

stage = Path(tempfile.mkdtemp(prefix=".scheduling-cortex.stage.", dir=target.parent))
backup: Path | None = None
venv_transferred = False
committed = False
try:
    def copy_selected_tree(
        source_root: Path,
        destination_root: Path,
        allowed_suffixes: frozenset[str],
    ) -> None:
        destination_root.mkdir(parents=True, exist_ok=True)
        for candidate in sorted(source_root.rglob("*")):
            if candidate.is_symlink():
                raise SystemExit("[viventium] Refusing symlinked Scheduling Cortex support file")
            if not candidate.is_file() or candidate.suffix not in allowed_suffixes:
                continue
            relative = candidate.relative_to(source_root)
            destination = destination_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)

    for filename in (*required_files, "requirements.txt", "README.md"):
        candidate = source / filename
        if candidate.is_symlink():
            raise SystemExit(f"[viventium] Refusing symlinked Scheduling Cortex file: {filename}")
        if candidate.is_file():
            shutil.copy2(candidate, stage / filename)

    package_target = stage / "scheduling_cortex"
    package_target.mkdir()
    for candidate in sorted(package_source.rglob("*.py")):
        if candidate.is_symlink() or not candidate.is_file():
            raise SystemExit("[viventium] Refusing unsafe Scheduling Cortex package file")
        relative = candidate.relative_to(package_source)
        destination = package_target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, destination)

    copy_selected_tree(shared_source, stage / "shared", frozenset({".py"}))
    copy_selected_tree(
        workbench_source,
        stage / "viventium_v0_4" / "prompt-workbench" / "backend" / "prompt_workbench",
        frozenset({".py"}),
    )
    prompt_registry_target = stage / "scripts" / "viventium" / "prompt_registry.py"
    prompt_registry_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prompt_registry_source, prompt_registry_target)
    installed_source_of_truth = (
        stage / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth"
    )
    installed_source_of_truth.mkdir(parents=True, exist_ok=True)
    for filename in ("local.viventium-agents.yaml", "local.librechat.yaml"):
        shutil.copy2(source_of_truth / filename, installed_source_of_truth / filename)
    copy_selected_tree(
        prompts_source,
        installed_source_of_truth / "prompts",
        frozenset({".md", ".yaml", ".yml"}),
    )

    if os.path.lexists(target):
        backup = Path(
            tempfile.mkdtemp(prefix=".scheduling-cortex.backup.", dir=target.parent)
        )
        backup.rmdir()
        target.rename(backup)
    stage.rename(target)
    if backup is not None:
        prior_venv = backup / ".venv"
        if (
            prior_venv.exists()
            and not prior_venv.is_symlink()
            and prior_venv.is_dir()
            and not (target / ".venv").exists()
        ):
            prior_venv.rename(target / ".venv")
            venv_transferred = True
            if (
                os.environ.get(
                    "VIVENTIUM_QA_FAIL_SCHEDULER_AFTER_VENV_TRANSFER"
                )
                == "1"
            ):
                raise RuntimeError(
                    "synthetic failure after Scheduler venv transfer"
                )
    committed = True
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            # The new component and preserved venv are already committed.
            # A stale owner-private backup is safer than attempting rollback
            # from a backup that cleanup may have partially removed.
            pass
except BaseException:
    if not committed and backup is not None and backup.exists():
        if venv_transferred:
            activated_venv = target / ".venv"
            restored_venv = backup / ".venv"
            if (
                activated_venv.is_symlink()
                or not activated_venv.is_dir()
                or restored_venv.exists()
                or restored_venv.is_symlink()
            ):
                raise RuntimeError(
                    "[viventium] Scheduler rollback could not restore the prior venv safely"
                )
            activated_venv.rename(restored_venv)
        if target.exists():
            shutil.rmtree(target)
        backup.rename(target)
    raise
finally:
    if stage.exists():
        shutil.rmtree(stage)
PY
}

prepare_telegram_runtime_component() {
  local python_bin
  local selection_file="$APP_SUPPORT_DIR/runtime/components/telegram-viventium.json"
  python_bin="$(resolve_repo_python)"
  "$python_bin" "$SCRIPT_DIR/telegram_runtime_component.py" prepare \
    --repo-root "$HELPER_RUNTIME_REPO_ROOT" \
    --app-support-dir "$APP_SUPPORT_DIR" \
    --selection-file "$selection_file" \
    --sync-dependencies >/dev/null
}

write_helper_launcher_scripts() {
  local python_bin
  python_bin="$(resolve_repo_python)"
  "$python_bin" - "$HELPER_RUNTIME_REPO_ROOT" "$APP_SUPPORT_DIR" "$HELPER_SCRIPT_DIR" \
    "$HELPER_STACK_SCRIPT_COPY" "$HELPER_STACK_WRAPPER" <<'PY'
import os
from pathlib import Path
import shlex
import sys
import tempfile

repo_root = Path(sys.argv[1]).resolve()
app_support_dir = Path(sys.argv[2]).resolve()
helper_script_dir = Path(sys.argv[3]).resolve()
stack_script_copy = Path(sys.argv[4]).resolve()
stack_wrapper = Path(sys.argv[5]).resolve()
source_script = repo_root / "viventium_v0_4" / "viventium-librechat-start.sh"
bin_viventium = repo_root / "bin" / "viventium"

helper_script_dir.mkdir(parents=True, exist_ok=True)

def replace_text(path: Path, content: str, mode: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

replace_text(stack_script_copy, source_script.read_text(encoding="utf-8"), 0o755)

runtime_env = app_support_dir / "runtime" / "runtime.env"
runtime_local_env = app_support_dir / "runtime" / "runtime.local.env"
scheduling_mcp_dir = app_support_dir / "runtime" / "components" / "scheduling-cortex"

def q(value: Path | str) -> str:
    return shlex.quote(str(value))

dollar = chr(36)

wrapper = f"""#!/usr/bin/env bash
# Compatibility wrapper written by the installer. The menu-bar helper builds
# detached start/stop commands from helper-config.json directly so stale wrapper
# contents cannot rebind runtime operations to a protected-folder checkout.
set -euo pipefail
export VIVENTIUM_HELPER_V0_ROOT={q(repo_root / "viventium_v0_4")}
export VIVENTIUM_HELPER_CORE_ROOT={q(repo_root)}
export VIVENTIUM_HELPER_WORKSPACE_ROOT={q(repo_root.parent)}
export VIVENTIUM_APP_SUPPORT_DIR={q(app_support_dir)}
export VIVENTIUM_ENV_FILE={q(runtime_env)}
export VIVENTIUM_ENV_LOCAL_FILE={q(runtime_local_env)}
export VIVENTIUM_SCHEDULING_MCP_DIR={q(scheduling_mcp_dir)}
if [[ "{dollar}{{1:-}}" == "--stop" ]]; then
  shift
  exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} stop "{dollar}@"
fi
export VIVENTIUM_HELPER_STOP_BACKGROUND_NATIVE=1
export VIVENTIUM_DETACHED_START=true
exec /bin/bash {q(bin_viventium)} --app-support-dir {q(app_support_dir)} launch "{dollar}@"
"""

replace_text(stack_wrapper, wrapper, 0o755)

for pattern in ("*.command", "helper-detached-*.sh"):
    for stale_script in helper_script_dir.glob(pattern):
        try:
            stale_script.unlink()
        except FileNotFoundError:
            pass
PY
}

write_launch_agent_plist() {
  local python_bin public_install_dir
  python_bin="$(resolve_repo_python)"
  public_install_dir="$(default_public_install_repo_root)"
  "$python_bin" - "$LAUNCH_AGENT_PLIST" "$HELPER_APP_BUNDLE" "$HELPER_EXECUTABLE_NAME" \
    "$HOME" "$PATH" "$HELPER_RUNTIME_REPO_ROOT" "$public_install_dir" "$HELPER_LOG_FILE" <<'PY'
import os
import plistlib
import sys
import tempfile
from pathlib import Path

(
    output_path,
    helper_bundle,
    executable_name,
    home,
    executable_path,
    runtime_repo_root,
    public_install_dir,
    log_file,
) = sys.argv[1:]
payload = {
    "Label": "ai.viventium.helper",
    "ProgramArguments": [str(Path(helper_bundle) / "Contents" / "MacOS" / executable_name)],
    "WorkingDirectory": home,
    "RunAtLoad": True,
    "LimitLoadToSessionType": ["Aqua"],
    "EnvironmentVariables": {
        "PATH": executable_path,
        "VIVENTIUM_HELPER_RUNTIME_REPO_ROOT": runtime_repo_root,
        "VIVENTIUM_PUBLIC_INSTALL_DIR": public_install_dir,
    },
    "StandardOutPath": log_file,
    "StandardErrorPath": log_file,
}
path = Path(output_path)
descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
temporary = Path(temporary_name)
try:
    with os.fdopen(descriptor, "wb") as handle:
        plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
PY
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
  # Cleanup is intentionally limited to paths owned by Viventium. Never read or
  # rewrite shell history, terminal session state, or unrelated LaunchAgents.
  find "$HELPER_SCRIPT_DIR" -maxdepth 1 -type f \
    \( -name '*.command' -o -name 'helper-detached-*.sh' \) -delete 2>/dev/null || true
  local legacy_launch_agent="$LAUNCH_AGENT_DIR/ai.viventium.helper.terminal.plist"
  if [[ -f "$legacy_launch_agent" ]]; then
    [[ "$SKIP_LAUNCHCTL" == "1" ]] || \
      launchctl bootout "gui/$UID" "$legacy_launch_agent" >/dev/null 2>&1 || true
    rm -f "$legacy_launch_agent"
  fi
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
  prebuilt_helper_binary_matches_digest || return 1

  local expected_hash
  local actual_hash
  expected_hash="$(tr -d '[:space:]' < "$HELPER_PREBUILT_SOURCE_HASH_FILE")"
  actual_hash="$(helper_source_hash)"
  [[ -n "$expected_hash" && "$expected_hash" == "$actual_hash" ]]
}

prebuilt_helper_binary_matches_digest() {
  [[ -x "$HELPER_PREBUILT_EXECUTABLE" ]] || return 1
  [[ -f "$HELPER_PREBUILT_BINARY_HASH_FILE" ]] || return 1
  local expected_hash
  local actual_hash
  expected_hash="$(tr -d '[:space:]' < "$HELPER_PREBUILT_BINARY_HASH_FILE" | tr '[:upper:]' '[:lower:]')"
  [[ "$expected_hash" =~ ^[0-9a-fA-F]{64}$ ]] || return 1
  actual_hash="$(shasum -a 256 "$HELPER_PREBUILT_EXECUTABLE" | awk '{print $1}')"
  [[ "$expected_hash" == "$actual_hash" ]]
}

use_prebuilt_helper() {
  local notice="${1:-Using prebuilt helper fallback}"
  mkdir -p "$HELPER_BUILD_DIR"
  cp "$HELPER_PREBUILT_EXECUTABLE" "$BUILT_EXECUTABLE"
  chmod +x "$BUILT_EXECUTABLE"
  echo "[viventium] $notice from $HELPER_PREBUILT_EXECUTABLE" >&2
}

build_helper() {
  if [[ "$SKIP_BUILD" == "1" ]]; then
    [[ -x "$BUILT_EXECUTABLE" ]] || {
      echo "Missing built helper executable: $BUILT_EXECUTABLE" >&2
      exit 1
    }
    return 0
  fi
  if [[ "$FORCE_LOCAL_BUILD" != "1" ]] && prebuilt_helper_matches_sources; then
    use_prebuilt_helper "Using shipped prebuilt helper"
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
  if [[ "$FORCE_LOCAL_BUILD" != "1" ]] && prebuilt_helper_matches_sources; then
    use_prebuilt_helper "Using prebuilt helper fallback"
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

  if [[ "$FORCE_LOCAL_BUILD" == "1" ]]; then
    echo "[viventium] Local helper build was forced and no source build completed successfully" >&2
    return 1
  fi
  if [[ -f "$HELPER_PREBUILT_SOURCE_HASH_FILE" ]]; then
    echo "[viventium] Prebuilt helper fallback exists but does not match current helper sources" >&2
  else
    echo "[viventium] No matching prebuilt helper fallback found" >&2
  fi

  return 1
}

install_bundle() {
  trap 'rollback_install_transaction $?' ERR
  trap 'rollback_install_transaction 130' INT TERM
  local icon_path=""
  [[ ! -f "$HELPER_ICON_RESOURCE" ]] || icon_path="$HELPER_ICON_RESOURCE"
  HELPER_STAGE_STATE="$(
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" stage \
      --destination-state "$HELPER_DESTINATION_STATE" \
      --built-executable "$BUILT_EXECUTABLE" \
      --info-plist "$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/Resources/Info.plist" \
      --icon-path "$icon_path" \
      --bundle-identifier "$HELPER_BUNDLE_IDENTIFIER" \
      --executable-name "$HELPER_EXECUTABLE_NAME"
  )"
  STAGED_APP_BUNDLE="$(
    "$HELPER_TRANSACTION_PYTHON" -c \
      'import json,sys; print(json.loads(sys.argv[1])["app_path"])' \
      "$HELPER_STAGE_STATE"
  )"
}

verify_installed_bundle() {
  local bundle="${1:-$HELPER_APP_BUNDLE}"
  if [[ "$bundle" == "$STAGED_APP_BUNDLE" && -n "$HELPER_STAGE_STATE" ]]; then
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" validate-stage \
      --destination-state "$HELPER_DESTINATION_STATE" \
      --stage-state "$HELPER_STAGE_STATE"
  fi
  local installed_executable="$bundle/Contents/MacOS/$HELPER_EXECUTABLE_NAME"
  [[ -x "$installed_executable" ]] || {
    echo "[viventium] Installed helper executable is missing: $installed_executable" >&2
    exit 1
  }
  if ! cmp -s "$BUILT_EXECUTABLE" "$installed_executable"; then
    echo "[viventium] Installed helper executable does not match the built/shipped helper." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "ingest-transcripts" >/dev/null; then
    echo "[viventium] Installed helper is missing transcript ingest support." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "--ignore-idle-gate" >/dev/null; then
    echo "[viventium] Installed helper is missing the manual transcript ingest idle-gate override." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "--until-caught-up" >/dev/null; then
    echo "[viventium] Installed helper is missing bounded transcript catch-up support." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "--interactive-maintenance" >/dev/null; then
    echo "[viventium] Installed helper is missing interactive transcript maintenance support." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "Choose Transcripts Folder" >/dev/null; then
    echo "[viventium] Installed helper is missing the transcript folder picker." >&2
    exit 1
  fi
  if ! strings "$installed_executable" | grep -F -- "prompt-workbench" >/dev/null; then
    echo "[viventium] Installed helper is missing Prompt Workbench support." >&2
    exit 1
  fi
}

sign_installed_bundle() {
  local bundle="${1:-$HELPER_APP_BUNDLE}"
  if [[ "$bundle" == "$STAGED_APP_BUNDLE" && -n "$HELPER_STAGE_STATE" ]]; then
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" validate-stage \
      --destination-state "$HELPER_DESTINATION_STATE" \
      --stage-state "$HELPER_STAGE_STATE"
  fi
  [[ "$SKIP_CODESIGN" == "1" ]] && return 0
  [[ -x /usr/bin/codesign ]] || return 0

  if ! /usr/bin/codesign --force --sign - --identifier "$HELPER_BUNDLE_IDENTIFIER" "$bundle" >/dev/null 2>&1; then
    echo "[viventium] Warning: Viventium helper installed but could not be code signed locally." >&2
  fi
}

refresh_staged_bundle_state() {
  HELPER_STAGE_STATE="$(
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" refresh-stage \
      --destination-state "$HELPER_DESTINATION_STATE" \
      --stage-state "$HELPER_STAGE_STATE"
  )"
}

rollback_install_transaction() {
  local exit_code="${1:-1}"
  local rollback_status=0
  trap - ERR INT TERM
  set +e
  if [[ -n "$HELPER_STAGE_STATE" ]]; then
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" rollback-persisted \
      --destination-state "$HELPER_DESTINATION_STATE" \
      --stage-state "$HELPER_STAGE_STATE" || rollback_status=$?
  fi
  if [[ "$rollback_status" == "0" ]]; then
    echo "[viventium] Helper installation failed; restored the previously owned helper bundle. Forward recovery remains pending." >&2
  else
    echo "[viventium] Helper installation failed and rollback stopped at a changed filesystem boundary; retained the owned backup for recovery." >&2
  fi
  exit "$exit_code"
}

activate_staged_bundle() {
  trap 'rollback_install_transaction $?' ERR
  trap 'rollback_install_transaction 130' INT TERM
  "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" activate \
    --destination-state "$HELPER_DESTINATION_STATE" \
    --stage-state "$HELPER_STAGE_STATE" >/dev/null
}

commit_install_transaction() {
  trap - ERR INT TERM
  "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" commit-persisted \
    --destination-state "$HELPER_DESTINATION_STATE" \
    --stage-state "$HELPER_STAGE_STATE" || \
    echo "[viventium] Warning: an identity-bound helper transaction backup remains for recovery." >&2
  HELPER_STAGE_STATE=""
  clear_helper_install_receipt
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
    if [[ "$RECOVERY_BUNDLE_ONLY" == "1" ]]; then
      [[ -d "$HELPER_APP_BUNDLE" && ! -L "$HELPER_APP_BUNDLE" ]] || {
        echo "[viventium] Recovery-only helper activation requires an existing owned helper bundle." >&2
        exit 1
      }
      verify_preserved_helper_config
      local_helper_was_running=0
      if pgrep -f "$HELPER_APP_BUNDLE/Contents/MacOS/$HELPER_EXECUTABLE_NAME" >/dev/null 2>&1; then
        local_helper_was_running=1
      fi
      write_helper_install_receipt
      build_helper
      install_bundle
      verify_installed_bundle "$STAGED_APP_BUNDLE"
      sign_installed_bundle "$STAGED_APP_BUNDLE"
      refresh_staged_bundle_state
      write_helper_install_receipt
      stop_existing_helper
      activate_staged_bundle
      qa_kill_helper_install_if_requested activation
      commit_install_transaction
      if [[ "$local_helper_was_running" == "1" ]]; then
        /usr/bin/open -g "$HELPER_APP_BUNDLE"
      fi
      exit 0
    fi
    write_helper_install_receipt
    cleanup_legacy_terminal_helper_launchers
    build_helper
    install_bundle
    verify_installed_bundle "$STAGED_APP_BUNDLE"
    sign_installed_bundle "$STAGED_APP_BUNDLE"
    refresh_staged_bundle_state
    write_helper_install_receipt
    if [[ "$PRESERVE_HELPER_CONFIG" == "1" ]]; then
      verify_preserved_helper_config
    else
      write_helper_config
    fi
    qa_kill_helper_install_if_requested config
    install_scheduler_runtime_component
    prepare_telegram_runtime_component
    qa_kill_helper_install_if_requested scheduler
    write_helper_launcher_scripts
    qa_kill_helper_install_if_requested scripts
    stop_existing_helper
    unregister_login_item || true
    remove_launch_agent
    activate_staged_bundle
    qa_kill_helper_install_if_requested activation
    register_login_item || {
      write_launch_agent_plist
      bootstrap_launch_agent
    }
    qa_kill_helper_install_if_requested registration
    launch_helper_app
    commit_install_transaction
    clear_committed_telegram_recovery_pointer
    ;;
  uninstall)
    cleanup_legacy_terminal_helper_launchers
    unregister_login_item || true
    remove_launch_agent
    stop_existing_helper
    "$HELPER_TRANSACTION_PYTHON" "$HELPER_TRANSACTION_TOOL" uninstall \
      --destination-state "$HELPER_DESTINATION_STATE"
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 1
    ;;
esac
