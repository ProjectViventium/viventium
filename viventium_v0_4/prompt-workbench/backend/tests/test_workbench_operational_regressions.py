from __future__ import annotations

import json
import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from prompt_workbench import (  # noqa: E402
    auth,
    drafts,
    evals,
    periphery_snapshots,
    prompt_service,
    runtime_env,
    scheduled_prompts,
    sync_engine,
)


@pytest.mark.parametrize("private_source", (False, True))
def test_workbench_never_reuses_generated_runtime_yaml_as_prompt_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    private_source: bool,
) -> None:
    support = tmp_path / "synthetic-app-support"
    runtime = support / "runtime"
    runtime.mkdir(parents=True)
    env_path = runtime / "runtime.env"
    env_path.write_text("SYNTHETIC_WORKBENCH_MARKER=ready\n", encoding="utf-8")
    generated = runtime / "librechat.yaml"
    generated.write_text("generated: true\n", encoding="utf-8")
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH", str(generated))
    monkeypatch.delenv("VIVENTIUM_LIBRECHAT_PRIVATE_SOURCE_OF_TRUTH", raising=False)
    if private_source:
        approved = tmp_path / "approved-private-source.yaml"
        approved.write_text("version: 1\n", encoding="utf-8")
        monkeypatch.setenv("VIVENTIUM_LIBRECHAT_PRIVATE_SOURCE_OF_TRUTH", str(approved))

    runtime_env.load_viventium_runtime_env(env_path)

    assert os.environ.get("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH") == (
        str(approved) if private_source else None
    )


@pytest.mark.parametrize(
    "configured_origin",
    (
        "https://example.com",
        "http://127.0.0.1@example.com",
        "http://example.com@127.0.0.1:3080",
        "file:///synthetic-example",
        "http://127.0.0.1:3080?" + "access_token" + "=synthetic-example",
    ),
)
def test_admin_credentials_never_leave_a_strict_loopback_origin(
    configured_origin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", configured_origin)
    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)
    outbound_requests: list[object] = []
    monkeypatch.setattr(
        auth.urllib.request,
        "urlopen",
        lambda request, **_kwargs: outbound_requests.append(request),
    )

    from prompt_workbench.app import app

    response = TestClient(app).get(
        "/api/auth/status",
        headers={"authorization": "Bearer " + "synthetic-example"},
    )

    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert outbound_requests == []


