from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'scripts/viventium/librechat_build.sh'
CLI = ROOT / 'bin/viventium'


def run_shell(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['bash', '-c', 'set -euo pipefail\n' + body],
        cwd=tmp_path, text=True, capture_output=True, timeout=20,
    )


def source_build() -> str:
    return f'source {shlex.quote(str(BUILD))}\n'


def activation_preparation_guard() -> str:
    source = CLI.read_text()
    start = source.index('      if ! prepare_dev_runtime_librechat_candidate; then')
    end = source.index('      if ! "$REPO_ROOT/scripts/viventium/doctor.sh"', start)
    return source[start:end]


@pytest.mark.parametrize('failed', [False, True])
def test_candidate_build_finishes_before_cutover_and_failure_keeps_daily_running(tmp_path: Path, failed: bool) -> None:
    # Exercise the actual activation guard and shared preparation owner; npm is the boundary.
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    (candidate / 'client').mkdir()
    daily = tmp_path / 'daily-running'
    daily.write_text('running')
    log = tmp_path / 'events'
    setup = source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(candidate))}
log={shlex.quote(str(log))}
daily={shlex.quote(str(daily))}
configure_librechat_build_runtime() {{ :; }}
ensure_validated_node24_runtime() {{ :; }}
node() {{ [[ "$1" == "$LIBRECHAT_DIR/client/scripts/prepare-local-sandpack-bundler.cjs" ]] && [[ -f "$daily" ]]; }}
librechat_dependency_install_reason() {{ printf '%s\\n' missing; }}
librechat_build_tree_idle() {{ :; }}
ensure_librechat_node_dependencies() {{ [[ -f "$daily" ]] && echo dependencies >> "$log"; }}
npm() {{
  [[ -f "$daily" ]] || return 92
  echo "$*" >> "$log"
  if [[ "$*" == 'run build:api' && {'true' if failed else 'false'} == true ]]; then return 23; fi
}}
prepare_dev_runtime_librechat_candidate() {{ prepare_librechat_candidate; }}
rollback_prepared_dev_runtime_activation() {{ echo rollback >> "$log"; }}
activation() {{
  local activation_dir=prepared
{activation_preparation_guard()}
  echo stop >> "$log"
  rm "$daily"
}}
activation
'''
    result = run_shell(tmp_path, setup)
    events = log.read_text().splitlines()
    assert events[:4] == ['dependencies', 'run build:data-provider', 'run build:data-schemas', 'run build:api']
    if failed:
        assert result.returncode != 0
        assert events[-1] == 'rollback'
        assert 'stop' not in events
        assert daily.read_text() == 'running'
    else:
        assert result.returncode == 0, result.stderr
        assert events[-3:] == ['run build:client-package', 'run build', 'stop']
        assert not daily.exists()


def test_failed_server_build_does_not_mark_packages_prepared_when_called_from_a_guard(tmp_path: Path) -> None:
    result = run_shell(tmp_path, source_build() + '''
should_rebuild_librechat_server_packages() { return 0; }
npm() { return 23; }
if ensure_librechat_server_packages_ready; then exit 90; fi
[[ "$LIBRECHAT_SERVER_PACKAGES_PREPARED_THIS_RUN" == false ]]
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('outside_cwd', [False, True])
def test_candidate_preparation_rejects_a_real_node_reader_without_stopping_it(tmp_path: Path, outside_cwd: bool) -> None:
    node = shutil.which('node')
    if not node or not shutil.which('lsof'):
        pytest.skip('Node and lsof are needed for the real process ownership check')
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    script = candidate / 'reader.js'
    script.write_text("process.stdout.write('ready\\n'); setInterval(() => {}, 1000);\n")
    worker = subprocess.Popen([node, str(script)], cwd=tmp_path if outside_cwd else candidate,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert worker.stdout is not None and worker.stdout.readline().strip() == 'ready'
        result = run_shell(tmp_path, source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(candidate))}
