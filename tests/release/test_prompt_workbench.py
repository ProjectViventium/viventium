from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_BACKEND = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend"
if str(WORKBENCH_BACKEND) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_BACKEND))

from prompt_workbench import drafts, import_mapper, prompt_service, promptfoo_adapter, sync_engine  # noqa: E402
from prompt_workbench import evals  # noqa: E402
from prompt_workbench.paths import resolve_repo_path  # noqa: E402


PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
WORKBENCH_DIST = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "dist"
WORKBENCH_SRC = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "src"


def write_prompt(root: Path, rel: str, prompt_id: str, body: str, **metadata: object) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": prompt_id,
        "owner_layer": "test",
        "target": "test",
        "version": 1,
        "status": "active",
        "safety_class": "public_product",
        "required_context": [],
        "output_contract": "test",
        **metadata,
    }
    path.write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False).strip() + "\n---\n" + body.rstrip() + "\n",
        encoding="utf-8",
    )
    return path


def test_workbench_render_matches_existing_prompt_registry() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    expected = render_prompt("main.conscious_agent", registry)

    actual = prompt_service.render_prompt_payload("main.conscious_agent")["rendered"]

    assert actual == expected
    assert "# Identity" in actual


def test_workbench_static_index_is_fresh_and_assets_are_immutable() -> None:
    if not (WORKBENCH_DIST / "index.html").exists():
        pytest.skip("Prompt Workbench dist bundle is not built in this checkout")
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    index_response = client.get("/", headers={"If-Modified-Since": "Sat, 16 May 2026 00:00:00 GMT"})

    assert index_response.status_code == 200
    assert "no-store" in index_response.headers["cache-control"]

    match = re.search(r'(?:src|href)="(/assets/[^"]+)"', index_response.text)
    assert match, "dist index should reference at least one built asset"
    asset_response = client.get(match.group(1))

    assert asset_response.status_code == 200
    assert "immutable" in asset_response.headers["cache-control"]


def test_workbench_build_version_exposes_public_safe_bundle_hash() -> None:
    if not (WORKBENCH_DIST / "index.html").exists():
        pytest.skip("Prompt Workbench dist bundle is not built in this checkout")
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    payload = TestClient(app).get("/api/build-version").json()

    assert payload["available"] is True
    assert re.fullmatch(r"[0-9a-f]{16}", payload["indexHash"])
    assert payload["entryAssets"]
    encoded = json.dumps(payload)
    assert str(REPO_ROOT) not in encoded


def test_workbench_cors_is_limited_to_served_loopback_origins() -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:8781",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:9999",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:8781"
    assert "access-control-allow-origin" not in blocked.headers


def test_workbench_local_storage_access_goes_through_safe_wrapper() -> None:
    offenders: list[str] = []
    for path in WORKBENCH_SRC.rglob("*"):
        if path.name == "storage.ts" or path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\blocalStorage\b", text):
            offenders.append(str(path.relative_to(WORKBENCH_SRC)))

    assert offenders == []


@pytest.mark.parametrize(
    ("source_hash", "live_hash", "ledger", "expected"),
    [
        ("a", "a", {"sourceHash": "a", "liveHash": "a"}, "synced"),
        ("a", "b", {"sourceHash": "a", "liveHash": "a"}, "live-ahead"),
        ("b", "a", {"sourceHash": "a", "liveHash": "a"}, "source-ahead"),
        ("b", "c", {"sourceHash": "a", "liveHash": "a"}, "conflict"),
        ("b", "c", None, "conflict"),
    ],
)
def test_sync_state_classifier(source_hash: str, live_hash: str, ledger: dict[str, str] | None, expected: str) -> None:
    assert (
        sync_engine.classify_sync_state(
            source_hash=source_hash,
            live_hash=live_hash,
            ledger_record=ledger,
        )
        == expected
    )