def test_scratchpad_scan_ignores_generated_trees_and_symlinked_directories(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private-notes"
    private_root.mkdir()
    genuine = private_root / "notes"
    genuine.mkdir()
    (genuine / "actual-note.md").write_text("Genuine synthetic note", encoding="utf-8")

    for directory_name in ("node_modules", ".git", ".venv", "dist", "periphery"):
        ignored = private_root / directory_name
        ignored.mkdir()
        (ignored / "must-not-be-included.md").write_text(
            "Synthetic generated or private artifact",
            encoding="utf-8",
        )

    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.md").write_text("Synthetic external note", encoding="utf-8")
    (private_root / "linked-directory").symlink_to(external, target_is_directory=True)

    rows = periphery_snapshots._scratchpad_records(str(private_root), {})

    assert [row["relativePath"] for row in rows] == ["notes/actual-note.md"]


def test_scratchpad_scan_is_bounded_before_recursive_enumeration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private-notes"
    private_root.mkdir()
    for index in range(12):
        (private_root / f"synthetic-note-{index:02}.md").write_text(
            f"Synthetic note {index}",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        periphery_snapshots,
        "MAX_SCRATCHPAD_SCAN_ENTRIES",
        4,
        raising=False,
    )

    def fail_if_recursive_glob(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Scratchpad discovery must not enumerate an unbounded tree")

    monkeypatch.setattr(Path, "rglob", fail_if_recursive_glob)

    rows = periphery_snapshots._scratchpad_records(str(private_root), {})

    assert 0 < len(rows) <= 4


def test_simultaneous_eval_runs_keep_independent_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime(2026, 8, 25, 12, 0, 0, tzinfo=tz)

    private_root = tmp_path / "private"
    monkeypatch.setattr(evals, "datetime", FrozenDateTime)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: {"families": []})

    first = evals.run_exact_model_eval(live=False)
    second = evals.run_exact_model_eval(live=False)

    assert first["id"] != second["id"]
    assert (private_root / "eval-runs" / first["id"] / "workbench-run.json").is_file()
    assert (private_root / "eval-runs" / second["id"] / "workbench-run.json").is_file()
    assert len(evals.list_eval_runs()) == 2


@pytest.mark.parametrize(
    "unsafe_text",
    (
        "https://example.com/?" + "workbench_token" + "=synthetic-example&tab=evals",
        "Provider refused " + "access_token" + "=synthetic-example",
        "Authorization: Bearer " + "synthetic-example",
    ),
)
def test_public_eval_output_never_exposes_query_or_bearer_credentials(
    unsafe_text: str,
) -> None:
    redacted = evals._sanitize_output(unsafe_text)

    assert "synthetic-example" not in redacted


def test_public_eval_record_uses_a_typed_private_data_safe_projection() -> None:
    record = {
        "id": "20260825T160000Z-0123456789ab",
        "live": True,
        "outputDir": "/private/synthetic-owner/private-run",
        "prompt": "SYNTHETIC-PRIVATE-PROMPT",
        "rawResponse": "SYNTHETIC-PRIVATE-RESPONSE",
        "providerResponse": {"text": "SYNTHETIC-NESTED-RESPONSE"},
        "runnerSummary": {
            "status": "passed",
            "completedCount": 1,
            "rawResponse": "SYNTHETIC-SUMMARY-RESPONSE",
        },
        "executionRoute": {
            "status": "verified",
            "requestedProvider": "synthetic-provider",
            "requestedModel": "synthetic-model",
            "requestedEffort": "medium",
            "effectiveProvider": "synthetic-fallback-provider",
            "effectiveModel": "synthetic-fallback-model",
            "effectiveEffort": "high",
            "fallbackUsed": True,
            "fallbackAuthorized": True,
            "fallbackReason": "provider_timeout",
            "configuredProvider": "synthetic-provider",
            "privatePrompt": "SYNTHETIC-ROUTE-PROMPT",
            "fallbackError": "SYNTHETIC-PRIVATE-FALLBACK-ERROR",
            "routes": [
                {
                    "targetKey": "synthetic-target",
                    "fallbackReason": "SYNTHETIC-PRIVATE-FALLBACK-ERROR",
                }
            ],
        },
        "command": ["node", "--output-dir=/private/synthetic-owner/private-run"],
        "stdoutTail": "Provider used /private/synthetic-owner/model-artifact",
        "stderrTail": "",
    }

    public = evals._public_run_record(record)
    serialized = json.dumps(public, sort_keys=True)

    for private_value in (
        "SYNTHETIC-PRIVATE-PROMPT",
        "SYNTHETIC-PRIVATE-RESPONSE",
        "SYNTHETIC-NESTED-RESPONSE",
        "SYNTHETIC-SUMMARY-RESPONSE",
        "SYNTHETIC-ROUTE-PROMPT",
        "SYNTHETIC-PRIVATE-FALLBACK-ERROR",
        "/private/synthetic-owner",
    ):
        assert private_value not in serialized
    assert public["id"] == record["id"]
    assert public["runnerSummary"]["completedCount"] == 1
    assert public["executionRoute"]["status"] == "verified"
    assert public["executionRoute"]["requestedEffort"] == "medium"
    assert public["executionRoute"]["effectiveEffort"] == "high"
    assert public["executionRoute"]["fallbackReason"] == "provider_timeout"
    assert "fallbackReason" not in public["executionRoute"]["routes"][0]


@pytest.mark.parametrize(
    "sanitize",
    (evals._sanitize_output, sync_engine._sanitize_output, scheduled_prompts._safe_summary),
    ids=("eval", "sync", "schedule"),
)
@pytest.mark.parametrize(
    "unsafe_text",
    (
        "Provider rejected " + "access_token" + "=synthetic-example",
        '{"' + "client_secret" + '":"synthetic-example"}',
    ),
)
def test_all_workbench_output_paths_redact_structured_credentials(
    sanitize: object,
    unsafe_text: str,
) -> None:
    assert "synthetic-example" not in sanitize(unsafe_text)


def _configured_route(
    provider: str,
    model: str,
    effort: str = "medium",
    fallbacks: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "provider": provider,
        "model": model,
        "effort": effort,
        "fallbacks": fallbacks or [],
    }


def _prompt_route_frame(
    requested_provider: str,
    requested_model: str,
    *,
    requested_effort: str = "medium",
    effective_provider: str | None = None,
    effective_model: str | None = None,
    effective_effort: str | None = None,
    fallback_reason: str = "none",
) -> dict[str, object]:
    effective_provider = effective_provider or requested_provider
    effective_model = effective_model or requested_model
    effective_effort = effective_effort or requested_effort
    fallback_used = (
        effective_provider,
        effective_model,
        effective_effort,
    ) != (requested_provider, requested_model, requested_effort)
    return {
        "requested_provider_hash": evals._sha(requested_provider),
        "requested_model_hash": evals._sha(requested_model),
        "requested_effort": requested_effort,
        "provider_hash": evals._sha(effective_provider),
        "model_hash": evals._sha(effective_model),
        "effective_effort": effective_effort,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }


def test_exact_model_run_discloses_verified_actual_route_without_private_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    output_dir = private_root / "eval-runs" / "synthetic-live-run"
    output_dir.mkdir(parents=True)
    configured_provider = "synthetic-provider"
    configured_model = "synthetic-model"
    provider_hash = evals._sha(configured_provider)
    model_hash = evals._sha(configured_model)
    request_hash = evals._sha("synthetic-live-request")
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps(
            {
                "liveResults": [
                    {
                        "status": "completed",
                        "requestIdentityHash": request_hash,
                        "observedRequestIdentityHash": request_hash,
                        "responseForJudge": "Synthetic private model response",
                        "promptFrameEvidenceForJudge": json.dumps(
                            {
                                "prompt_frames": [
                                    {
                                        "prompt_family": "main_runtime",
                                        **_prompt_route_frame(
                                            configured_provider,
                                            configured_model,
                                        ),
                                        "request_identity_hash": request_hash,
                                    }
                                ]
                            }
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route(configured_provider, configured_model),
        raising=False,
    )

    route = evals._exact_model_execution_route(output_dir, execution_target=None)

    assert route == {
        "status": "verified",
        "requestedProvider": configured_provider,
        "requestedModel": configured_model,
        "requestedEffort": "medium",
        "effectiveProvider": configured_provider,
        "effectiveModel": configured_model,
        "effectiveEffort": "medium",
        "fallbackUsed": False,
        "fallbackAuthorized": False,
        "fallbackReason": "none",
        "configuredProvider": configured_provider,
        "configuredModel": configured_model,
        "configuredProviderHash": provider_hash,
        "configuredModelHash": model_hash,
        "observedProviderHash": provider_hash,
        "observedModelHash": model_hash,
        "completedCaseCount": 1,
    }
    assert "Synthetic private model response" not in json.dumps(route)


def test_exact_model_run_rejects_silent_provider_or_model_remap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "synthetic-live-run"
    output_dir.mkdir()
    request_hash = evals._sha("synthetic-remap-request")
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps(
            {
                "liveResults": [
                    {
                        "status": "completed",
                        "requestIdentityHash": request_hash,
                        "observedRequestIdentityHash": request_hash,
                        "promptFrameEvidenceForJudge": json.dumps(
                            {
                                "prompt_frames": [
                                    {
                                        "prompt_family": "main_runtime",
                                        **_prompt_route_frame(
                                            "configured-provider",
                                            "configured-model",
                                            effective_provider="unexpected-provider",
                                            effective_model="unexpected-model",
                                        ),
                                        "request_identity_hash": request_hash,
                                    }
                                ]
                            }
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route("configured-provider", "configured-model"),
        raising=False,
    )

    route = evals._exact_model_execution_route(output_dir, execution_target=None)

    assert route["status"] == "mismatch"
    assert route["reason"] == "configured_execution_route_mismatch"
    assert route["configuredProvider"] == "configured-provider"
    assert route["configuredModel"] == "configured-model"


@pytest.mark.parametrize(
    ("tamper", "expected_status", "expected_reason"),
    (
        ("missing_requested_effort", "unverified", "execution_route_evidence_unavailable"),
        ("missing_effective_effort", "unverified", "execution_route_evidence_unavailable"),
        ("undeclared_effort", "mismatch", "configured_execution_route_mismatch"),
        ("missing_fallback_reason", "mismatch", "fallback_reason_missing"),
    ),
)
def test_exact_model_run_fails_closed_on_incomplete_or_undeclared_effort_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    output_dir = tmp_path / f"synthetic-{tamper}"
    output_dir.mkdir()
    provider = "synthetic-provider"
    model = "synthetic-model"
    request_hash = evals._sha(f"synthetic-{tamper}-request")
    frame = _prompt_route_frame(provider, model)
    configured = _configured_route(provider, model)
    if tamper == "missing_requested_effort":
        frame.pop("requested_effort")
    elif tamper == "missing_effective_effort":
        frame.pop("effective_effort")
    else:
        frame.update(
            {
                "effective_effort": "high",
                "fallback_used": True,
                "fallback_reason": "provider_timeout",
            }
        )
        if tamper == "missing_fallback_reason":
            frame.pop("fallback_reason")
            configured["fallbacks"] = [
                {"provider": provider, "model": model, "effort": "high"}
            ]
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps(
            {
                "liveResults": [
                    {
                        "status": "completed",
                        "requestIdentityHash": request_hash,
                        "observedRequestIdentityHash": request_hash,
                        "promptFrameEvidenceForJudge": {
                            "prompt_frames": [
                                {
                                    "prompt_family": "main_runtime",
                                    **frame,
                                    "request_identity_hash": request_hash,
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: configured,
        raising=False,
    )

    route = evals._exact_model_execution_route(output_dir, execution_target=None)

    assert route["status"] == expected_status
    assert route["reason"] == expected_reason


def test_exact_model_run_reports_a_safe_surface_mismatch_instead_of_generic_missing_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "synthetic-surface-mismatch"
    output_dir.mkdir()
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps(
            {
                "liveResults": [
                    {
                        "caseId": "synthetic-telegram-case",
                        "surface": "telegram",
                        "observedSurface": "web",
                        "status": "failed",
                        "error": "execution_surface_mismatch",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route("configured-provider", "configured-model"),
    )

    route = evals._exact_model_execution_route(output_dir, execution_target=None)

    assert route["status"] == "unverified"
    assert route["reason"] == "execution_surface_mismatch"
    assert "telegram" not in json.dumps(route)
    assert "web" not in json.dumps(route)


@pytest.mark.parametrize("judge", (None, {"status": "unavailable"}, {"status": "judged", "pass": False}))
def test_exact_model_route_requires_actual_independent_semantic_verdicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    judge: dict[str, object] | None,
) -> None:
    output_dir = tmp_path / "synthetic-semantic-run"
    output_dir.mkdir()
    provider = "synthetic-provider"
    model = "synthetic-model"
    agent = "synthetic-agent"
    request_hash = evals._sha("synthetic-semantic-request")
    row: dict[str, object] = {
        "caseId": "synthetic-case",
        "status": "completed",
        "requestIdentityHash": request_hash,
        "observedRequestIdentityHash": request_hash,
        "promptFrameEvidenceForJudge": {
            "prompt_frames": [
                {
                    "prompt_family": "main_runtime",
                    **_prompt_route_frame(provider, model),
                    "agent_id_hash": evals._sha(agent),
                    "request_identity_hash": request_hash,
                }
            ]
        },
    }
    if judge is not None:
        row["semanticJudge"] = judge
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps({"summary": {"agentIdHash": evals._sha(agent)}, "args": {"agentIdHash": evals._sha(agent)}, "liveResults": [row]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route(provider, model),
    )

    route = evals._exact_model_execution_route(
        output_dir,
        execution_target={"agentId": agent, "promptRef": "cortex.synthetic.execution"},
        selected_case_ids=["synthetic-case"],
        semantic_judge_required=True,
    )

    assert route["status"] != "verified"
    assert route["reason"] == "semantic_judge_verdict_unverified"


def test_specialist_execution_cannot_be_certified_by_a_main_agent_provider_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "synthetic-specialist-run"
    output_dir.mkdir()
    provider = "synthetic-provider"
    model = "synthetic-model"
    specialist = "synthetic-specialist"
    request_hash = evals._sha("synthetic-specialist-request")
    (output_dir / "exact-model-eval.json").write_text(
        json.dumps(
            {
                "summary": {"agentIdHash": evals._sha(specialist)},
                "args": {"agentIdHash": evals._sha(specialist)},
                "liveResults": [
                    {
                        "caseId": "synthetic-case",
                        "status": "completed",
                        "requestIdentityHash": request_hash,
                        "observedRequestIdentityHash": request_hash,
                        "semanticJudge": {"status": "judged", "pass": True},
                        "promptFrameEvidenceForJudge": {
                            "prompt_frames": [
                                {
                                    "prompt_family": "main_runtime",
                                    **_prompt_route_frame(provider, model),
                                    "agent_id_hash": evals._sha("synthetic-main"),
                                    "request_identity_hash": request_hash,
                                }
                            ]
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route(provider, model),
    )

    route = evals._exact_model_execution_route(
        output_dir,
        execution_target={"agentId": specialist, "promptRef": "cortex.synthetic.execution"},
        selected_case_ids=["synthetic-case"],
        semantic_judge_required=True,
    )

    assert route["status"] != "verified"
    assert route["reason"] == "execution_agent_identity_mismatch"


@pytest.mark.parametrize("tamper", ("missing_judge_model", "missing_actual_judge_call"))
def test_semantic_judgment_requires_a_completed_independent_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    output_dir = tmp_path / "synthetic-independent-judge-run"
    output_dir.mkdir()
    provider = "synthetic-provider"
    model = "synthetic-model"
    specialist = "synthetic-specialist"
    judge_hash = evals._sha("synthetic-judge")
    request_hash = evals._sha("synthetic-independent-judge-request")
    payload = {
        "summary": {"agentIdHash": evals._sha(specialist), "judgeModelHash": judge_hash},
        "args": {"agentIdHash": evals._sha(specialist), "judgeModelHash": judge_hash},
        "liveResults": [
            {
                "caseId": "synthetic-case",
                "status": "completed",
                "requestIdentityHash": request_hash,
                "observedRequestIdentityHash": request_hash,
                "semanticJudge": {
                    "status": "judged",
                    "pass": True,
                    "attemptCount": 1,
                    "rawHash": evals._sha("synthetic-judge-response"),
                },
                "promptFrameEvidenceForJudge": {
                    "prompt_frames": [
                        {
                            "prompt_family": "main_runtime",
                            **_prompt_route_frame(provider, model),
                            "agent_id_hash": evals._sha(specialist),
                            "request_identity_hash": request_hash,
                        }
                    ]
                },
            }
        ],
    }
    if tamper == "missing_judge_model":
        payload["summary"].pop("judgeModelHash")
    else:
        payload["liveResults"][0]["semanticJudge"]["attemptCount"] = 0
    (output_dir / "exact-model-eval.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route(provider, model),
    )

    route = evals._exact_model_execution_route(
        output_dir,
        execution_target={"agentId": specialist, "promptRef": "cortex.synthetic.execution"},
        selected_case_ids=["synthetic-case"],
        semantic_judge_required=True,
    )

    assert route["status"] != "verified"
    assert route["reason"] == "semantic_judge_verdict_unverified"


def test_model_mismatch_cannot_keep_a_successful_runner_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: {"families": []})
    monkeypatch.setattr(
        evals,
        "_exact_model_execution_route",
        lambda *_args, **_kwargs: {
            "status": "mismatch",
            "reason": "configured_execution_route_mismatch",
        },
    )
    monkeypatch.setattr(
        evals.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "passed", "completedCount": 1, "resultCount": 1}),
            stderr="",
        ),
    )

    result = evals.run_exact_model_eval(live=True)

    assert result["returnCode"] == 1
    assert result["runnerSummary"]["status"] == "blocked"
    assert result["runnerSummary"]["blockedReason"] == "configured_execution_route_mismatch"


def test_unverified_execution_cannot_keep_a_forged_successful_stdout_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evals, "workbench_private_root", lambda: tmp_path)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: {"families": []})
    monkeypatch.setattr(
        evals,
        "_exact_model_execution_route",
        lambda *_args, **_kwargs: {
            "status": "unverified",
            "reason": "semantic_judge_verdict_unverified",
        },
    )
    monkeypatch.setattr(
        evals.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "completed_full_semantic_passed",
                    "resultCount": 1,
                    "semanticJudgedCount": 1,
                    "semanticPassedCount": 1,
                }
            ),
            stderr="",
        ),
    )

    result = evals.run_exact_model_eval(live=True)

    assert result["returnCode"] == 1
    assert result["runnerSummary"]["status"] == "blocked"
    assert result["runnerSummary"]["blockedReason"] == "semantic_judge_verdict_unverified"


def _activation_route_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    observed_provider: str,
    observed_model: str,
    completed_attempt: bool = True,
) -> tuple[Path, dict[str, object]]:
    output_dir = tmp_path / "synthetic-activation"
    output_dir.mkdir()
    bank: dict[str, object] = {
        "families": [
            {
                "id": "synthetic-activation-family",
                "runner": "background_activation",
                "activationTargets": [
                    {"key": "synthetic-target", "agentId": "synthetic-agent"}
                ],
            }
        ]
    }
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(
        prompt_service,
        "source_agents_bundle",
        lambda: {
            "mainAgent": {
                "background_cortices": [
                    {
                        "agent_id": "synthetic-agent",
                        "activation": {
                            "provider": "primary-provider",
                            "model": "primary-model",
                            "fallbacks": [
                                {
                                    "provider": "fallback-provider",
                                    "model": "fallback-model",
                                }
                            ],
                        },
                    }
                ]
            }
        },
    )
    fallback_used = (observed_provider, observed_model) != (
        "primary-provider",
        "primary-model",
    )
    fallback_reason = "provider_timeout" if fallback_used else "none"
    attempts = []
    if completed_attempt:
        if fallback_used:
            attempts.append(
                {
                    "provider": "primary-provider",
                    "model": "primary-model",
                    "effort": "provider_default",
                    "source": "primary",
                    "status": "failed",
                    "fallbackReason": "none",
                    "error": {"class": "provider_timeout"},
                }
            )
        attempts.append(
            {
                "provider": observed_provider,
                "model": observed_model,
                "effort": "provider_default",
                "source": "fallback" if fallback_used else "primary",
                "status": "completed",
                "fallbackReason": fallback_reason,
            }
        )
    (output_dir / "activation-model-eval.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "targetKey": "synthetic-target",
                        "actual": True,
                        "error": None,
                        "providerUsed": observed_provider,
                        "modelUsed": observed_model,
                        "effortUsed": "provider_default",
                        "requestedProvider": "primary-provider",
                        "requestedModel": "primary-model",
                        "requestedEffort": "provider_default",
                        "effectiveProvider": observed_provider,
                        "effectiveModel": observed_model,
                        "effectiveEffort": "provider_default",
                        "fallbackReason": fallback_reason,
                        "providerAttempts": attempts,
                        "reason": "Private model content must never be copied",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return output_dir, bank


def test_activation_eval_identifies_only_explicitly_authorized_fallbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir, bank = _activation_route_fixture(
        tmp_path,
        monkeypatch,
        observed_provider="fallback-provider",
        observed_model="fallback-model",
    )

    route = evals._activation_model_execution_route(
        output_dir,
        bank=bank,
        family_id="synthetic-activation-family",
    )

    assert route["status"] == "verified"
    assert route["completedCaseCount"] == 1
    assert route["routes"][0] == {
        "targetKey": "synthetic-target",
        "requestedProvider": "primary-provider",
        "requestedModel": "primary-model",
        "requestedEffort": "provider_default",
        "configuredProvider": "primary-provider",
        "configuredModel": "primary-model",
        "effectiveProvider": "fallback-provider",
        "effectiveModel": "fallback-model",
        "effectiveEffort": "provider_default",
        "fallbackUsed": True,
        "fallbackAuthorized": True,
        "fallbackReason": "provider_timeout",
    }
    assert "Private model content" not in json.dumps(route)


def test_activation_eval_rejects_an_undeclared_provider_or_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir, bank = _activation_route_fixture(
        tmp_path,
        monkeypatch,
        observed_provider="unexpected-provider",
        observed_model="unexpected-model",
    )

    route = evals._activation_model_execution_route(
        output_dir,
        bank=bank,
        family_id="synthetic-activation-family",
    )

    assert route["status"] == "mismatch"
    assert route["reason"] == "configured_execution_route_mismatch"


def test_activation_eval_does_not_treat_unproven_provider_labels_as_execution_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir, bank = _activation_route_fixture(
        tmp_path,
        monkeypatch,
        observed_provider="primary-provider",
        observed_model="primary-model",
        completed_attempt=False,
    )

    route = evals._activation_model_execution_route(
        output_dir,
        bank=bank,
        family_id="synthetic-activation-family",
    )

    assert route["status"] == "unverified"
    assert route["reason"] == "activation_provider_completion_unverified"


@pytest.mark.parametrize("tamper", ("wrong_decision", "duplicate", "fallback_without_primary_failure"))
def test_activation_execution_route_rejects_forged_decisions_and_fallback_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    fallback = tamper == "fallback_without_primary_failure"
    output_dir, bank = _activation_route_fixture(
        tmp_path,
        monkeypatch,
        observed_provider="fallback-provider" if fallback else "primary-provider",
        observed_model="fallback-model" if fallback else "primary-model",
    )
    artifact_path = output_dir / "activation-model-eval.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    row = payload["results"][0]
    row.update(
        {
            "caseId": "synthetic-case",
            "repetition": 1,
            "required": True,
            "allowed": True,
            "actual": tamper != "wrong_decision",
            "pass": True,
        }
    )
    if tamper == "fallback_without_primary_failure":
        row["providerAttempts"] = row["providerAttempts"][-1:]
    if tamper == "duplicate":
        payload["results"].append(dict(row))
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    route = evals._activation_model_execution_route(
        output_dir,
        bank=bank,
        family_id="synthetic-activation-family",
        selected_case_ids=["synthetic-case"],
    )

    assert route["status"] != "verified"
    assert route["reason"] in {
        "activation_decision_incorrect",
        "activation_decision_duplicate",
        "activation_primary_failure_unverified",
        "fallback_reason_mismatch",
    }


def test_live_activation_eval_preserves_the_complete_canonical_model_execution_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bank = {
        "families": [
            {
                "id": "synthetic-activation-family",
                "runner": "background_activation",
                "activationTargets": [{"key": "synthetic-target", "agentId": "synthetic-agent"}],
                "cases": [{"id": "synthetic-case", "surface": "web"}],
            }
        ]
    }
    canonical_summary = {
        "status": "passed",
        "selectedCaseCount": 1,
        "selectedTargetCount": 1,
        "repetitions": 1,
        "resultCount": 1,
        "completedCount": 1,
        "passCount": 1,
        "failureCount": 0,
        "failedCaseRunCount": 0,
        "falsePositiveCount": 0,
        "falseNegativeCount": 0,
        "unavailableCount": 0,
        "unavailableRequiredCount": 0,
        "timeoutOrProviderErrorCount": 0,
        "inconsistentDecisionCount": 0,
        "semanticInconsistentDecisionCount": 0,
        "privateTrace": "synthetic-private-content",
    }
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: tmp_path)
    monkeypatch.setattr(evals, "_eval_lineage_manifest", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(evals, "_activation_model_execution_route", lambda *_args, **_kwargs: {
        "status": "verified",
        "completedCaseCount": 1,
        "routes": [],
    })
    monkeypatch.setattr(drafts, "assert_no_active_blocking_drafts", lambda *_args, **_kwargs: None)

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        output = Path(next(item.split("=", 1)[1] for item in command if item.startswith("--output-dir=")))
        (output / "activation-model-eval.json").write_text(
            json.dumps({"summary": canonical_summary, "results": []}),
            encoding="utf-8",
        )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "passed", "resultCount": 1}),
            stderr="",
        )

    monkeypatch.setattr(evals.subprocess, "run", run)

    result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="synthetic-activation-family",
    )

    assert result["runnerSummary"]["completedCount"] == 1
    assert result["runnerSummary"]["selectedTargetCount"] == 1
    assert result["runnerSummary"]["passCount"] == 1
    assert "synthetic-private-content" not in json.dumps(result)


def test_build_version_reports_when_running_backend_no_longer_matches_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app_module = importlib.import_module("prompt_workbench.app")
    monkeypatch.setattr(app_module, "_BACKEND_BOOT_SOURCE_HASH", "loaded-source", raising=False)
    monkeypatch.setattr(app_module, "_backend_source_hash", lambda: "current-source", raising=False)

    payload = TestClient(app_module.app).get("/api/build-version").json()

    assert payload["backend"] == {
        "loadedSourceHash": "loaded-source",
        "currentSourceHash": "current-source",
        "sourceCurrent": False,
    }


def test_build_version_exposes_only_a_verified_public_safe_frontend_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module = importlib.import_module("prompt_workbench.app")
    source = tmp_path / "src" / "App.tsx"
    asset = tmp_path / "dist" / "assets" / "index.js"
    source.parent.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    (tmp_path / "dist" / "index.html").write_text(
        '<script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    asset.write_text("built", encoding="utf-8")
    monkeypatch.setattr(app_module, "WORKBENCH_ROOT", tmp_path)
    monkeypatch.setattr(app_module, "_BACKEND_BOOT_SOURCE_HASH", "a" * 16)
    monkeypatch.setattr(app_module, "_backend_source_hash", lambda: "a" * 16)

    assert app_module.build_version()["frontend"]["receiptValid"] is False
    asset_hash, file_count = app_module._built_asset_identity()
    receipt = {
        "schemaVersion": 1,
        "frontendInputHash": app_module._frontend_input_identity(),
        "builtAssetHash": asset_hash,
        "builtFileCount": file_count,
    }
    (tmp_path / "dist" / app_module.BUILD_RECEIPT_NAME).write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    payload = app_module.build_version()

    assert payload["frontend"]["receiptValid"] is True
    assert str(tmp_path) not in json.dumps(payload)

    fixed_time = asset.stat().st_mtime_ns
    asset.write_text("stale", encoding="utf-8")
    os.utime(asset, ns=(fixed_time, fixed_time))
    assert app_module.build_version()["frontend"]["receiptValid"] is False


def _installed_fixture() -> dict[str, dict[str, object]]:
    source_hash = "a" * 16
    created_at = datetime.now(timezone.utc)
    configured_provider = "synthetic-provider"
    configured_model = "synthetic-model"
    provider_hash = evals._sha(configured_provider)
    model_hash = evals._sha(configured_model)
    scheduled_run = {"status": "completed", "triggerKind": "scheduled"}
    lineage = {
        "schemaVersion": 1,
        "familyIds": ["synthetic-family"],
        "caseIds": ["synthetic-case"],
        "rootPromptIds": [],
        "promptDependencies": [],
        "runtimeContextDependencies": [],
        "includeEdges": [],
        "promptCount": 0,
        "runtimeContextCount": 0,
    }
    lineage["manifestHash"] = evals._sha(json.dumps(lineage, sort_keys=True, separators=(",", ":")))
    return {
        "/api/auth/status": {
            "authenticated": True,
            "admin": True,
            "method": "local_loopback_admin",
        },
        "/api/build-version": {
            "available": True,
            "indexHash": source_hash,
            "entryAssets": ["/assets/synthetic.js"],
            "backend": {
                "loadedSourceHash": source_hash,
                "currentSourceHash": source_hash,
                "sourceCurrent": True,
            },
            "frontend": {
                "receiptAvailable": True,
                "schemaVersion": 1,
                "receiptFrontendInputHash": "b" * 64,
                "currentFrontendInputHash": "b" * 64,
                "receiptBuiltAssetHash": "c" * 64,
                "currentBuiltAssetHash": "c" * 64,
                "receiptBuiltFileCount": 2,
                "currentBuiltFileCount": 2,
                "sourceCurrent": True,
                "assetsCurrent": True,
                "receiptValid": True,
            },
        },
        "/api/frames": {
            "frames": [],
            "health": {
                "status": "empty",
                "source": "trusted_runtime_logs",
                "reason": "no_matching_frames",
                "filesScanned": 1,
                "invalidEventCount": 0,
                "truncatedReadCount": 0,
                "releaseEvidence": False,
            },
        },
        "/api/prompts": {
            "prompts": [
                {"id": "main.identity"},
                {"id": "surface.wing"},
                {"id": "scheduler.consciousness_continuity_opportunity"},
            ],
            "flow": {"nodes": [{"id": "main.identity"}]},
            "evalBank": {"caseCount": 1},
        },
        "/api/prompts/main.identity/workbench-context": {
            "promptId": "main.identity",
            "delivery": {"kind": "managed_agent", "state": "synced"},
            "sync": {"state": "synced", "sourceHash": source_hash, "liveHash": source_hash},
        },
        "/api/prompts/surface.wing/workbench-context": {
            "promptId": "surface.wing",
            "delivery": {"kind": "compiled_runtime", "state": "synced"},
            "runtimePromptBundle": {
                "status": "ok",
                "promptState": "synced",
                "liveBundleAvailable": True,
            },
        },
        "/api/prompts/scheduler.consciousness_continuity_opportunity/workbench-context": {
            "promptId": "scheduler.consciousness_continuity_opportunity",
            "delivery": {"kind": "compiled_runtime", "state": "synced"},
            "runtimePromptBundle": {
                "status": "ok",
                "promptState": "synced",
                "liveBundleAvailable": True,
            },
        },
        "/api/drafts": {"drafts": [{"status": "applied"}]},
        "/api/evals": {
            "familyCount": 1,
            "caseCount": 1,
            "families": [{"id": "synthetic-family", "cases": [{"id": "synthetic-case"}]}],
        },
        "/api/evals/execution-route": {
            "provider": configured_provider,
            "model": configured_model,
        },
        "/api/evals/runs": {
            "runs": [
                {
                    "id": created_at.strftime("%Y%m%dT%H%M%SZ") + "-0123456789ab",
                    "candidateSourceHash": source_hash,
                    "live": True,
                    "createdAt": created_at.isoformat(),
                    "returnCode": 0,
                    "selectedCaseCount": 1,
                    "selectedCaseIds": ["synthetic-case"],
                    "resultCount": 1,
                    "lineageManifest": lineage,
                    "runnerSummary": {
                        "status": "completed_full",
                        "completedCount": 1,
                        "resultCount": 1,
                        "failedCount": 0,
                    },
                    "executionRoute": {
                        "status": "verified",
                        "configuredProvider": configured_provider,
                        "configuredModel": configured_model,
                        "configuredProviderHash": provider_hash,
                        "configuredModelHash": model_hash,
                        "observedProviderHash": provider_hash,
                        "observedModelHash": model_hash,
                        "completedCaseCount": 1,
                        "artifactSha256": "a" * 64,
                        "caseEvidence": [
                            {
                                "caseId": "synthetic-case",
                                "agentIdHash": evals._sha("synthetic-main"),
                                "semanticJudged": False,
                                "semanticPassed": False,
                            }
                        ],
                    },
                }
            ]
        },
        "/api/scheduled-prompts?readOnly=true": {
            "scheduledPrompts": [
                {
                    "id": "synthetic-continuity",
                    "sourcePromptId": "scheduler.consciousness_continuity_opportunity",
                    "active": True,
                    "latestScheduledRun": scheduled_run,
                },
                {
                    "id": "synthetic-nightly",
                    "templateId": "workbench_nightly_subconscious_thought_formation_v1",
                    "active": True,
                    "latestScheduledRun": scheduled_run,
                },
            ]
        },
        "/api/scheduled-prompts/synthetic-continuity/runs?readOnly=true": {"runs": [scheduled_run]},
        "/api/scheduled-prompts/synthetic-nightly/runs?readOnly=true": {"runs": [scheduled_run]},
        "/api/cognitive-integrity": {
            "schemaVersion": 3,
            "status": "ok",
            "blockingChecks": [],
            "checks": {
                "runtimeConfigDrift": {"status": "ok"},
                "promptBundleDrift": {"status": "ok"},
                "sourceProviderCapabilityTransport": {"status": "ok"},
                "liveProviderCapabilityTransport": {"status": "ok"},
                "sourceMemoryExposure": {"status": "ok"},
                "liveMemoryExposure": {"status": "ok"},
                "glasshiveHostWorkerRuntime": {"status": "ok"},
                "workbenchNightly": {"status": "ok"},
                "workbenchHealthContext": {"status": "ok"},
                "workbenchConsciousnessContinuity": {"status": "ok"},
                "qaTestAccount": {"status": "ok"},
                "qaAccountSavedMemoryReadRuntime": {"status": "ok"},
                "qaAccountImmediateMemoryWriterRuntime": {"status": "ok"},
                "conversationRecallRuntime": {"status": "ok"},
                "memoryHardening": {"status": "ok"},
            },
        },
    }


def _run_installed_fixture(
    payloads: dict[str, dict[str, object]],
    *,
    origin: str = "http://127.0.0.1:8781",
) -> dict[str, object]:
    from prompt_workbench import installed_journey

    return installed_journey.inspect_installed_workbench(
        origin,
        fetch=lambda path, _timeout: payloads[path],
    )


def test_installed_read_only_proof_requires_every_real_workbench_gate() -> None:
    report = _run_installed_fixture(_installed_fixture())

    assert report["status"] == "pass"
    assert report["blockingChecks"] == []
    assert report["counts"]["promptCount"] == 3
    assert report["counts"]["verifiedLiveEvalCount"] == 1
    assert report["counts"]["verifiedEvalCaseCount"] == 1


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("run", "selectedCaseCount", 2),
        ("run", "selectedCaseIds", []),
        ("run", "selectedCaseIds", ["synthetic-case", "synthetic-case"]),
        ("run", "selectedCaseIds", ["unknown-case"]),
        ("run", "resultCount", 2),
        ("summary", "completedCount", 2),
        ("summary", "resultCount", 2),
        ("route", "completedCaseCount", 2),
    ),
)
def test_installed_proof_rejects_inconsistent_selected_completed_and_verified_eval_counts(
    target: str,
    field: str,
    value: object,
) -> None:
    payloads = _installed_fixture()
    row = payloads["/api/evals/runs"]["runs"][0]
    selected = {
        "run": row,
        "summary": row["runnerSummary"],
        "route": row["executionRoute"],
    }[target]
    selected[field] = value

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def test_installed_proof_rejects_one_passing_case_when_other_required_cases_were_not_run() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals"]["caseCount"] = 2
    payloads["/api/evals"]["families"][0]["cases"].append({"id": "untested-case"})

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "required_eval_coverage_incomplete" in report["blockingChecks"]
    assert report["counts"]["evalCaseCount"] == 2
    assert report["counts"]["verifiedEvalCaseCount"] == 1


def test_installed_proof_accepts_complete_case_coverage_across_independently_verified_runs() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals"]["caseCount"] = 2
    payloads["/api/evals"]["families"][0]["cases"].append({"id": "second-case"})
    first = payloads["/api/evals/runs"]["runs"][0]
    second = {
        **first,
        "id": first["id"][:-12] + "0123456789ac",
        "selectedCaseIds": ["second-case"],
        "runnerSummary": {**first["runnerSummary"]},
        "executionRoute": {
            **first["executionRoute"],
            "caseEvidence": [
                {**first["executionRoute"]["caseEvidence"][0], "caseId": "second-case"}
            ],
        },
        "lineageManifest": {**first["lineageManifest"], "caseIds": ["second-case"]},
    }
    lineage = second["lineageManifest"]
    lineage.pop("manifestHash")
    lineage["manifestHash"] = evals._sha(json.dumps(lineage, sort_keys=True, separators=(",", ":")))
    payloads["/api/evals/runs"]["runs"].append(second)

    report = _run_installed_fixture(payloads)

    assert report["status"] == "pass"
    assert report["counts"]["verifiedLiveEvalCount"] == 2
    assert report["counts"]["verifiedEvalCaseCount"] == 2


@pytest.mark.parametrize(
    "cases",
    (
        [{"id": "synthetic-case"}, {"id": "synthetic-case"}],
        [{"id": "synthetic-case"}, {}],
    ),
)
def test_installed_proof_rejects_duplicate_or_unbound_required_eval_cases(
    cases: list[dict[str, object]],
) -> None:
    payloads = _installed_fixture()
    payloads["/api/evals"]["caseCount"] = 2
    payloads["/api/evals"]["families"][0]["cases"] = cases

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "eval_registry_invalid" in report["blockingChecks"]


def test_installed_proof_rejects_semantic_judge_count_below_selected_cases() -> None:
    payloads = _installed_fixture()
    row = payloads["/api/evals/runs"]["runs"][0]
    row["semanticJudgeRequired"] = True
    row["runnerSummary"].update({"semanticJudgedCount": 0, "semanticPassedCount": 1})

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("caseIds", ["different-case"]),
        ("familyIds", ["different-family"]),
        ("manifestHash", "0" * 16),
    ),
)
def test_installed_proof_rejects_unbound_or_changed_eval_lineage(
    field: str,
    value: object,
) -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/runs"]["runs"][0]["lineageManifest"][field] = value

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def test_installed_proof_rejects_a_missing_eval_lineage_manifest() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/runs"]["runs"][0].pop("lineageManifest")

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def test_installed_proof_cannot_disable_a_catalog_required_semantic_judge() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals"]["families"][0]["semanticJudge"] = True
    payloads["/api/evals/runs"]["runs"][0]["semanticJudgeRequired"] = False

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def _installed_specialist_fixture() -> dict[str, dict[str, object]]:
    payloads = _installed_fixture()
    target = {"agentId": "synthetic-specialist", "promptRef": "cortex.synthetic.execution"}
    payloads["/api/evals"]["families"][0].update(
        {
            "runner": "background_execution",
            "executionTarget": target,
            "promptRefs": [target["promptRef"]],
        }
    )
    content_hash = evals._sha("synthetic-specialist-content")
    body_hash = evals._sha("synthetic-specialist-body")
    payloads["/api/prompts"]["prompts"].append(
        {
            "id": target["promptRef"],
            "contentHash": content_hash,
            "bodyHash": body_hash,
            "includeCount": 0,
        }
    )
    route = {"provider": "specialist-provider", "model": "specialist-model"}
    payloads["/api/evals/execution-route?family=synthetic-family"] = {
        "kind": "background_execution",
        "family": "synthetic-family",
        "agentId": target["agentId"],
        "promptRef": target["promptRef"],
        **route,
    }
    row = payloads["/api/evals/runs"]["runs"][0]
    row.update({"family": "synthetic-family", "executionTarget": target, "semanticJudgeRequired": True})
    row["lineageManifest"]["executionTarget"] = target
    row["lineageManifest"]["rootPromptIds"] = [target["promptRef"]]
    row["lineageManifest"]["promptDependencies"] = [
        {
            "id": target["promptRef"],
            "kind": "prompt",
            "status": "available",
            "direct": True,
            "contentHash": content_hash,
            "bodyHash": body_hash,
            "renderedHash": evals._sha("synthetic-specialist-rendered"),
        }
    ]
    row["lineageManifest"]["promptCount"] = 1
    row["lineageManifest"].pop("manifestHash")
    row["lineageManifest"]["manifestHash"] = evals._sha(
        json.dumps(row["lineageManifest"], sort_keys=True, separators=(",", ":"))
    )
    row["runnerSummary"].update({"semanticJudgedCount": 1, "semanticPassedCount": 1})
    row["executionRoute"].update(
        {
            "configuredProvider": route["provider"],
            "configuredModel": route["model"],
            "configuredProviderHash": evals._sha(route["provider"]),
            "configuredModelHash": evals._sha(route["model"]),
            "observedProviderHash": evals._sha(route["provider"]),
            "observedModelHash": evals._sha(route["model"]),
            "caseEvidence": [
                {
                    "caseId": "synthetic-case",
                    "agentIdHash": evals._sha(target["agentId"]),
                    "semanticJudged": True,
                    "semanticPassed": True,
                }
            ],
        }
    )
    return payloads


def test_installed_proof_accepts_a_specialist_exact_model_without_remapping_to_main() -> None:
    report = _run_installed_fixture(_installed_specialist_fixture())

    assert report["status"] == "pass"
    assert report["counts"]["verifiedEvalCaseCount"] == 1


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("row", "family", "different-family"),
        ("target", "agentId", "different-specialist"),
        ("target", "promptRef", "cortex.other.execution"),
        ("route", "configuredModel", "different-model"),
    ),
)
def test_installed_proof_rejects_a_specialist_with_wrong_owner_or_model(
    target: str,
    field: str,
    value: str,
) -> None:
    payloads = _installed_specialist_fixture()
    row = payloads["/api/evals/runs"]["runs"][0]
    selected = {"row": row, "target": row["executionTarget"], "route": row["executionRoute"]}[target]
    selected[field] = value

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def _installed_activation_fixture() -> dict[str, dict[str, object]]:
    payloads = _installed_fixture()
    targets = [
        {"key": "synthetic-first", "agentId": "synthetic-agent-first"},
        {"key": "synthetic-second", "agentId": "synthetic-agent-second"},
    ]
    payloads["/api/evals"]["families"][0].update(
        {"runner": "background_activation", "activationTargets": targets}
    )
    payloads["/api/evals"]["families"][0]["cases"][0].update(
        {
            "required_activations": ["synthetic-first"],
            "allowed_activations": ["synthetic-first"],
        }
    )
    payloads["/api/evals/execution-route?family=synthetic-family"] = {
        "kind": "background_activation",
        "family": "synthetic-family",
        "targets": [
            {
                "targetKey": "synthetic-first",
                "provider": "first-provider",
                "model": "first-model",
                "fallbacks": [{"provider": "approved-fallback", "model": "fallback-model"}],
            },
            {
                "targetKey": "synthetic-second",
                "provider": "second-provider",
                "model": "second-model",
                "fallbacks": [],
            },
        ],
    }
    row = payloads["/api/evals/runs"]["runs"][0]
    row.update(
        {
            "family": "synthetic-family",
            "semanticJudgeRequired": False,
            "resultCount": 2,
            "runnerSummary": {
                "status": "passed",
                "selectedCaseCount": 1,
                "selectedTargetCount": 2,
                "repetitions": 1,
                "resultCount": 2,
                "completedCount": 2,
                "passCount": 2,
                "failureCount": 0,
                "failedCaseRunCount": 0,
                "falsePositiveCount": 0,
                "falseNegativeCount": 0,
                "unavailableCount": 0,
                "unavailableRequiredCount": 0,
                "timeoutOrProviderErrorCount": 0,
                "inconsistentDecisionCount": 0,
                "semanticInconsistentDecisionCount": 0,
            },
            "executionRoute": {
                "status": "verified",
                "completedCaseCount": 2,
                "artifactSha256": "a" * 64,
                "routes": [
                    {
                        "targetKey": "synthetic-first",
                        "configuredProvider": "first-provider",
                        "configuredModel": "first-model",
                        "effectiveProvider": "first-provider",
                        "effectiveModel": "first-model",
                        "fallbackUsed": False,
                        "fallbackAuthorized": False,
                    },
                    {
                        "targetKey": "synthetic-second",
                        "configuredProvider": "second-provider",
                        "configuredModel": "second-model",
                        "effectiveProvider": "second-provider",
                        "effectiveModel": "second-model",
                        "fallbackUsed": False,
                        "fallbackAuthorized": False,
                    },
                ],
                "caseEvidence": [
                    {
                        "caseId": "synthetic-case",
                        "targetKey": "synthetic-first",
                        "repetition": 1,
                        "required": True,
                        "allowed": True,
                        "actual": True,
                        "passed": True,
                        "effectiveProvider": "first-provider",
                        "effectiveModel": "first-model",
                        "primaryFailureVerified": False,
                    },
                    {
                        "caseId": "synthetic-case",
                        "targetKey": "synthetic-second",
                        "repetition": 1,
                        "required": False,
                        "allowed": False,
                        "actual": False,
                        "passed": True,
                        "effectiveProvider": "second-provider",
                        "effectiveModel": "second-model",
                        "primaryFailureVerified": False,
                    },
                ],
            },
        }
    )
    return payloads


def test_installed_proof_accepts_all_configured_activation_targets_without_main_model_remap() -> None:
    report = _run_installed_fixture(_installed_activation_fixture())

    assert report["status"] == "pass"
    assert report["counts"]["verifiedEvalCaseCount"] == 1


def test_installed_proof_accepts_only_an_explicitly_configured_activation_fallback() -> None:
    payloads = _installed_activation_fixture()
    execution_route = payloads["/api/evals/runs"]["runs"][0]["executionRoute"]
    route = execution_route["routes"][0]
    route.update(
        {
            "effectiveProvider": "approved-fallback",
            "effectiveModel": "fallback-model",
            "fallbackUsed": True,
            "fallbackAuthorized": True,
        }
    )
    execution_route["caseEvidence"][0].update(
        {
            "effectiveProvider": "approved-fallback",
            "effectiveModel": "fallback-model",
            "primaryFailureVerified": True,
        }
    )

    report = _run_installed_fixture(payloads)

    assert report["status"] == "pass"


def test_installed_proof_rejects_an_activation_target_missing_from_observed_provider_evidence() -> None:
    payloads = _installed_activation_fixture()
    payloads["/api/evals/runs"]["runs"][0]["executionRoute"]["routes"].pop()

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("summary", "selectedTargetCount", 1),
        ("summary", "completedCount", 1),
        ("summary", "passCount", 1),
        ("summary", "falsePositiveCount", 1),
        ("summary", "unavailableRequiredCount", 1),
        ("route", "effectiveProvider", "unapproved-provider"),
        ("route", "fallbackAuthorized", True),
    ),
)
def test_installed_proof_rejects_incomplete_or_unauthorized_activation_execution(
    target: str,
    field: str,
    value: object,
) -> None:
    payloads = _installed_activation_fixture()
    row = payloads["/api/evals/runs"]["runs"][0]
    selected = row["runnerSummary"] if target == "summary" else row["executionRoute"]["routes"][0]
    selected[field] = value

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize("origin", ("https://example.com", "file:///synthetic-example"))
def test_installed_proof_rejects_non_loopback_before_any_request(origin: str) -> None:
    from prompt_workbench import installed_journey

    requested: list[str] = []

    with pytest.raises(ValueError, match="loopback"):
        installed_journey.inspect_installed_workbench(
            origin,
            fetch=lambda path, _timeout: requested.append(path),
        )

    assert requested == []


def test_installed_proof_fails_closed_for_stale_running_backend() -> None:
    payloads = _installed_fixture()
    payloads["/api/build-version"]["backend"] = {"sourceCurrent": False}

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "installed_backend_source_stale" in report["blockingChecks"]


def test_installed_proof_rejects_an_unbound_backend_identity_claim() -> None:
    payloads = _installed_fixture()
    payloads["/api/build-version"]["backend"] = {"sourceCurrent": True}

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "installed_backend_source_stale" in report["blockingChecks"]


@pytest.mark.parametrize(
    ("frontend_change", "expected"),
    (
        ({"receiptAvailable": False}, "installed_frontend_build_receipt_invalid"),
        ({"currentFrontendInputHash": "f" * 64}, "installed_frontend_build_receipt_invalid"),
        ({"currentBuiltAssetHash": "f" * 64}, "installed_frontend_build_receipt_invalid"),
    ),
)
def test_installed_proof_requires_a_current_frontend_build_receipt(
    frontend_change: dict[str, object],
    expected: str,
) -> None:
    payloads = _installed_fixture()
    payloads["/api/build-version"]["frontend"].update(frontend_change)

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert expected in report["blockingChecks"]


@pytest.mark.parametrize(
    ("frames", "expected"),
    (
        ({"frames": []}, "frames_health_unverified"),
        (
            {
                "frames": [],
                "health": {"status": "degraded", "releaseEvidence": False},
            },
            "frames_health_degraded",
        ),
        (
            {
                "frames": [],
                "health": {"status": "unavailable", "releaseEvidence": False},
            },
            "frames_health_unavailable",
        ),
    ),
)
def test_installed_proof_requires_typed_healthy_frames(
    frames: dict[str, object],
    expected: str,
) -> None:
    payloads = _installed_fixture()
    payloads["/api/frames"] = frames

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert expected in report["blockingChecks"]


def test_frames_failure_does_not_conceal_cognitive_integrity_failure() -> None:
    payloads = _installed_fixture()
    payloads["/api/frames"] = {"frames": []}
    payloads["/api/cognitive-integrity"] = {
        "schemaVersion": 3,
        "status": "blocked",
        "blockingChecks": ["workbenchConsciousnessContinuity"],
        "checks": {},
    }

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "frames_health_unverified" in report["blockingChecks"]
    assert "cognitive_integrity_blocked" in report["blockingChecks"]


def test_stale_backend_stops_before_schedule_reads_that_could_modify_state() -> None:
    from prompt_workbench import installed_journey

    payloads = _installed_fixture()
    payloads["/api/build-version"]["backend"] = {"sourceCurrent": False}
    requested: list[str] = []

    def fetch(path: str, _timeout: float) -> dict[str, object]:
        requested.append(path)
        return payloads[path]

    report = installed_journey.inspect_installed_workbench(
        "http://127.0.0.1:8781",
        fetch=fetch,
    )

    assert report["status"] == "blocked"
    assert not any(path.startswith("/api/scheduled-prompts") for path in requested)


def test_schedule_listing_endpoint_can_use_a_non_mutating_storage_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app_module = importlib.import_module("prompt_workbench.app")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "true")
    observed: list[bool] = []

    def list_schedules(*, user_id: str, read_only: bool = False) -> dict[str, list[object]]:
        observed.append(read_only)
        return {"scheduledPrompts": []}

    monkeypatch.setattr(app_module.scheduled_prompts, "list_scheduled_prompts", list_schedules)

    response = TestClient(app_module.app).get("/api/scheduled-prompts?readOnly=true")

    assert response.status_code == 200
    assert observed == [True]


def test_schedule_run_history_supports_read_only_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[bool] = []

    class FakeStore:
        def get_scheduled_prompt_definition(self, _definition_id: str) -> dict[str, str]:
            return {"user_id": "synthetic-owner"}

        def list_scheduled_prompt_runs(self, **_kwargs: object) -> list[object]:
            return []

    def open_storage(*, read_only: bool = False) -> FakeStore:
        observed.append(read_only)
        return FakeStore()

    monkeypatch.setattr(scheduled_prompts, "storage", open_storage)

    result = scheduled_prompts.list_runs(
        "synthetic-definition",
        user_id="synthetic-owner",
        read_only=True,
    )

    assert result == {"runs": []}
    assert observed == [True]


def test_installed_proof_fails_closed_without_verified_exact_model_execution() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/runs"]["runs"][0].pop("executionRoute")

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize("status", ("partial_semantic_passed", "partial_baseline"))
def test_installed_proof_rejects_partial_eval_evidence(status: str) -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/runs"]["runs"][0]["runnerSummary"]["status"] = status

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def test_installed_proof_binds_eval_to_the_current_configured_provider_and_model() -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/execution-route"]["model"] = "new-configured-model"

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize(
    "change",
    (
        {"completedCount": True},
        {"failedCount": 1},
        {"semanticFailedCount": 1},
        {"semanticJudgeUnavailableCount": 1},
        {"duplicateResponseQualityFailureCount": 1},
        {"unresolvedAsyncQualityFailureCount": 1},
        {"status": "failed_completion"},
    ),
)
def test_installed_proof_rejects_failed_or_malformed_eval_evidence(
    change: dict[str, object],
) -> None:
    payloads = _installed_fixture()
    payloads["/api/evals/runs"]["runs"][0]["runnerSummary"].update(change)

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


def test_installed_proof_rejects_empty_scheduled_run_history() -> None:
    payloads = _installed_fixture()
    payloads["/api/scheduled-prompts/synthetic-continuity/runs?readOnly=true"] = {
        "runs": []
    }

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "continuity_run_history_unavailable" in report["blockingChecks"]


def test_installed_proof_rejects_an_unsubstantiated_cognitive_health_claim() -> None:
    payloads = _installed_fixture()
    payloads["/api/cognitive-integrity"] = {"status": "ok", "blockingChecks": []}

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "cognitive_integrity_blocked" in report["blockingChecks"]


@pytest.mark.parametrize(
    "check",
    (
        "sourceProviderCapabilityTransport",
        "liveProviderCapabilityTransport",
        "sourceMemoryExposure",
        "liveMemoryExposure",
        "glasshiveHostWorkerRuntime",
        "workbenchHealthContext",
        "qaTestAccount",
        "qaAccountSavedMemoryReadRuntime",
        "conversationRecallRuntime",
    ),
)
def test_installed_proof_rejects_an_omitted_canonical_cognitive_health_check(
    check: str,
) -> None:
    payloads = _installed_fixture()
    payloads["/api/cognitive-integrity"]["checks"].pop(check)

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "cognitive_integrity_blocked" in report["blockingChecks"]


def test_execution_route_endpoint_exposes_only_the_explicit_configured_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app_module = importlib.import_module("prompt_workbench.app")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "true")
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: _configured_route("synthetic-provider", "synthetic-model"),
    )

    response = TestClient(app_module.app).get("/api/evals/execution-route")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "synthetic-provider",
        "model": "synthetic-model",
        "effort": "medium",
        "fallbacks": [],
    }