PYTHON_BIN={shlex.quote(sys.executable)}
librechat_build_tree_idle
''')
        assert result.returncode != 0
        assert 'in use' in result.stderr
        assert worker.poll() is None
    finally:
        worker.terminate()
        worker.wait(timeout=5)


def test_candidate_preparation_rejects_an_external_dependency_tree(tmp_path: Path) -> None:
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    external = tmp_path / 'daily-dependencies'
    external.mkdir()
    sentinel = external / 'sentinel'
    sentinel.write_text('keep')
    (candidate / 'node_modules').symlink_to(external, target_is_directory=True)
    result = run_shell(tmp_path, source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(candidate))}
PYTHON_BIN={shlex.quote(sys.executable)}
librechat_build_tree_idle
''')
    assert result.returncode != 0
    assert 'another checkout' in result.stderr
    assert sentinel.read_text() == 'keep'


def test_candidate_preserves_lockfile_freshness_instead_of_adjusting_timestamps(tmp_path: Path) -> None:
    candidate = tmp_path / 'candidate'
    (candidate / 'node_modules').mkdir(parents=True)
    installed = candidate / 'node_modules/.package-lock.json'
    installed.write_text('{}')
    lock = candidate / 'package-lock.json'
    lock.write_text('{}')
    os.utime(installed, (1_700_000_000, 1_700_000_000))
    os.utime(lock, (1_700_000_010, 1_700_000_010))
    before = (installed.stat().st_mtime_ns, lock.stat().st_mtime_ns)
    result = run_shell(candidate, source_build() + 'librechat_dependency_install_reason\n')
    assert result.returncode == 0
    assert result.stdout.strip() == 'package-lock changed'
    assert before == (installed.stat().st_mtime_ns, lock.stat().st_mtime_ns)


def test_prepared_candidate_skips_rebuild_but_rechecks_later_source_changes(tmp_path: Path) -> None:
    candidate = tmp_path / 'candidate'
    files = {
        'package-lock.json': '{}',
        'packages/api/src/example.ts': 'export const answer = 1;',
        'node_modules/.package-lock.json': '{}',
        'packages/data-provider/dist/index.js': '',
        'packages/data-schemas/dist/index.cjs': '',
        'packages/api/dist/index.js': '',
        'packages/client/dist/index.js': '',
        'client/dist/index.html': '',
        'client/dist/sandpack-bundler/index.html': 'IS_ONPREM:"true"',
    }
    for relative, text in files.items():
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        stamp = 1_700_000_000 if relative in ('package-lock.json', 'packages/api/src/example.ts') else 1_700_000_010
        os.utime(path, (stamp, stamp))
    setup = source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(candidate))}
configure_librechat_build_runtime() {{ :; }}
ensure_validated_node24_runtime() {{ :; }}
node() {{ return 0; }}
npm() {{ echo unexpected-build >&2; return 92; }}
librechat_build_tree_idle() {{ echo unexpected-write >&2; return 93; }}
prepare_librechat_candidate
prepare_librechat_candidate
'''
    result = run_shell(candidate, setup)
    assert result.returncode == 0, result.stderr
    changed = candidate / 'packages/api/src/example.ts'
    os.utime(changed, (1_700_000_020, 1_700_000_020))
    result = run_shell(candidate, setup)
    assert result.returncode != 0
    assert 'unexpected-write' in result.stderr
    assert 'unexpected-build' not in result.stderr


@pytest.mark.parametrize('changed', [
    'client/src/Chat.tsx', 'client/public/icon.svg', 'client/vite.config.ts',
    'client/scripts/post-build.cjs', 'packages/client/src/Panel.tsx',
    'packages/data-provider/src/schema.ts', 'packages/data-provider/dist/index.js',
    'package-lock.json',
])
def test_existing_client_bundle_rebuilds_after_its_input_changes(tmp_path: Path, changed: str) -> None:
    candidate = tmp_path / 'candidate'
    files = {
        changed: 'input',
        'packages/client/dist/index.js': 'client package',
        'client/dist/index.html': 'existing bundle',
        'client/dist/sandpack-bundler/index.html': 'IS_ONPREM:"true"',
    }
    for relative, content in files.items():
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        stamp = 1_700_000_000 if relative == changed else 1_700_000_010
        os.utime(path, (stamp, stamp))
    check = source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(candidate))}
if should_rebuild_librechat_client_bundle; then echo rebuild; else echo current; fi
'''
    result = run_shell(candidate, check)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'current'
    os.utime(candidate / changed, (1_700_000_020, 1_700_000_020))
    result = run_shell(candidate, check)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'rebuild'


