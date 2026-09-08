"""Workbench source changes must reach the actual worker composition boundary."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.viventium.prompt_registry import build_prompt_bundle, load_prompt_registry, render_prompt

BOOTSTRAP = ROOT / "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/bootstrap.py"
PROMPTS = ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts"
PAIRS = {
    "GLASSHIVE_SAFETY_CHECKPOINT_RULE": "worker.safety_checkpoint",
    "GLASSHIVE_WORKER_COMPLETION_CONTRACT": "worker.completion_contract",
    "GLASSHIVE_NATIVE_CAPABILITY_INVENTORY": "worker.native_capability_inventory",
}
PROBE = """
import hashlib,json,sys
from workers_projects_runtime import bootstrap as b, profile_runtime as p
values = {
 'completion': b.GLASSHIVE_WORKER_COMPLETION_CONTRACT,
 'capabilities': b.GLASSHIVE_NATIVE_CAPABILITY_INVENTORY,
 'project': b.merge_glasshive_worker_instructions('Synthetic owner context.'),
 'harness': p.HOST_NATIVE_HARNESS_PROMPT,
 'agents': p.HOST_DEFAULT_AGENTS_MD,
 'run': p._instruction_with_completion_contract('Synthetic requested work.'),
}
print(json.dumps({'hashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in values.items()},
 'registeredTextReachedRun':'Changed registered completion.' in values['run'],
 'registeredTextReachedHarness':'Changed registered capabilities.' in values['harness'],
 'registeredSafetyReachedAll':all('Changed registered safety.' in values[key] for key in ['project','harness']),
 'registeredHostReachedHarness':'Changed registered host.' in values['harness'],
 'compiledLoaderImported':'compiled_prompt_contract' in sys.modules}))