def test_execution_route_endpoint_exposes_the_current_declared_specialist_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app_module = importlib.import_module("prompt_workbench.app")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "true")
    route = {
        "kind": "background_execution",
        "family": "synthetic-family",
        "agentId": "synthetic-agent",
        "promptRef": "cortex.synthetic.execution",
        "provider": "synthetic-specialist-provider",
        "model": "synthetic-specialist-model",
    }
    monkeypatch.setattr(
        evals,
        "_configured_family_execution_route",
        lambda family: route if family == "synthetic-family" else None,
    )

    response = TestClient(app_module.app).get("/api/evals/execution-route?family=synthetic-family")
    unavailable = TestClient(app_module.app).get("/api/evals/execution-route?family=unknown-family")

    assert response.status_code == 200
    assert response.json() == route
    assert unavailable.status_code == 503


def test_family_execution_routes_use_each_declared_specialist_and_activation_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bank = {
        "families": [
            {
                "id": "synthetic-specialist-family",
                "runner": "background_execution",
                "executionTarget": {
                    "agentId": "synthetic-specialist",
                    "promptRef": "cortex.synthetic.execution",
                },
                "cases": [{"id": "specialist-case"}],
            },
            {
                "id": "synthetic-activation-family",
                "runner": "background_activation",
                "activationTargets": [{"key": "synthetic-target", "agentId": "synthetic-activation"}],
                "cases": [{"id": "activation-case"}],
            },
        ]
    }
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(
        prompt_service,
        "source_agents_bundle",
        lambda: {
            "mainAgent": {
                "provider": "main-provider",
                "model": "main-model",
                "reasoning_effort": "medium",
                "background_cortices": [
                    {
                        "agent_id": "synthetic-activation",
                        "activation": {
                            "provider": "activation-provider",
                            "model": "activation-model",
                            "fallbacks": [
                                {"provider": "approved-fallback", "model": "fallback-model"}
                            ],
                        },
                    }
                ],
            },
            "backgroundAgents": [
                {
                    "id": "synthetic-specialist",
                    "provider": "specialist-provider",
                    "model": "specialist-model",
                    "reasoning_effort": "medium",
                }
            ],
        },
    )

    specialist = evals._configured_family_execution_route("synthetic-specialist-family")
    activation = evals._configured_family_execution_route("synthetic-activation-family")

    assert specialist == {
        "kind": "background_execution",
        "family": "synthetic-specialist-family",
        "agentId": "synthetic-specialist",
        "promptRef": "cortex.synthetic.execution",
        "provider": "specialist-provider",
        "model": "specialist-model",
        "effort": "medium",
        "fallbacks": [],
    }
    assert activation == {
        "kind": "background_activation",
        "family": "synthetic-activation-family",
        "targets": [
            {
                "targetKey": "synthetic-target",
                "provider": "activation-provider",
                "model": "activation-model",
                "effort": "provider_default",
                "fallbacks": [
                    {
                        "provider": "approved-fallback",
                        "model": "fallback-model",
                        "effort": "provider_default",
                    }
                ],
            }
        ],
    }