def test_clean_live_edit_maps_to_one_markdown_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    private_root = tmp_path / "private"
    write_prompt(prompt_root, "main.md", "main.test", "", includes=["section.test"])
    section_path = write_prompt(prompt_root, "section.md", "section.test", "# Section\nold behavior\n")
    monkeypatch.setattr(import_mapper, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)

    draft = import_mapper.create_import_live_draft(
        prompt_id="main.test",
        live_text="# Section\nnew behavior\n",
        private_root=private_root,
    )

    assert draft["status"] == "draft"
    assert draft["mappedPromptId"] == "section.test"
    assert "new behavior" in draft["patch"]
    assert draft["targetPath"].endswith("section.md")
    assert section_path.read_text(encoding="utf-8").count("old behavior") == 1


def test_ambiguous_live_edit_requires_manual_target() -> None:
    source = "# One\nold\n\n# Two\nold\n"
    live = "# One\nnew\n\n# Two\nnew\n"
    candidate = import_mapper.derive_single_section_replacement(
        source,
        live,
        [("one", "# One\nold"), ("two", "# Two\nold")],
    )

    assert candidate is None


def test_public_prompt_safety_blocks_private_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    private_text = target.read_text(encoding="utf-8") + "\nContact user@example.com\n"

    with pytest.raises(ValueError, match="Private pattern email_address"):
        drafts.create_file_draft(
            target_path=target,
            new_text=private_text,
            kind="source-edit",
            private_root=tmp_path / "private",
        )


def test_public_safety_scan_applies_to_eval_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)

    with pytest.raises(ValueError, match="Private pattern bearer_token"):
        drafts.create_file_draft(
            target_path=prompt_bank,
            new_text='{"note": "Bearer abcdefghijklmnop"}',
            kind="eval-edit",
            private_root=tmp_path / "private",
        )


def test_eval_draft_target_is_limited_to_prompt_bank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    runner = eval_root / "run-exact-model-evals.cjs"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    runner.write_text("console.log('runner');\n", encoding="utf-8")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)

    with pytest.raises(ValueError, match="outside prompt/eval source roots"):
        drafts.create_file_draft(
            target_path=runner,
            new_text="console.log('changed');\n",
            kind="eval-edit",
            private_root=tmp_path / "private",
        )


def test_sync_status_rows_do_not_return_live_instruction_text() -> None:
    row = sync_engine._row_for_agent(
        agent_id="agent_test",
        label="Test",
        source_prompt_id="main.identity",
        source_instructions="source",
        live_instructions="live private prompt",
        live_version=1,
        records={},
    )

    assert "_liveInstructions" not in row
    assert row["liveTextAvailable"] is True
    assert sync_engine.LIVE_TEXT_CACHE["agent_test"] == "live private prompt"


def test_sync_status_does_not_return_local_absolute_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "source_agents_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(
        sync_engine,
        "load_latest_live_bundle",
        lambda: {"_artifactPath": str(tmp_path / "runs" / "viventium-agents.yaml"), "mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}},
    )
    monkeypatch.setattr(sync_engine, "_git_commit", lambda: "abc123")

    status = sync_engine.get_status(private_root=tmp_path / "private")
    encoded = json.dumps(status)

    assert "liveArtifactPath" not in status
    assert "ledgerPath" not in status
    assert str(tmp_path) not in encoded
    assert status["liveArtifactAvailable"] is True
    assert status["liveArtifactName"] == "viventium-agents.yaml"


def test_pull_live_uses_pull_action(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0}

    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)

    sync_engine.pull_live(env="local")

    assert calls == [["pull", "--env=local"]]


def test_reviewed_push_uses_stored_dry_run_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0, "parsed": {"args": args}, "stdoutTail": "timestamp changes"}

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)
    monkeypatch.setattr(sync_engine, "refresh_ledger_after_reconcile", lambda private_root=None: {"status": "updated"})
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}})

    dry_run = sync_engine.push_live_dry_run(env="local")
    reviewed = sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert reviewed["returnCode"] == 0
    assert calls[0] == ["push", "--env=local", "--prompts-only", "--dry-run"]
    assert calls[1] == ["push", "--env=local", "--prompts-only", "--compare-reviewed"]

    with pytest.raises(ValueError, match="stored dry-run"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")


def test_reviewed_push_refuses_unresolved_live_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0, "parsed": {"args": args}, "stdoutTail": "timestamp changes"}

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": []})
    dry_run = sync_engine.push_live_dry_run(env="local")
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 0, "source-ahead": 0, "live-ahead": 1, "conflict": 0}})

    with pytest.raises(ValueError, match="Live drift still needs review"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_eval_preview_blocks_pending_prompt_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=False, prompt_id="main.voice_style")


