from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'scripts/viventium/native_runtime.py'
LAUNCHER = ROOT / 'viventium_v0_4/viventium-librechat-start.sh'
VALUES = {'JWT_SECRET': '1' * 64, 'JWT_REFRESH_SECRET': '2' * 64,
          'CREDS_KEY': '3' * 64, 'CREDS_IV': '4' * 32}


def runtime_module():
    spec = importlib.util.spec_from_file_location('instance_secret_runtime', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_env(path, values=VALUES):
    path.write_text(''.join(f'{k}={v}\n' for k, v in values.items()) +
                    'UNRELATED_OWNER_SETTING=preserve\n')
    path.chmod(0o600)
    return path


def shell_function(text, name):
    start = text.index(f'{name}() {{')
    end = text.index('\n}\n', start) + 3
    return text[start:end].replace('${BASH_SOURCE[0]}', str(LAUNCHER)) + '\n'


def run_tool(support, *args):
    return subprocess.run([sys.executable, str(TOOL), 'source-secrets',
                           '--app-support-dir', str(support), *map(str, args)],
                          capture_output=True, text=True)


def test_quiesced_checkout_uses_same_instance_secrets(tmp_path):
    support = tmp_path / 'support'
    state = support / 'state'
    state.mkdir(parents=True)
    secrets = state / 'native-secrets.json'
    secrets.write_text(json.dumps(VALUES))
    secrets.chmod(0o600)
    checkout = private_env(tmp_path / 'checkout.env', {k: 'f' * len(v) for k, v in VALUES.items()})
    original = checkout.read_bytes()
    script = LAUNCHER.read_text()
    names = ['read_env_kv', 'is_librechat_default_secret',
             'prepare_librechat_env_for_quiesced_validation']
    if 'load_librechat_instance_secrets() {' in script:
        names.insert(0, 'load_librechat_instance_secrets')
    definitions = ''.join(shell_function(script, name) for name in names)
    completed = subprocess.run(['bash', '-c', 'set -euo pipefail\n' + definitions +
        'generate_hex_secret() { return 90; }\nlog_error() { echo "$*" >&2; }\n' +
        'prepare_librechat_env_for_quiesced_validation\n' +
        '[[ "$CREDS_KEY" == "' + VALUES['CREDS_KEY'] + '" ]]\n' +
        '[[ "$JWT_REFRESH_SECRET" == "' + VALUES['JWT_REFRESH_SECRET'] + '" ]]\n'],
        env={**os.environ, 'LIBRECHAT_RUNTIME_ENV_FILE': str(checkout),
             'VIVENTIUM_APP_SUPPORT_ROOT': str(support), 'VIVENTIUM_CORE_DIR': str(ROOT),
             'PYTHON_BIN': sys.executable}, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert checkout.read_bytes() == original


def test_explicit_adoption_is_private_exact_and_idempotent(tmp_path):
    support = tmp_path / 'support'
    legacy = private_env(tmp_path / 'legacy.env')
    original = legacy.read_bytes()
    for _ in range(2):
        result = run_tool(support, '--adopt-env', legacy)
        assert result.returncode == 0, result.stderr
        assert all(value not in result.stdout + result.stderr for value in VALUES.values())
    saved = support / 'state/native-secrets.json'
    assert json.loads(saved.read_text()) == VALUES
    assert saved.stat().st_mode & 0o777 == 0o600
    assert legacy.read_bytes() == original
    changed = private_env(tmp_path / 'changed.env', {**VALUES, 'CREDS_KEY': 'a' * 64})
    assert run_tool(support, '--adopt-env', changed).returncode != 0
    assert json.loads(saved.read_text()) == VALUES


@pytest.mark.parametrize('failure', ['missing', 'malformed', 'duplicate', 'symlink', 'public'])
def test_adoption_rejects_unsafe_or_incomplete_source(tmp_path, failure):
    support = tmp_path / 'support'
    legacy = private_env(tmp_path / 'legacy.env')
    if failure == 'missing': legacy.write_text('CREDS_KEY=' + VALUES['CREDS_KEY'] + '\n')
    elif failure == 'malformed': legacy.write_text(legacy.read_text().replace(VALUES['CREDS_IV'], 'invalid'))
    elif failure == 'duplicate': legacy.write_text(legacy.read_text() + 'CREDS_KEY=' + VALUES['CREDS_KEY'] + '\n')
    elif failure == 'symlink':
        link = tmp_path / 'link.env'
        link.symlink_to(legacy)
        legacy = link
    else: legacy.chmod(0o644)
    result = run_tool(support, '--adopt-env', legacy)
    assert result.returncode != 0
    assert not (support / 'state/native-secrets.json').exists()
    assert all(value not in result.stdout + result.stderr for value in VALUES.values())


def test_missing_owner_never_generates_on_read_or_existing_instance_init(tmp_path):
    support = tmp_path / 'support'
    support.mkdir()
    sentinel = support / 'config.yaml'
    sentinel.write_text('synthetic existing instance\n')
    for option in ['--export', '--initialize']:
        result = run_tool(support, option)
        assert result.returncode != 0
        assert not (support / 'state/native-secrets.json').exists()
    assert sentinel.read_text() == 'synthetic existing instance\n'


def test_fresh_initialization_is_stable_and_separate_by_instance(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    assert run_tool(first, '--initialize').returncode == 0
    one = (first / 'state/native-secrets.json').read_bytes()
    assert run_tool(first, '--initialize').returncode == 0
    assert (first / 'state/native-secrets.json').read_bytes() == one
    assert run_tool(second, '--initialize').returncode == 0
    assert (second / 'state/native-secrets.json').read_bytes() != one


def test_adoption_does_not_execute_unrelated_dotenv_content(tmp_path):
    support = tmp_path / 'support'
    legacy = private_env(tmp_path / 'legacy.env')
    sentinel = tmp_path / 'must-not-exist'
    legacy.write_text(legacy.read_text() + f'UNRELATED=$(touch {sentinel})\n')
    result = run_tool(support, '--adopt-env', legacy)
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    assert json.loads((support / 'state/native-secrets.json').read_text()) == VALUES


def test_concurrent_different_adoptions_do_not_replace_winner(tmp_path):
    support = tmp_path / 'support'
    runtime_module().ensure_support_directories(support, 'state')
    sources = [private_env(tmp_path / 'one.env'),
               private_env(tmp_path / 'two.env', {**VALUES, 'CREDS_KEY': 'b' * 64})]
    processes = [subprocess.Popen([sys.executable, str(TOOL), 'source-secrets',
                  '--app-support-dir', str(support), '--adopt-env', str(source)],
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for source in sources]
    outputs = [p.communicate(timeout=10) for p in processes]
    assert sorted(p.returncode for p in processes) == [0, 1]
    winning = sources[next(i for i, p in enumerate(processes) if p.returncode == 0)]
    saved = json.loads((support / 'state/native-secrets.json').read_text())
    assert all(f'{key}={value}\n' in winning.read_text() for key, value in saved.items())
    assert all(value not in str(outputs) for value in saved.values())


def test_existing_database_without_config_is_not_a_fresh_instance(tmp_path):
    support = tmp_path / 'support'
    database = support / 'state/mongo-data'
    database.mkdir(parents=True)
    sentinel = database / 'WiredTiger'
    sentinel.write_bytes(b'synthetic durable database')
    assert run_tool(support, '--initialize').returncode != 0
    assert sentinel.read_bytes() == b'synthetic durable database'
    assert not (support / 'state/native-secrets.json').exists()


@pytest.mark.parametrize('existing_database', [False, True])
def test_actual_install_preamble_initializes_before_python_bootstrap(tmp_path, existing_database):
    source = (ROOT / 'bin/viventium').read_text()
    # Execute the actual install preamble and stop at the dependency bootstrap boundary.
    preamble = source.split('SKIP_PYTHON_BOOTSTRAP=0\n', 1)[0]
    preamble = preamble.replace('SCRIPT_SOURCE="$(resolve_script_source)"',
                                f'SCRIPT_SOURCE="{ROOT / "bin/viventium"}"', 1)
    script = tmp_path / 'install-preamble.sh'
    script.write_text(preamble + '\nprintf "reached-bootstrap-boundary\\n"\n')
    support = tmp_path / 'support'
    if existing_database:
        database = support / 'state/mongo-data'
        database.mkdir(parents=True)
        (database / 'WiredTiger').write_bytes(b'synthetic existing data')
    result = subprocess.run(['bash', str(script), '--app-support-dir', str(support),
                             'install', '--no-start'],
                            env={**os.environ, 'VIVENTIUM_PYTHON_BIN': sys.executable},
                            capture_output=True, text=True)
    if existing_database:
        assert result.returncode != 0
        assert 'reached-bootstrap-boundary' not in result.stdout
        assert not (support / 'state/native-secrets.json').exists()
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == 'reached-bootstrap-boundary'
        assert (support / 'state/native-secrets.json').exists()
        assert not (support / 'state/bootstrap-python').exists()
        assert not (support / 'state/cli-operation.lock').exists()