def test_installed_proof_never_repeats_private_response_values() -> None:
    payloads = _installed_fixture()
    payloads["/api/auth/status"].update(
        {"email": "owner@example.com", "userId": "synthetic-owner-identifier"}
    )
    payloads["/api/prompts"]["prompts"][0]["text"] = "Synthetic private user prompt"

    report = _run_installed_fixture(payloads)
    encoded = json.dumps(report)

    assert "owner@example.com" not in encoded
    assert "synthetic-owner-identifier" not in encoded
    assert "Synthetic private user prompt" not in encoded


def test_installed_proof_does_not_hide_failed_continuity_or_cognitive_health() -> None:
    payloads = _installed_fixture()
    continuity = payloads["/api/scheduled-prompts?readOnly=true"]["scheduledPrompts"][0]
    continuity["latestScheduledRun"] = {"status": "failed", "triggerKind": "scheduled"}
    payloads["/api/cognitive-integrity"] = {
        "status": "blocked",
        "blockingChecks": ["workbenchConsciousnessContinuity"],
    }

    report = _run_installed_fixture(payloads)

    assert report["status"] == "blocked"
    assert "continuity_latest_scheduled_run_failed" in report["blockingChecks"]
    assert "cognitive_integrity_blocked" in report["blockingChecks"]