def test_live_eval_blocks_any_pending_prompt_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "identity.md", "main.identity", "Applied identity")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied identity", "Draft identity"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=True, prompt_id="main.voice_style")


def test_live_eval_runner_uses_prompt_bank_equals_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    runner = eval_root / "run-exact-model-evals.cjs"
    runner.write_text("// synthetic runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[list[str]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(max_cases=2, live=True, prompt_id="main.voice_style")

    assert result["returnCode"] == 0
    assert captured
    assert f"--prompt-bank={prompt_bank}" in captured[0]
    assert "--prompt-bank" not in captured[0]


def test_eval_preview_blocks_pending_eval_bank_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=prompt_bank,
        new_text=json.dumps({"families": [{"id": "changed", "cases": []}]}) + "\n",
        kind="eval-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=False, prompt_id="main.identity")


def test_active_draft_block_summary_is_public_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError) as raised:
        drafts.assert_no_active_blocking_drafts("Eval preview", prompt_id="main.voice_style")

    assert set(raised.value.blocking_drafts[0]) == {
        "id",
        "kind",
        "promptId",
        "targetPath",
        "status",
        "createdAt",
        "changeSummary",
    }
    encoded = json.dumps(raised.value.blocking_drafts)
    assert "newText" not in encoded
    assert "currentText" not in encoded
    assert "targetAbsolutePath" not in encoded
    assert "patch" not in encoded
    assert "idempotencyToken" not in encoded


def test_push_dry_run_blocks_pending_drafts_before_agent_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    calls: list[list[str]] = []
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0})

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Push dry-run blocked"):
        sync_engine.push_live_dry_run(env="local")

    assert calls == []


def test_reviewed_push_blocks_pending_drafts_after_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    calls: list[list[str]] = []
    private_root = tmp_path / "private"
    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": []})
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0, "parsed": {"args": args}})

    dry_run = sync_engine.push_live_dry_run(env="local")
    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Reviewed push blocked"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_reviewed_push_refuses_source_changes_since_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = [
        {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": [{"agentId": "agent", "label": "Main", "sourceHash": "old"}]},
        {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": [{"agentId": "agent", "label": "Main", "sourceHash": "new"}]},
    ]
    calls: list[list[str]] = []
    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "get_status", lambda: statuses.pop(0))
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0, "parsed": {"args": args}})

    dry_run = sync_engine.push_live_dry_run(env="local")

    with pytest.raises(ValueError, match="Source changed since the stored dry-run"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_drafts_can_be_listed_and_discarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")

    draft = drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Public text", "Public text updated"),
        kind="source-edit",
        private_root=tmp_path / "private",
    )
    listed = drafts.list_drafts(private_root=tmp_path / "private")
    discarded = drafts.discard_draft(draft["id"], private_root=tmp_path / "private")

    assert listed[0]["id"] == draft["id"]
    assert "currentText" not in listed[0]
    assert "newText" not in listed[0]
    assert listed[0]["changeSummary"]["additions"] == 1
    assert discarded["status"] == "discarded"


def test_duplicate_draft_saves_return_existing_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    new_text = target.read_text(encoding="utf-8").replace("Public text", "Public text updated")

    first = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=tmp_path / "private")
    second = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=tmp_path / "private")
    listed = drafts.list_drafts(private_root=tmp_path / "private")

    assert second["id"] == first["id"]
    assert second["duplicate"] is True
    assert len(listed) == 1


def test_apply_stale_draft_marks_already_applied_when_target_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    private_root = tmp_path / "private"
    new_text = target.read_text(encoding="utf-8").replace("Public text", "Public text updated")
    draft = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=private_root)
    target.write_text(new_text, encoding="utf-8")

    applied = drafts.apply_draft(draft["id"], draft["idempotencyToken"], private_root=private_root)

    assert applied["status"] == "applied"
    assert applied["alreadyApplied"] is True
    assert target.read_text(encoding="utf-8") == new_text