"""


def probe(bundle=None, *, managed=True):
    env = {key: value for key, value in os.environ.items() if not key.startswith('VIVENTIUM_')}
    env['PYTHONPATH'] = str(BOOTSTRAP.parents[1])
    if managed:
        env['VIVENTIUM_INSTALL_MODE'] = 'express'
    if bundle is not None:
        env['VIVENTIUM_PROMPT_BUNDLE_PATH'] = str(bundle)
    return subprocess.run([sys.executable, '-c', PROBE], env=env, capture_output=True, text=True)


def write_bundle(tmp_path, data=None):
    path = tmp_path / 'prompt-bundle.json'
    path.write_text(json.dumps(data if data is not None else build_prompt_bundle(PROMPTS)))
    return path


def test_registered_initial_bodies_match_explicit_standalone_compatibility():
    registry = load_prompt_registry(PROMPTS)
    module = ast.parse(BOOTSTRAP.read_text())
    for constant, prompt_id in PAIRS.items():
        node = next(node for node in module.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == constant for target in node.targets))
        standalone = ast.literal_eval(node.value.args[1])
        registered = render_prompt(prompt_id, registry).rstrip('\n')
        registered += '\n' if standalone.endswith('\n') else ''
        assert registered == standalone


def test_managed_and_standalone_emit_identical_actual_worker_frames(tmp_path):
    standalone = probe(managed=False)
    managed = probe(write_bundle(tmp_path))
    assert standalone.returncode == managed.returncode == 0, managed.stderr
    old, new = json.loads(standalone.stdout), json.loads(managed.stdout)
    assert old['hashes'] == new['hashes']
    assert old['compiledLoaderImported'] is False
    assert new['compiledLoaderImported'] is True


def test_compiled_source_edit_reaches_actual_run_harness_and_capabilities(tmp_path):
    bundle = build_prompt_bundle(PROMPTS)
    bundle['prompts']['worker.completion_contract']['body'] = 'Changed registered completion.\n'
    bundle['prompts']['worker.native_capability_inventory']['body'] = 'Changed registered capabilities.\n'
    bundle['prompts']['worker.safety_checkpoint']['body'] = 'Changed registered safety.\n'
    bundle['prompts']['worker.host_native_harness']['body'] += '\nChanged registered host.\n'
    result = probe(write_bundle(tmp_path, bundle))
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output['registeredTextReachedRun'] and output['registeredTextReachedHarness']
    assert output['registeredSafetyReachedAll'] and output['registeredHostReachedHarness']


@pytest.mark.parametrize('failure', ['missing_path', 'missing_entry', 'invalid_bundle', 'cycle', 'unknown_variable'])
def test_managed_worker_never_restores_inline_defaults_after_required_source_failure(tmp_path, failure):
    bundle = build_prompt_bundle(PROMPTS)
    if failure == 'missing_entry':
        del bundle['prompts']['worker.completion_contract']
    elif failure == 'invalid_bundle':
        bundle = {'prompts': []}
    elif failure == 'cycle':
        bundle['prompts']['worker.completion_contract']['metadata']['includes'] = ['worker.completion_contract']
    elif failure == 'unknown_variable':
        bundle['prompts']['worker.completion_contract']['body'] = '{{unknown}}'
    path = None if failure == 'missing_path' else write_bundle(tmp_path, bundle)
    result = probe(path)
    assert result.returncode != 0
    assert not result.stdout
    assert 'prompt_bundle_unavailable' in result.stderr or 'required_prompt_invalid' in result.stderr


def test_workbench_exposes_sources_and_exact_consumer_relationships(monkeypatch):
    sys.path.insert(0, str(ROOT / "viventium_v0_4/prompt-workbench/backend"))
    from prompt_workbench import prompt_service
    monkeypatch.setattr(prompt_service, 'PROMPTS_ROOT', PROMPTS)
    monkeypatch.setattr(prompt_service, 'REPO_ROOT', ROOT)
    monkeypatch.setattr(prompt_service, 'LIBRECHAT_ROOT', ROOT / 'viventium_v0_4/LibreChat')
    monkeypatch.setattr(prompt_service, 'git_history', lambda *_args, **_kwargs: [])
    entries = {row['id']: row for row in prompt_service.list_prompts()}
    for prompt_id in [*PAIRS.values(), 'worker.host_native_harness']:
        assert entries[prompt_id]['ownerLayer'] == 'glasshive_worker'
        detail = prompt_service.get_prompt(prompt_id)
        assert detail['rendered'].strip() == detail['body'].strip()
        related = prompt_service.related_config_for_prompt(prompt_id)
        consumer = '_host_harness_prompt' if prompt_id == 'worker.host_native_harness' else '_instruction_with_completion_contract'
        assert {row['selector'] for row in related} == {'_worker_prompt', consumer}
    assert prompt_service._config_source_path('viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/auth.py') is None


@pytest.mark.parametrize('failure', ['missing_safety', 'missing_host', 'host_unknown_variable'])
def test_required_host_authority_sources_fail_closed(tmp_path, failure):
    bundle = build_prompt_bundle(PROMPTS)
    if failure == 'missing_safety':
        del bundle['prompts']['worker.safety_checkpoint']
    elif failure == 'missing_host':
        del bundle['prompts']['worker.host_native_harness']
    else:
        bundle['prompts']['worker.host_native_harness']['body'] += '{{unknown_authority}}'
    result = probe(write_bundle(tmp_path, bundle))
    assert result.returncode != 0
    assert 'required_prompt_invalid' in result.stderr


def test_host_frame_substitutes_current_source_dependencies_in_order(tmp_path):
    bundle = build_prompt_bundle(PROMPTS)
    bundle['prompts']['worker.host_native_harness']['body'] = (
        '{{critical_operating_instructions}}\n{{native_capability_inventory}}\n'
        '{{completion_contract}}\n{{safety_checkpoint}}')
    path = write_bundle(tmp_path, bundle)
    env = {key: value for key, value in os.environ.items() if not key.startswith('VIVENTIUM_')}
    env.update(PYTHONPATH=str(BOOTSTRAP.parents[1]), VIVENTIUM_INSTALL_MODE='express',
               VIVENTIUM_PROMPT_BUNDLE_PATH=str(path))
    code = "from workers_projects_runtime import bootstrap as b, profile_runtime as p; import json; print(json.dumps(p.HOST_NATIVE_HARNESS_PROMPT))"
    result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    text = json.loads(result.stdout)
    assert '{{' not in text
    assert text.index('CRITICAL OPERATING INSTRUCTIONS') < text.index('Native capability discovery')
    assert text.index('Native capability discovery') < text.index('GlassHive completion contract')
    assert text.index('GlassHive completion contract') < text.index('Safety boundary:')
