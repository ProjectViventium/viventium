import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]


def test_native_cli_runs_the_same_life_owner_and_keeps_source_folders_unread(tmp_path):
    release=tmp_path/'release';support=tmp_path/'support';life=tmp_path/'Life';source=tmp_path/'Source'
    for folder in [release/'bin',release/'runtime/python/bin',release/'runtime/scripts',support,life,source]:folder.mkdir(parents=True)
    shutil.copy2(REPO/'scripts/viventium/native_cli.sh',release/'bin/viventium')
    for name in ['life_setup.py','config_settings.py','life_bootstrap.py']:
        shutil.copy2(REPO/'scripts/viventium'/name,release/'runtime/scripts'/name)
    shutil.copytree(REPO/'templates/life-v0.01',release/'templates/life-v0.01')
    python=release/'runtime/python/bin/python3';python.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' "$@"\n');python.chmod(0o755)
    config=support/'config.yaml';config.write_text(json.dumps({'integrations':{'glasshive':{'provider':{'life_dir':str(life),'life_enabled':False}}}}));config.chmod(0o600)
    env={**os.environ,'VIVENTIUM_APP_SUPPORT_DIR':str(support)}
    for action in [['enable'],['intent','--stdin-json'],['status'],['intent','--clear'],['disable']]:
        completed=subprocess.run(['/bin/sh',str(release/'bin/viventium'),'life',*action,'--json'],
            input=json.dumps({'text':'Synthetic intent','folders':[str(source)]}) if '--stdin-json' in action else None,env=env,capture_output=True,text=True)
        assert completed.returncode==0,completed.stderr
        payload=json.loads(completed.stdout);assert payload['connector']=='none'
        assert str(source) not in completed.stdout
    assert payload['enabled'] is False and payload['intent_recorded'] is False
    assert (life/'AGENTS.md').is_file()
    assert not list(source.iterdir())


def test_helper_artifact_hash_covers_separate_life_view(tmp_path):
    spec=importlib.util.spec_from_file_location('helper_verify',REPO/'scripts/viventium/helper_artifact_verify.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for relative in module.SOURCE_FILES:
        file=tmp_path/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('source')
    before=module.helper_source_hash(tmp_path)
    view=tmp_path/'Sources/ViventiumHelper/LifeSetup.swift';assert view.is_file()
    view.write_text('changed LIFE behavior')
    assert module.helper_source_hash(tmp_path)!=before