def test_repo_relative_prompt_paths_resolve_for_draft_api() -> None:
    rel_path = "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/identity.md"

    resolved = resolve_repo_path(rel_path)

    assert resolved == REPO_ROOT / rel_path
    assert resolved.exists()


def test_eval_preview_filters_family_and_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bank = {
        "families": [
            {"id": "family_a", "cases": [{"id": "a_web", "surface": "web"}, {"id": "a_voice", "surface": "voice"}]},
            {"id": "family_b", "cases": [{"id": "b_web", "surface": "web"}]},
        ]
    }
    monkeypatch.setattr(evals, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)

    result = evals.run_exact_model_eval(max_cases=5, live=False, family="family_a", surface="voice", prompt_id="main.identity")

    assert result["mode"] == "synthetic-no-live-preview"
    assert result["resultCount"] == 1
    assert result["cases"] == [{"family": "family_a", "case": "a_voice", "surface": "voice"}]
    assert "outputDir" not in result
    assert result["privateOutputAvailable"] is True
    assert result["artifactName"] == result["id"]


def test_eval_case_edit_creates_reviewed_eval_bank_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps({"families": [{"id": "family_a", "cases": [{"id": "case_a", "surface": "web", "prompt": "old", "rubric": ["old rubric"]}]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")

    draft = evals.create_eval_case_draft(
        family_id="family_a",
        case_id="case_a",
        updated_case={"prompt": "new", "rubric": ["new rubric"]},
    )

    assert draft["kind"] == "eval-edit"
    assert draft["status"] == "draft"
    assert "new rubric" in draft["patch"]
    assert prompt_bank.read_text(encoding="utf-8").count("old rubric") == 1


def test_eval_case_edit_rejects_semantic_noop_formatting_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps({"families": [{"id": "family_a", "cases": [{"id": "case_a", "surface": "web", "prompt": "old", "rubric": ["old rubric"]}]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")

    with pytest.raises(ValueError, match="No changes detected"):
        evals.create_eval_case_draft(
            family_id="family_a",
            case_id="case_a",
            updated_case={"prompt": "old", "rubric": ["old rubric"], "surface": "web"},
        )


def test_eval_case_create_appends_without_reformatting_unrelated_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        '{\n'
        '  "families": [\n'
        '    {\n'
        '      "id": "family_a",\n'
        '      "cases": [\n'
        '        {\n'
        '          "id": "case_a",\n'
        '          "surface": "web",\n'
        '          "prompt": "old",\n'
        '          "rubric": ["old rubric"]\n'
        '        }\n'
        '      ]\n'
        '    },\n'
        '    {\n'
        '      "id": "family_b",\n'
        '      "cases": [\n'
        '        {\n'
        '          "id": "case_b",\n'
        '          "surface": "wing",\n'
        '          "prompt": "ambient",\n'
        '          "exact_runner_excluded_rubric_indices": [1],\n'
        '          "rubric": ["stay quiet"]\n'
        '        }\n'
        '      ]\n'
        '    }\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    draft = evals.create_eval_case_draft(
        family_id="family_a",
        case_id="new_case",
        updated_case={"surface": "voice", "prompt": "Say one useful thing.", "rubric": ["is concise"]},
        create=True,
    )
    raw_draft = json.loads((private_root / "drafts" / f"{draft['id']}.json").read_text(encoding="utf-8"))

    assert '"id": "new_case"' in draft["patch"]
    assert "exact_runner_excluded_rubric_indices" not in draft["patch"]
    assert json.loads(raw_draft["newText"])["families"][0]["cases"][1]["id"] == "new_case"


def test_workbench_context_links_prompt_history_evals_and_qa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "source_agents_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(sync_engine, "load_latest_live_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(sync_engine, "_git_commit", lambda: "abc123")

    context = prompt_service.workbench_context("main.identity")
    encoded = json.dumps(context)

    assert context["promptId"] == "main.identity"
    assert any(family["id"] == "main_identity_style" for family in context["linkedEvals"]["families"])
    assert any(row["id"] == "PW-004" for row in context["qaCoverage"])
    assert str(Path.home()) not in encoded


def test_workbench_context_surfaces_eval_edit_drafts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(prompt_service, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"agents": []})
    monkeypatch.setattr(evals, "evals_for_prompt", lambda prompt_id: {"promptId": prompt_id, "familyCount": 0, "caseCount": 0, "families": []})
    monkeypatch.setattr(evals, "list_eval_runs_for_prompt", lambda prompt_id, limit=8: [])
    monkeypatch.setattr(prompt_service, "qa_coverage_for_prompt", lambda prompt_id: [])

    drafts.create_file_draft(
        target_path=prompt_bank,
        new_text=json.dumps({"families": [{"id": "changed", "cases": []}]}) + "\n",
        kind="eval-edit",
    )

    context = prompt_service.workbench_context("main.voice_style")

    assert any(draft["kind"] == "eval-edit" for draft in context["drafts"])


def test_promptfoo_adapter_round_trips_one_synthetic_case() -> None:
    bank = {
        "families": [
            {
                "id": "family",
                "cases": [
                    {
                        "id": "case",
                        "surface": "web",
                        "prompt": "Answer briefly.",
                        "rubric": ["answers briefly and avoids private content"],
                    }
                ],
            }
        ]
    }

    config = promptfoo_adapter.prompt_bank_to_promptfoo(bank, prompt_id="main.conscious_agent")

    assert config["providers"] == ["echo"]
    assert config["tests"][0]["metadata"]["prompt_id"] == "main.conscious_agent"
    assert config["tests"][0]["vars"]["case_id"] == "case"


def test_prompt_workbench_cli_status_is_public_safe(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"

    completed = subprocess.run(
        [
            str(REPO_ROOT / "bin" / "viventium"),
            "--app-support-dir",
            str(app_support),
            "prompt-workbench",
            "status",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)

    assert payload == {"pid": None, "port": None, "status": "stopped", "url": None}
    assert str(REPO_ROOT) not in completed.stdout


def test_prompt_workbench_cli_help_documents_scoped_stop() -> None:
    completed = subprocess.run(
        [str(REPO_ROOT / "bin" / "viventium"), "help", "prompt-workbench"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "prompt-workbench open" in completed.stdout
    assert "prompt-workbench stop" in completed.stdout
    assert "Stop does not stop" in completed.stdout
    assert "main Viventium runtime" in completed.stdout


def test_prompt_workbench_lifecycle_script_scopes_process_ownership() -> None:
    script = (REPO_ROOT / "scripts" / "viventium" / "prompt_workbench.py").read_text(encoding="utf-8")

    assert "state/prompt-workbench" not in script
    assert '"state" / "prompt-workbench"' in script
    assert "prompt_workbench.app:app" in script
    assert "Recorded PID did not belong to this Prompt Workbench." in script
    assert "Cleared stale workbench state; retry the action." in script
    assert "clear_state(app_support_dir)" in script
    assert '"__pycache__"' in script
    assert "viventium-librechat-start.sh" not in script
    assert "native_stack.sh" not in script


def test_prompt_workbench_dev_server_ports_are_consistent() -> None:
    lifecycle_script = (REPO_ROOT / "scripts" / "viventium" / "prompt_workbench.py").read_text(encoding="utf-8")
    package_json = json.loads((REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "package.json").read_text(encoding="utf-8"))
    vite_config = (REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "vite.config.ts").read_text(encoding="utf-8")
    app_source = (
        REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend" / "prompt_workbench" / "app.py"
    ).read_text(encoding="utf-8")

    assert "DEFAULT_PORT = 8781" in lifecycle_script
    assert "--port 8781" in package_json["scripts"]["serve"]
    assert "--port 8781" in package_json["scripts"]["dev:api"]
    assert "'/api': 'http://127.0.0.1:8781'" in vite_config
    assert "127.0.0.1:8765" not in app_source
