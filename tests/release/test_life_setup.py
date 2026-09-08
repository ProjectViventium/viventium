import json
import os
import subprocess
import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / 'scripts/viventium/life_setup.py'


def fixture(tmp_path):
    root = tmp_path / 'Life'; root.mkdir()
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump({'integrations': {'glasshive': {'provider': {'life_dir': str(root), 'life_enabled': False}}}}))
    config.chmod(0o600)
    return config, tmp_path / 'state', root


def run(config, state, *args, data=None):
    return subprocess.run([sys.executable, str(TOOL), '--config-file', str(config), '--state-dir', str(state), *args, '--json'],
        input=json.dumps(data) if data is not None else None, capture_output=True, text=True)


def ok(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_actual_choose_skip_reopen_clear_disable_and_preserve_manual_notes(tmp_path):
    config, state, root = fixture(tmp_path)
    sources = root / 'Sources'; sources.mkdir()
    doc = sources / 'WHAT_TO_CONNECT.md'
    manual = 'My own note stays byte-exact.\n\n'; doc.write_text(manual)
    chosen = tmp_path / 'Research'; chosen.mkdir()
    (chosen / 'private.txt').write_text('not imported')
    before = (chosen / 'private.txt').stat()
    assert ok(run(config,state,'status'))['enabled'] is False
    assert ok(run(config,state,'enable'))['enabled'] is True
    text = '  My research, when I decide.\nKeep my exact wording.  '
    result = ok(run(config,state,'intent','--stdin-json',data={'text':text,'folders':[str(chosen)]}))
    assert result['intent']['text'] == text
    assert result['intent']['folder_count'] == 1
    assert str(chosen) not in json.dumps(result)
    assert doc.read_text().startswith(manual)
    assert not (state/'life/intent.json').exists()
    reopened = ok(run(config,state,'status','--show-path'))
    assert reopened['intent']['folders'] == [str(chosen)]
    assert reopened['intent']['text'] == text
    cleared = ok(run(config,state,'intent','--clear'))
    assert cleared['enabled'] is True and not cleared['intent_recorded']
    assert doc.read_text() == manual
    ok(run(config,state,'intent','--text','Another intention'))
    disabled = ok(run(config,state,'disable'))
    assert not disabled['enabled'] and not disabled['intent_recorded']
    assert disabled['folder_configured'] is True
    assert doc.read_text() == manual
    assert yaml.safe_load(config.read_text())['integrations']['glasshive']['provider']['life_dir'] == str(root)
    assert config.stat().st_mode & 0o777 == 0o600
    assert doc.stat().st_mode & 0o777 == 0o600
    assert (chosen/'private.txt').stat().st_mtime_ns == before.st_mtime_ns


def test_unavailable_symlink_and_relative_folder_leave_config_unchanged(tmp_path):
    config,state,root = fixture(tmp_path); original=config.read_bytes()
    link=tmp_path/'alias'; link.symlink_to(root,target_is_directory=True)
    for raw in [str(tmp_path/'missing'),str(link),'relative']:
        result=run(config,state,'enable','--stdin-json',data={'folder':raw})
        assert result.returncode == 1 and raw not in result.stderr
        assert config.read_bytes() == original


def test_legacy_intent_migrates_only_on_owner_mutation(tmp_path):
    config,state,root=fixture(tmp_path)
    old=state/'life/intent.json'; old.parent.mkdir(parents=True)
    old.write_text(json.dumps({'version':1,'text':'Old words','recorded_at':'2026-01-01'})); old.chmod(0o600)
    assert ok(run(config,state,'status'))['intent']['text']=='Old words'
    assert old.exists() and not (root/'Sources').exists()
    ok(run(config,state,'intent','--text','New words'))
    assert not old.exists()
    assert 'New words' in (root/'Sources/WHAT_TO_CONNECT.md').read_text()


def test_tampered_managed_block_and_linked_document_are_not_overwritten(tmp_path):
    config,state,root=fixture(tmp_path); sources=root/'Sources'; sources.mkdir()
    doc=sources/'WHAT_TO_CONNECT.md'; doc.write_text('<!-- VIVENTIUM CONNECT INTENT START -->\nbroken')
    before=doc.read_bytes()
    assert run(config,state,'intent','--text','new').returncode==1
    assert doc.read_bytes()==before
    doc.unlink(); target=tmp_path/'outside'; target.write_text('untouched'); doc.symlink_to(target)
    assert run(config,state,'intent','--text','new').returncode==1
    assert target.read_text()=='untouched'


def test_empty_intent_requires_clear_and_duplicate_choices_are_idempotent(tmp_path):
    config,state,root=fixture(tmp_path)
    assert run(config,state,'intent','--stdin-json',data={'text':'','folders':[]}).returncode==1
    data=ok(run(config,state,'intent','--stdin-json',data={'text':'','folders':[str(root),str(root)]}))
    assert data['intent']['folder_count']==1
    assert ok(run(config,state,'intent','--clear'))['changed'] is True
    assert ok(run(config,state,'intent','--clear'))['changed'] is False


def test_selected_sources_are_metadata_only_and_not_runtime_grants(tmp_path, monkeypatch):
    import importlib.util
    import io
    sys.path.insert(0,str(REPO/'scripts/viventium'))
    spec=importlib.util.spec_from_file_location('life_source_audit',TOOL); owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    config,state,root=fixture(tmp_path)
    source=tmp_path/'Selected';source.mkdir();(source/'private.txt').write_text('must not be read')
    observed=[]
    def audit(event,args):
        if event in ('open','os.listdir','os.scandir') and args and isinstance(args[0],(str,bytes)):
            candidate=os.fsdecode(args[0])
            if candidate==str(source) or candidate.startswith(str(source)+os.sep):
                observed.append((event,candidate));raise AssertionError('Source content access')
    sys.addaudithook(audit)
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'text':'Read later','folders':[str(source)]})))
    args=owner.build_parser().parse_args(['--config-file',str(config),'--state-dir',str(state),'intent','--stdin-json'])
    result=owner.execute(args)
    assert result['intent']['folder_count']==1 and observed==[]
    provider=yaml.safe_load(config.read_text())['integrations']['glasshive']['provider']
    assert 'allowed_workspace_roots' not in provider


