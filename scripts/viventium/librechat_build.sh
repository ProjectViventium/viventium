#!/usr/bin/env bash
# Existing LibreChat dependency/build owner, shared by startup and candidate preparation.
# Sourcing initializes only process-local helpers/flags; the caller chooses when to prepare.

configure_librechat_build_runtime() {
  VIVENTIUM_NODE_RUNTIME_VERSION="24.16.0"
  VIVENTIUM_NODE_RUNTIME_ARCH="$(uname -m 2>/dev/null || true)"
  VIVENTIUM_RUNTIME_TOOLS_DIR="${VIVENTIUM_RUNTIME_TOOLS_DIR:-${VIVENTIUM_APP_SUPPORT_DIR:-$HOME/Library/Application Support/Viventium}/runtime-tools}"
  VIVENTIUM_NODE_RUNTIME_BIN="${VIVENTIUM_RUNTIME_TOOLS_DIR}/node/${VIVENTIUM_NODE_RUNTIME_VERSION}/${VIVENTIUM_NODE_RUNTIME_ARCH}/bin"
  if [[ -d "$VIVENTIUM_NODE_RUNTIME_BIN" ]]; then
    export PATH="$VIVENTIUM_NODE_RUNTIME_BIN:${PATH}"
  fi
}

current_node_version() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi

  local version=""
  version="$(node -v 2>/dev/null || true)"
  if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    return 1
  fi

  printf '%s\n' "$version"
}

prepend_validated_node_runtime_to_path() {
  if [[ -d "$VIVENTIUM_NODE_RUNTIME_BIN" ]]; then
    export PATH="$VIVENTIUM_NODE_RUNTIME_BIN:${PATH}"
    hash -r 2>/dev/null || true
  fi
}

ensure_validated_node24_runtime() {
  prepend_validated_node_runtime_to_path

  local version=""
  local resolved_node=""
  local resolved_npm=""
  version="$(current_node_version || true)"
  resolved_node="$(command -v node 2>/dev/null || true)"
  resolved_npm="$(command -v npm 2>/dev/null || true)"
  if [[ "$version" == "v${VIVENTIUM_NODE_RUNTIME_VERSION}" \
    && "$resolved_node" == "${VIVENTIUM_NODE_RUNTIME_BIN}/node" \
    && "$resolved_npm" == "${VIVENTIUM_NODE_RUNTIME_BIN}/npm" ]]; then
    return 0
  fi

  local current_version="missing"
  if command -v node >/dev/null 2>&1; then
    current_version="$(node -v 2>/dev/null || printf 'unknown')"
  fi

  log_error "Validated Node ${VIVENTIUM_NODE_RUNTIME_VERSION} runtime required at ${VIVENTIUM_NODE_RUNTIME_BIN}; found ${current_version} at ${resolved_node:-missing}. Run 'bin/viventium upgrade' to install the pinned official runtime"
  return 1
}

librechat_client_build_node_options() {
  local max_old_space_size="${VIVENTIUM_CLIENT_BUILD_MAX_OLD_SPACE_SIZE:-4096}"
  if [[ -n "$max_old_space_size" ]]; then
    printf '%s\n' "--max-old-space-size=${max_old_space_size}"
  fi
}