# Installation and cleanup share candidate preparation's checkout ownership boundary.
def dependency_setup(tmp_path: Path, relative: str = 'node_modules') -> tuple[Path, Path, Path]:
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    (checkout / 'package-lock.json').write_text('{}')
    external = tmp_path / 'other-checkout'
    external.mkdir()
    sentinel = external / 'sentinel'
    sentinel.write_text('preserve')
    sentinel.chmod(0o444)
    linked = checkout / relative
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.symlink_to(external, target_is_directory=True)
    return checkout, linked, sentinel


def dependency_shell(checkout: Path, event_log: Path) -> str:
    return source_build() + f'''
LIBRECHAT_DIR={shlex.quote(str(checkout))}
PYTHON_BIN={shlex.quote(sys.executable)}
event_log={shlex.quote(str(event_log))}
RED= YELLOW= NC=
ensure_validated_node24_runtime() {{ :; }}
librechat_dependency_install_reason() {{ printf '%s\\n' missing; }}
node() {{ return 0; }}
cd "$LIBRECHAT_DIR"
'''


def sentinel_snapshot(sentinel: Path) -> tuple[bytes, int, int]:
    st = sentinel.stat()
    return sentinel.read_bytes(), st.st_mode, st.st_mtime_ns


@pytest.mark.parametrize('relative', ['node_modules', 'packages/data-provider/node_modules'])
@pytest.mark.parametrize('entrypoint', ['run_librechat_dependency_install', 'ensure_librechat_node_dependencies'])
def test_dependency_install_rejects_shared_paths_before_npm_mutates_them(
    tmp_path: Path, relative: str, entrypoint: str,
) -> None:
    checkout, linked, sentinel = dependency_setup(tmp_path, relative)
    before = sentinel_snapshot(sentinel)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + f'''
run_librechat_npm() {{
  echo "npm $*" >> "$event_log"
  printf mutated > {shlex.quote(str(linked / 'sentinel'))}
}}
{entrypoint}
''')
    assert result.returncode != 0
    assert 'another checkout' in result.stderr
    assert not events.exists()
    assert linked.is_symlink()
    assert sentinel_snapshot(sentinel) == before


@pytest.mark.parametrize('relative', ['node_modules', 'packages/data-provider/node_modules'])
def test_dependency_cleanup_rejects_shared_paths_before_chmod_or_unlink(
    tmp_path: Path, relative: str,
) -> None:
    checkout, linked, sentinel = dependency_setup(tmp_path, relative)
    before = sentinel_snapshot(sentinel)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
chmod() { echo chmod >> "$event_log"; }
clean_librechat_dependency_tree
''')
    assert result.returncode != 0
    assert 'another checkout' in result.stderr
    assert not events.exists()
    assert linked.is_symlink()
    assert sentinel_snapshot(sentinel) == before


@pytest.mark.parametrize('entrypoint', ['run_librechat_dependency_install', 'clean_librechat_dependency_tree'])
def test_dependency_mutation_rejects_dangling_external_links(tmp_path: Path, entrypoint: str) -> None:
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    linked = checkout / 'node_modules'
    linked.symlink_to(tmp_path / 'missing-other-checkout', target_is_directory=True)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + f'''
run_librechat_npm() {{ echo npm >> "$event_log"; }}
chmod() {{ echo chmod >> "$event_log"; }}
{entrypoint}
''')
    assert result.returncode != 0
    assert not events.exists()
    assert linked.is_symlink()


@pytest.mark.parametrize('locked', [False, True])
def test_dependency_install_preserves_normal_owned_tree_and_locked_command(tmp_path: Path, locked: bool) -> None:
    checkout = tmp_path / 'checkout'
    (checkout / 'node_modules').mkdir(parents=True)
    if locked:
        (checkout / 'package-lock.json').write_text('{}')
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
run_librechat_npm() { printf '%s\\n' "$*" >> "$event_log"; }
run_librechat_dependency_install
''')
    assert result.returncode == 0, result.stderr
    assert events.read_text().splitlines() == ['ci' if locked else 'install']