def test_failed_config_write_restores_original_intent_and_state(tmp_path, monkeypatch):
    import importlib.util
    sys.path.insert(0,str(REPO/'scripts/viventium'))
    spec=importlib.util.spec_from_file_location('life_rollback',TOOL); owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    config,state,root=fixture(tmp_path);src=root/'Sources';src.mkdir();doc=src/'WHAT_TO_CONNECT.md';doc.write_text('Keep my notes.\n')
    before=config.read_bytes();write=owner._atomic_write
    def fail_config(path,text):
        if path==config: raise OSError('synthetic full disk')
        return write(path,text)
    monkeypatch.setattr(owner,'_atomic_write',fail_config)
    args=owner.build_parser().parse_args(['--config-file',str(config),'--state-dir',str(state),'intent','--text','New intent'])
    import pytest
    with pytest.raises(OSError): owner.execute(args)
    assert config.read_bytes()==before and doc.read_text()=='Keep my notes.\n'


def test_remote_note_update_preserves_saved_folder_intent_when_disk_is_unavailable(tmp_path):
    config,state,root=fixture(tmp_path);source=tmp_path/'External';source.mkdir()
    ok(run(config,state,'intent','--stdin-json',data={'text':'First note','folders':[str(source)]}))
    source.rmdir()
    updated=ok(run(config,state,'intent','--stdin-json',data={'text':'Updated note'}))
    assert updated['intent']['folder_count']==1
    assert ok(run(config,state,'status','--show-path'))['intent']['folders']==[str(source)]


def test_helper_large_private_input_does_not_fill_a_pipe_before_launch(tmp_path):
    import shutil
    import pytest
    if sys.platform != 'darwin' or not shutil.which('swift'):
        pytest.skip('Swift/macOS helper runtime is required')
    source = (REPO / 'apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift').read_text()
    method = source.split('    private nonisolated static func runCLICaptured(', 1)[1].split(
        '    private struct UpdateCheckSummary', 1
    )[0]
    harness = tmp_path / 'input.swift'
    harness.write_text("""import Foundation
struct HelperProbe {
    static func makeCLIProcess(repoRoot: String, appSupportDir: String, arguments: [String], logFileName: String?) -> Process {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/cat")
        return process
    }
    nonisolated static func runCLICaptured(""" + method + """}
let text = String(repeating: "synthetic intent ✨\\n", count: 16384)
let result = HelperProbe.runCLICaptured(repoRoot: "", appSupportDir: "", arguments: [],
    timeoutSeconds: 3, standardInput: text, privateOutput: true)
guard result.exitStatus == 0 && result.stdout == text else { exit(1) }
print("exact private input returned")
""")
    result = subprocess.run(['swift', str(harness)], capture_output=True, text=True,
        timeout=30, env={**os.environ, 'TMPDIR': str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'exact private input returned'
    assert not list(tmp_path.glob('viventium-helper-input-*'))
    assert not list(tmp_path.glob('viventium-helper-cli-*'))