## === VIVENTIUM START ===
# Feature: LibreChat dependency auto-heal after pulls.
# Purpose: Prevent blank 3090/3080 startup when lockfile changes or critical modules are missing.
clean_librechat_dependency_tree() {
  (
    cd "$LIBRECHAT_DIR" || exit 1
    local rel=""
    for rel in \
      node_modules \
      client/node_modules \
      packages/api/node_modules \
      packages/client/node_modules \
      packages/data-provider/node_modules \
      packages/data-schemas/node_modules
    do
      local target="$LIBRECHAT_DIR/$rel"
      [[ -e "$target" || -L "$target" ]] || continue
      chmod -R u+w "$target" >/dev/null 2>&1 || true
      "${PYTHON_BIN:-python3}" - "$target" <<'PY' || exit 1
import os
import shutil
import stat
import sys
from pathlib import Path

target = Path(sys.argv[1])
if not target.exists() and not target.is_symlink():
    raise SystemExit(0)

def onerror(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass
    func(path)

if target.is_symlink() or target.is_file():
    target.unlink(missing_ok=True)
else:
    shutil.rmtree(target, onerror=onerror)
PY
    done
  )
}

run_librechat_npm() {
  if command -v corepack >/dev/null 2>&1; then
    corepack npm "$@"
    return
  fi
  npm "$@"
}


run_librechat_dependency_install() {
  if [[ -f "package-lock.json" ]]; then
    run_librechat_npm ci
  else
    run_librechat_npm install
  fi
}

LIBRECHAT_DEPS_INSTALLED_THIS_RUN=false
LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=false
LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN=false
LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN=false

default_librechat_health_retries() {
  if [[ "${LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN:-false}" == "true" || "${LIBRECHAT_PACKAGES_REBUILT_THIS_RUN:-false}" == "true" ]]; then
    echo 900
    return 0
  fi
  if [[ "${LIBRECHAT_DEPS_INSTALLED_THIS_RUN:-false}" == "true" ]]; then
    echo 300
    return 0
  fi
  echo 120
}

librechat_dependency_install_reason() {
  if [[ ! -d node_modules ]]; then
    printf '%s\n' 'node_modules missing'
  elif [[ -f package-lock.json && ( ! -f node_modules/.package-lock.json || package-lock.json -nt node_modules/.package-lock.json ) ]]; then
    printf '%s\n' 'package-lock changed'
  elif ! node -e "require.resolve('@google/genai')" >/dev/null 2>&1; then
    printf '%s\n' '@google/genai missing'
  fi
  return 0
}

ensure_librechat_node_dependencies() {
  if [[ ! -d "$LIBRECHAT_DIR" ]]; then
    log_error "LibreChat directory not found: $LIBRECHAT_DIR"
    return 1
  fi

  local deps_reason=""
  local deps_installed=false

  pushd "$LIBRECHAT_DIR" >/dev/null || return 1

  ensure_validated_node24_runtime || {
    popd >/dev/null || true
    return 1
  }

  deps_reason="$(librechat_dependency_install_reason)" || {
    popd >/dev/null || true
    return 1
  }

  if [[ -n "$deps_reason" ]]; then
    echo -e "${YELLOW}[viventium]${NC} Installing LibreChat dependencies (${deps_reason})..."
    if ! run_librechat_dependency_install; then
      echo -e "${YELLOW}[viventium]${NC} LibreChat dependency install failed; cleaning dependency trees and retrying once..."
      clean_librechat_dependency_tree || {
        popd >/dev/null || true
        return 1
      }
      run_librechat_dependency_install || {
        popd >/dev/null || true
        return 1
      }
    fi
    deps_installed=true
  fi

  if ! node -e "require.resolve('@google/genai')" >/dev/null 2>&1; then
    echo -e "${RED}[viventium]${NC} LibreChat dependency check failed: @google/genai not found"
    popd >/dev/null || true
    return 1
  fi

  popd >/dev/null || return 1

  if [[ "$deps_installed" == "true" ]]; then
    LIBRECHAT_DEPS_INSTALLED_THIS_RUN=true
  fi

  return 0
}
## === VIVENTIUM END ===

## === VIVENTIUM START ===
# Feature: Build-aware first-run LibreChat package helpers.
# Purpose: fresh installs need API package dist outputs before user-default reconciliation
# and agent seeding can run, while the direct startup path should not rebuild the client
# package twice during the same cold boot.
find_librechat_source_newer_than_dist() {
  local dist_file="${1:-}"
  shift || true

  if [[ -z "$dist_file" || ! -f "$dist_file" ]]; then
    return 0
  fi

  local candidate=""
  local newer_source=""
  for candidate in "$@"; do
    if [[ -f "$candidate" && "$candidate" -nt "$dist_file" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    if [[ -d "$candidate" ]]; then
      newer_source="$(find "$candidate" -type f -newer "$dist_file" 2>/dev/null | head -n 1)"
      if [[ -n "$newer_source" ]]; then
        printf '%s\n' "$newer_source"
        return 0
      fi
    fi
  done

  return 1
}

should_rebuild_librechat_server_packages() {
  if [[ "${VIVENTIUM_FORCE_PACKAGE_REBUILD:-0}" == "1" ]]; then
    return 0
  fi

  local markers=(
    "$LIBRECHAT_DIR/packages/data-provider/dist/index.js"
    "$LIBRECHAT_DIR/packages/data-schemas/dist/index.cjs"
    "$LIBRECHAT_DIR/packages/api/dist/index.js"
  )

  local marker
  for marker in "${markers[@]}"; do
    if [[ ! -f "$marker" ]]; then
      return 0
    fi
  done

  if find_librechat_source_newer_than_dist \
    "${markers[0]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/data-provider/src" \
    "$LIBRECHAT_DIR/packages/data-provider/react-query" \
    "$LIBRECHAT_DIR/packages/data-provider/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-provider/server-rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-provider/package.json" \
    >/dev/null; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "${markers[1]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/data-schemas/src" \
    "$LIBRECHAT_DIR/packages/data-schemas/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/data-schemas/package.json" \
    >/dev/null; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "${markers[2]}" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/api/src" \
    "$LIBRECHAT_DIR/packages/api/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/api/package.json" \
    >/dev/null; then
    return 0
  fi

  return 1
}

should_rebuild_librechat_client_package() {
  if [[ "${VIVENTIUM_FORCE_PACKAGE_REBUILD:-0}" == "1" ]]; then
    return 0
  fi

  local marker="$LIBRECHAT_DIR/packages/client/dist/index.js"
  if [[ ! -f "$marker" ]]; then
    return 0
  fi

  if find_librechat_source_newer_than_dist \
    "$marker" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/packages/client/src" \
    "$LIBRECHAT_DIR/packages/client/rollup.config.js" \
    "$LIBRECHAT_DIR/packages/client/package.json" \
    >/dev/null; then
    return 0
  fi

  return 1
}

ensure_librechat_server_packages_ready() {
  if [[ "${LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN:-false}" == "true" ]]; then
    return 0
  fi

  if should_rebuild_librechat_server_packages; then
    echo "[viventium] Building LibreChat server packages for installer-managed runtime tasks..."
    npm run build:data-provider || return 1
    npm run build:data-schemas || return 1
    npm run build:api || return 1
    LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=true
  fi

  LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN=true
  return 0
}
## === VIVENTIUM END ===

should_rebuild_librechat_packages() {
  if should_rebuild_librechat_server_packages; then
    return 0
  fi

  should_rebuild_librechat_client_package
}

# A status-only check: never signal a reader or mutate a running checkout.
librechat_build_tree_idle() {
  "${PYTHON_BIN:-python3}" - "$LIBRECHAT_DIR" <<'PY_IDLE'
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
# An external dependency tree is not owned by this candidate.
for name in ("node_modules", "client/node_modules", "packages/api/node_modules",
             "packages/client/node_modules", "packages/data-provider/node_modules",
             "packages/data-schemas/node_modules", "client/dist", "packages/api/dist",
             "packages/client/dist", "packages/data-provider/dist", "packages/data-schemas/dist"):
    path = root / name
    if path.is_symlink() and not path.resolve().is_relative_to(root):
        raise SystemExit("Candidate dependencies refer to another checkout; preparation stopped.")
try:
    result = subprocess.run(["lsof", "-nP", "-d", "cwd", "-Fpcn"],
                            capture_output=True, text=True, timeout=10)
except (OSError, subprocess.TimeoutExpired):
    raise SystemExit("Could not verify that the candidate build tree is idle.")
if result.returncode != 0 or not result.stdout.strip():
    raise SystemExit("Could not verify that the candidate build tree is idle.")
# Use lsof's process identity; macOS truncates ps's comm column even with -ww.
node_pids = set()
pid = ""
command = ""
for line in result.stdout.splitlines():
    if line.startswith("p"):
        pid, command = line[1:], ""
    elif line.startswith("c"):
        command = line[1:]
        if command in {"node", "nodejs", "npm", "corepack"}:
            node_pids.add(pid)
    elif line.startswith("n") and pid in node_pids:
        cwd = Path(line[1:])
        if cwd == root or root in cwd.parents:
            raise SystemExit("Candidate LibreChat is in use; prepare an inactive checkout before activation.")
# Also catch an absolute candidate entrypoint launched from another working directory.
try:
    processes = subprocess.run(["ps", "-Aww", "-o", "pid=", "-o", "args="],
                               capture_output=True, text=True, timeout=10)
except (OSError, subprocess.TimeoutExpired):
    raise SystemExit("Could not verify candidate process commands.")
if processes.returncode != 0:
    raise SystemExit("Could not verify candidate process commands.")
for line in processes.stdout.splitlines():
    parts = line.strip().split(None, 1)
    if len(parts) == 2 and parts[0] in node_pids and str(root) + "/" in parts[1]:
        raise SystemExit("Candidate LibreChat is in use; prepare an inactive checkout before activation.")

PY_IDLE
}

should_rebuild_librechat_client_bundle() {
  if [[ "${VIVENTIUM_FORCE_PACKAGE_REBUILD:-0}" == "1" ]] ||
    [[ ! -f "$LIBRECHAT_DIR/client/dist/index.html" ]] ||
    [[ ! -f "$LIBRECHAT_DIR/client/dist/sandpack-bundler/index.html" ]] ||
    ! grep -Fq 'IS_ONPREM:"true"' "$LIBRECHAT_DIR/client/dist/sandpack-bundler/index.html" 2>/dev/null; then
    return 0
  fi

  # An existing bundle can predate its UI or shared browser package inputs.
  # Reuse the same freshness check as the package builds before daily cutover.
  find_librechat_source_newer_than_dist \
    "$LIBRECHAT_DIR/client/dist/index.html" \
    "$LIBRECHAT_DIR/package-lock.json" \
    "$LIBRECHAT_DIR/package.json" \
    "$LIBRECHAT_DIR/client/src" \
    "$LIBRECHAT_DIR/client/public" \
    "$LIBRECHAT_DIR/client/scripts" \
    "$LIBRECHAT_DIR/client/index.html" \
    "$LIBRECHAT_DIR/client/package.json" \
    "$LIBRECHAT_DIR/client/vite.config.ts" \
    "$LIBRECHAT_DIR/client/tsconfig.json" \
    "$LIBRECHAT_DIR/client/tailwind.config.cjs" \
    "$LIBRECHAT_DIR/client/postcss.config.cjs" \
    "$LIBRECHAT_DIR/packages/client/src" \
    "$LIBRECHAT_DIR/packages/client/dist" \
    "$LIBRECHAT_DIR/packages/client/package.json" \
    "$LIBRECHAT_DIR/packages/data-provider/src" \
    "$LIBRECHAT_DIR/packages/data-provider/react-query" \
    "$LIBRECHAT_DIR/packages/data-provider/dist" \
    "$LIBRECHAT_DIR/packages/data-provider/package.json" \
    >/dev/null
}

prepare_librechat_build_outputs() {
  ensure_librechat_server_packages_ready || return 1
  local build_bundle=false
  if should_rebuild_librechat_client_bundle; then build_bundle=true; fi
  if should_rebuild_librechat_client_package || [[ "$build_bundle" == true ]]; then
    echo "[viventium] Building LibreChat client package..."
    npm run build:client-package || return 1
    LIBRECHAT_PACKAGES_REBUILT_THIS_RUN=true
  fi
  if [[ "$build_bundle" == true ]]; then
    echo "[viventium] Building LibreChat client bundle..."
    (
      local build_node_options=""
      build_node_options="$(librechat_client_build_node_options)"
      if [[ -n "$build_node_options" ]]; then
        export NODE_OPTIONS="${build_node_options}${NODE_OPTIONS:+ ${NODE_OPTIONS}}"
      fi
      cd client || exit 1
      npm run build
    ) || return 1
    LIBRECHAT_CLIENT_BUNDLE_BUILT_THIS_RUN=true
  fi
  # Direct and partial starts share this prerequisite with the wrapper start.
  node "$LIBRECHAT_DIR/client/scripts/prepare-local-sandpack-bundler.cjs" || return 1
}

prepare_librechat_candidate() (
  : "${RED:=}" "${YELLOW:=}" "${NC:=}"
  configure_librechat_build_runtime
  ensure_validated_node24_runtime || return 1
  cd "$LIBRECHAT_DIR" || return 1
  local deps_reason=""
  deps_reason="$(librechat_dependency_install_reason)" || return 1
  if [[ -n "$deps_reason" ]] || should_rebuild_librechat_packages || should_rebuild_librechat_client_bundle; then
    librechat_build_tree_idle || return 1
  fi
  ensure_librechat_node_dependencies || return 1
  prepare_librechat_build_outputs
)