def test_agent_source_bundle_overlays_applied_prompt_registry_without_changing_other_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "local.viventium-agents.yaml"
    source_path.write_text(
        """\
meta:
  version: 7
mainAgent:
  id: main-agent
  instructions: stale main instructions
  tools:
    - keep-main-tool
backgroundAgents:
  - id: parallel-agent
    instructions: stale parallel instructions
    provider: keep-provider
  - id: unmanaged-agent
    instructions: keep unmanaged instructions
config:
  keep: unchanged
""",
        encoding="utf-8",
    )
    prompt_root = tmp_path / "prompts"
    (prompt_root / "main").mkdir(parents=True)
    (prompt_root / "cortex").mkdir()
    (prompt_root / "main" / "conscious.md").write_text(
        """\
---
id: main.conscious_agent
owner_layer: test
target: main.instructions
version: 1
status: active
safety_class: public_product
required_context: []
output_contract: system_instructions
includes:
- main.tools
---
""",
        encoding="utf-8",
    )
    (prompt_root / "main" / "tools.md").write_text(
        """\
---
id: main.tools
owner_layer: test
target: main.instructions.section
version: 1
status: active
safety_class: public_product
required_context: []
output_contract: system_instructions
---
Applied main tools
""",
        encoding="utf-8",
    )
    (prompt_root / "cortex" / "parallel.md").write_text(
        """\
---
id: cortex.parallel.execution
owner_layer: test
target: backgroundAgents.parallel-agent.instructions
version: 1
status: active
safety_class: public_product
required_context: []
output_contract: system_instructions
---
Applied parallel instructions
""",
        encoding="utf-8",
    )
    before = source_path.read_bytes()
    monkeypatch.setattr(prompt_service, "AGENTS_SOURCE_PATH", source_path)
    monkeypatch.setattr(prompt_service, "PROMPTS_ROOT", prompt_root)

    bundle = prompt_service.source_agents_bundle()

    assert bundle["mainAgent"]["instructions"] == "Applied main tools"
    assert bundle["mainAgent"]["tools"] == ["keep-main-tool"]
    assert bundle["backgroundAgents"][0]["instructions"] == "Applied parallel instructions"
    assert bundle["backgroundAgents"][0]["provider"] == "keep-provider"
    assert bundle["backgroundAgents"][1]["instructions"] == "keep unmanaged instructions"
    assert bundle["config"] == {"keep": "unchanged"}
    assert source_path.read_bytes() == before