def test_dependency_install_allows_internal_workspace_link(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    (checkout / 'owned-dependencies').mkdir(parents=True)
    (checkout / 'node_modules').symlink_to('owned-dependencies', target_is_directory=True)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
run_librechat_npm() { echo npm >> "$event_log"; }
run_librechat_dependency_install
''')
    assert result.returncode == 0, result.stderr
    assert events.read_text().splitlines() == ['npm']


def test_failed_install_retry_rechecks_ownership_before_cleanup(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    (checkout / 'node_modules').mkdir(parents=True)
    external = tmp_path / 'other-checkout'
    external.mkdir()
    sentinel = external / 'sentinel'
    sentinel.write_text('preserve')
    before = sentinel_snapshot(sentinel)
    linked = checkout / 'packages/data-provider/node_modules'
    linked.parent.mkdir(parents=True)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + f'''
calls=0
run_librechat_npm() {{
  calls=$((calls + 1))
  echo "npm $calls" >> "$event_log"
  if [[ "$calls" == 1 ]]; then
    ln -s {shlex.quote(str(external))} {shlex.quote(str(linked))}
    return 23
  fi
}}
chmod() {{ echo chmod >> "$event_log"; }}
ensure_librechat_node_dependencies
''')
    assert result.returncode != 0
    assert events.read_text().splitlines() == ['npm 1']
    assert linked.is_symlink()
    assert sentinel_snapshot(sentinel) == before


def test_failed_owned_install_keeps_existing_single_cleanup_retry(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    (checkout / 'node_modules').mkdir(parents=True)
    (checkout / 'package-lock.json').write_text('{}')
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
calls=0
run_librechat_npm() {
  calls=$((calls + 1))
  echo "npm $calls $*" >> "$event_log"
  if [[ "$calls" == 1 ]]; then return 23; fi
  mkdir node_modules
}
ensure_librechat_node_dependencies
''')
    assert result.returncode == 0, result.stderr
    assert events.read_text().splitlines() == ['npm 1 ci', 'npm 2 ci']
    assert (checkout / 'node_modules').is_dir()


def test_dependency_install_rejects_shared_ancestor_directory(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    (checkout / 'packages').mkdir(parents=True)
    external = tmp_path / 'other-checkout'
    (external / 'node_modules').mkdir(parents=True)
    (checkout / 'packages/data-provider').symlink_to(external, target_is_directory=True)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
run_librechat_npm() { echo npm >> "$event_log"; }
run_librechat_dependency_install
''')
    assert result.returncode != 0
    assert not events.exists()


def test_dependency_install_reuses_existing_external_artifact_ownership_boundary(tmp_path: Path) -> None:
    checkout, linked, sentinel = dependency_setup(tmp_path, 'packages/api/dist')
    before = sentinel_snapshot(sentinel)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
run_librechat_npm() { echo npm >> "$event_log"; }
run_librechat_dependency_install
''')
    assert result.returncode != 0
    assert not events.exists()
    assert linked.is_symlink()
    assert sentinel_snapshot(sentinel) == before


def test_read_only_dependency_check_does_not_reject_sharing_without_a_mutation(tmp_path: Path) -> None:
    checkout, linked, sentinel = dependency_setup(tmp_path)
    before = sentinel_snapshot(sentinel)
    events = tmp_path / 'events'
    result = run_shell(tmp_path, dependency_shell(checkout, events) + '''
librechat_dependency_install_reason() { :; }
run_librechat_npm() { echo npm >> "$event_log"; }
ensure_librechat_node_dependencies
''')
    assert result.returncode == 0, result.stderr
    assert not events.exists()
    assert linked.is_symlink()
    assert sentinel_snapshot(sentinel) == before
