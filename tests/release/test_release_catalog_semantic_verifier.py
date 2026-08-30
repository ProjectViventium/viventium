from __future__ import annotations

from pathlib import Path

import pytest

from test_parallel_work_catalog_semantic_verifier import (
    RELEASE_CASE_IDS,
    assess_bundle,
    build_catalog_bundle,
    corrupt_case_binding,
    load_catalog_module,
    rewrite_document,
)


@pytest.mark.parametrize("case_id", RELEASE_CASE_IDS)
def test_every_release_case_requires_current_candidate_bound_installed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)

    result = assess_bundle(bundle)

    assert result["status"] == "PASS"
    assert result["caseId"] == case_id
    receipt = bundle["module"].receipt_manifest(result=result)
    assert receipt["surface"] == bundle["spec"].surface
    assert receipt["evidence"]


@pytest.mark.parametrize("case_id", RELEASE_CASE_IDS)
def test_every_release_case_rejects_missing_catalog_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    bundle["manifest"]["checks"].pop()

    with pytest.raises(ValueError, match="required catalog check"):
        assess_bundle(bundle)


@pytest.mark.parametrize("case_id", RELEASE_CASE_IDS)
@pytest.mark.parametrize("binding", ["case", "owner", "surface", "candidate", "artifact"])
def test_every_release_case_rejects_cross_case_owner_surface_or_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    binding: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    corrupt_case_binding(bundle, binding)

    with pytest.raises(ValueError):
        assess_bundle(bundle)


def test_release_browser_case_requires_real_browser_capture_and_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "REL-004")

    def remove_reload(document: dict[str, object]) -> None:
        document["payload"]["records"] = [
            record
            for record in document["payload"]["records"]
            if record["observationId"] != "background-cards-persist-after-reload"
        ]

    rewrite_document(bundle, "delivery_ledger", remove_reload)

    with pytest.raises(ValueError, match="observation"):
        assess_bundle(bundle)


@pytest.mark.parametrize(
    ("case_id", "kind", "observation"),
    [
        ("REL-001", "repository_scan", "zero-private-identifiers"),
        ("REL-002", "component_identity", "nested-source-review-complete"),
        ("REL-003", "component_identity", "parent-pin-equals-component-revision"),
        ("REL-005", "repository_scan", "zero-cross-project-markers"),
        ("REL-006", "release_snapshot", "open-gates-keep-feature-dark"),
        ("REL-UC-001", "repository_scan", "public-diff-user-path-clean"),
        ("REL-UC-002", "repository_scan", "degraded-scan-reports-unavailable"),
        ("REL-UC-003", "component_identity", "component-boundary-survives-restart"),
    ],
)
def test_release_cases_reject_faked_zero_findings_pin_and_dark_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    kind: str,
    observation: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)

    def corrupt(document: dict[str, object]) -> None:
        record = next(
            value
            for value in document["payload"]["records"]
            if value["observationId"] == observation
        )
        field = next(iter(record["facts"]))
        existing = record["facts"][field]
        if isinstance(existing, bool):
            record["facts"][field] = not existing
        elif isinstance(existing, int):
            record["facts"][field] = existing + 1
        else:
            record["facts"][field] = "fabricated"

    rewrite_document(bundle, kind, corrupt)

    with pytest.raises(ValueError, match="measurement"):
        assess_bundle(bundle)


def test_catalog_keeps_rel_uc_004_with_its_dedicated_hardened_verifier() -> None:
    module = load_catalog_module()

    assert "REL-UC-004" not in module.CASE_SPECS


def test_release_source_cases_do_not_accept_user_visible_text_without_producer_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "REL-001")
    rewrite_document(
        bundle,
        "repository_scan",
        lambda document: document["payload"].update(assertions=["PASS", "zero findings"]),
    )

    with pytest.raises(ValueError, match="producer|record|assertion"):
        assess_bundle(bundle)