@pytest.mark.parametrize("review_flag", ("--dry-run", "--compare-reviewed"))
def test_prompt_push_uses_private_ephemeral_rendered_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review_flag: str,
) -> None:
    private_root = tmp_path / "private"
    observed: dict[str, object] = {}
    bundle = {
        "meta": {"version": 7},
        "mainAgent": {
            "id": "main-agent",
            "instructions": "applied rendered instructions",
            "tools": ["keep-main-tool"],
        },
        "config": {"keep": "unchanged"},
    }

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        input_arg = next(arg for arg in cmd if arg.startswith("--in="))
        input_path = Path(input_arg.removeprefix("--in="))
        observed["input_path"] = input_path
        observed["mode"] = input_path.stat().st_mode & 0o777
        observed["bundle"] = sync_engine.yaml.safe_load(
            input_path.read_text(encoding="utf-8")
        )
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "source_agents_bundle", lambda: bundle)
    monkeypatch.setattr(sync_engine.subprocess, "run", fake_run)

    sync_engine.run_agent_sync(["push", "--env=local", "--prompts-only", review_flag])

    assert observed["bundle"] == bundle
    assert observed["mode"] == 0o600
    assert private_root in Path(observed["input_path"]).parents
    assert not Path(observed["input_path"]).exists()


