from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT
    / "qa"
    / "glasshive_host_workers"
    / "scripts"
    / "codex_app_server_instruction_probe.py"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("codex_app_server_instruction_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_server_probe_is_opt_in_and_never_changes_production_transport(
    monkeypatch, capsys
) -> None:
    probe = _load_probe()
    monkeypatch.delenv("WPR_CODEX_APP_SERVER_QA_ENABLED", raising=False)

    result = probe.main([])
    payload = json.loads(capsys.readouterr().out)

    assert result == 2
    assert payload == {
        "error": "app_server_qa_disabled",
        "production_transport_changed": False,
    }


def test_app_server_probe_requires_current_developer_instructions_and_terminal_events() -> None:
    source = PROBE_PATH.read_text()

    assert '"collaborationMode"' in source
    assert '"developer_instructions"' in source
    assert '"thread/inject_items"' not in source
    assert "QUIET-MARKER" in source
    assert "JOY-MARKER" in source
    assert "instructions_current and lifecycle_complete" in source
    assert '"production_transport_changed": False' in source


def test_app_server_probe_passes_only_when_two_developer_updates_win_on_one_thread(
    tmp_path,
) -> None:
    probe = _load_probe()
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "marker = ''\n"
        "turn = 0\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if 'id' not in request:\n"
        "        continue\n"
        "    method = request.get('method')\n"
        "    request_id = request['id']\n"
        "    if method == 'thread/start':\n"
        "        result = {'thread': {'id': 'thread-one'}}\n"
        "    elif method == 'turn/start':\n"
        "        text = request['params']['collaborationMode']['settings']['developer_instructions']\n"
        "        marker = 'JOY-MARKER' if 'JOY-MARKER' in text else 'QUIET-MARKER'\n"
        "        turn += 1\n"
        "        turn_id = f'turn-{turn}'\n"
        "        result = {'turn': {'id': turn_id}}\n"
        "    else:\n"
        "        result = {}\n"
        "    print(json.dumps({'id': request_id, 'result': result}), flush=True)\n"
        "    if method == 'turn/start':\n"
        "        print(json.dumps({'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'text': marker}}}), flush=True)\n"
        "        print(json.dumps({'method': 'turn/completed', 'params': {'turn': {'id': turn_id}}}), flush=True)\n"
    )
    fake_codex.chmod(0o755)
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    cwd = tmp_path / "workspace"
    cwd.mkdir()

    result = probe.run_probe(
        codex_bin=str(fake_codex),
        source_codex_home=source_home,
        cwd=cwd,
        model="synthetic-model",
        personality="none",
        timeout_s=10,
    )

    assert result["eligible_for_production_review"] is True
    assert result["developer_instructions_current"] is True
    assert result["turn_completed_events"] == [True, True]
    assert result["same_thread"] is True
    assert result["production_transport_changed"] is False