def test_pull_sync_cannot_rewrite_prompt_source_of_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        observed.append(cmd)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_run)

    sync_engine.run_agent_sync(["pull", "--env=local"])

    assert observed
    assert "--no-source-of-truth" in observed[0]


def test_live_import_advances_only_matching_reconciled_ledger_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir()
    ledger_path = private_root / "sync-ledger.json"
    untouched_conflict = {
        "agentId": "other-agent",
        "sourcePromptId": "cortex.other.execution",
        "sourceCommit": "old-commit",
        "sourceHash": "other-source-before",
        "renderedHash": "other-source-before",
        "liveHash": "other-live-before",
        "liveAgentVersion": 3,
        "updatedAt": "2026-01-01T00:00:00+00:00",
        "evalRunIds": ["other-eval"],
    }
    ledger_path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": {
                    "main-agent": {
                        "agentId": "main-agent",
                        "sourcePromptId": "main.conscious_agent",
                        "sourceCommit": "old-commit",
                        "sourceHash": "source-before",
                        "renderedHash": "source-before",
                        "liveHash": "live-before",
                        "liveAgentVersion": 1,
                        "updatedAt": "2026-01-01T00:00:00+00:00",
                        "evalRunIds": ["passing-eval"],
                    },
                    "other-agent": untouched_conflict,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sync_engine,
        "get_status",
        lambda private_root=None: {
            "sourceCommit": "current-commit",
            "agents": [
                {
                    "agentId": "main-agent",
                    "sourcePromptId": "main.conscious_agent",
                    "sourceHash": "reconciled",
                    "liveHash": "reconciled",
                    "liveAgentVersion": 2,
                },
                {
                    "agentId": "other-agent",
                    "sourcePromptId": "cortex.other.execution",
                    "sourceHash": "other-source-now",
                    "liveHash": "other-live-now",
                    "liveAgentVersion": 4,
                },
            ],
        },
    )

    result = sync_engine.advance_matching_reconciled_rows(private_root=private_root)
    updated = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert result == {"status": "updated", "updatedRecordCount": 1}
    assert updated["records"]["main-agent"]["sourceHash"] == "reconciled"
    assert updated["records"]["main-agent"]["liveHash"] == "reconciled"
    assert updated["records"]["main-agent"]["evalRunIds"] == ["passing-eval"]
    assert updated["records"]["other-agent"] == untouched_conflict
    assert (
        sync_engine.classify_sync_state(
            source_hash="next-source-edit",
            live_hash="reconciled",
            ledger_record=updated["records"]["main-agent"],
        )
        == "source-ahead"
    )


@pytest.mark.parametrize(
    ("draft_kind", "expected_advances"),
    (("live-import", 1), ("source-edit", 0), ("eval-edit", 0)),
)
def test_apply_draft_advances_reconciled_rows_only_for_live_import(
    draft_kind: str,
    expected_advances: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module = importlib.import_module("prompt_workbench.app")
    advances: list[bool] = []
    monkeypatch.setattr(
        app_module.drafts,
        "get_draft",
        lambda _draft_id: {"kind": draft_kind},
    )
    monkeypatch.setattr(
        app_module.drafts,
        "apply_draft",
        lambda draft_id, token: {
            "id": draft_id,
            "status": "applied",
            "token": token,
        },
    )
    monkeypatch.setattr(
        app_module.sync_engine,
        "advance_matching_reconciled_rows",
        lambda: advances.append(True),
        raising=False,
    )

    result = app_module.apply_draft(
        "synthetic-draft",
        SimpleNamespace(idempotencyToken="reviewed-token"),
        None,
    )

    assert result["status"] == "applied"
    assert len(advances) == expected_advances


def test_reviewed_push_pulls_fresh_live_before_advancing_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    calls: list[list[str]] = []
    ledger_refresh_after_calls: list[list[list[str]]] = []
    status = {
        "counts": {
            "synced": 0,
            "source-ahead": 1,
            "live-ahead": 0,
            "conflict": 0,
        },
        "agents": [
            {
                "agentId": "main-agent",
                "label": "Main",
                "sourceHash": "source-after-edit",
            }
        ],
    }

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {
            "returnCode": 0,
            "parsed": {"args": args},
            "stdoutTail": "synthetic reviewed output",
        }

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "get_status", lambda: status)
    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)
    monkeypatch.setattr(
        sync_engine,
        "refresh_ledger_after_reconcile",
        lambda private_root=None: ledger_refresh_after_calls.append(list(calls))
        or {"status": "updated"},
    )

    dry_run = sync_engine.push_live_dry_run(env="local")
    sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [
        ["push", "--env=local", "--prompts-only", "--dry-run"],
        ["push", "--env=local", "--prompts-only", "--compare-reviewed"],
        ["pull", "--env=local"],
    ]
    assert ledger_refresh_after_calls == [calls]
