#!/usr/bin/env python3
"""Receipt-compatible adapter for the installed MPV-061 semantic verifier."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


CASE_ID = "MPV-061"
CONTRACT_VERSION = 1
VERIFIER_ID = "mpv061-semantic-v1"
MAX_RESULT_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)
SHA256 = re.compile(r"[a-f0-9]{64}")
SAFE_KIND = re.compile(r"[a-z][a-z0-9_]{0,63}")
REQUIRED_GATES = (
    "full-journey-scope",
    "candidate-binding",
    "verified-private-evidence",
    "exact-session-and-reconnect-binding",
    "two-exact-independent-workers",
    "authorized-call-launch",
    "trusted-direct-wing-launch",
    "main-responsive-quick-turn",
    "authorized-call-control-a-only",
    "trusted-direct-wing-steer-a-only",
    "passive-wing-zero-authority",
    "listen-only-zero-authority",
    "exact-ordered-file-binding",
    "worker-context-capability-parity",
    "callback-delivery-and-artifact-once",
    "audible-transcript-audio-and-sole-queen",
    "hangup-reconnect-surface-continuity",
    "required-fallback-capability-parity",
    "required-restart-main-availability",
    "public-safe-report-boundary",
    "ordered-logical-turn-revisions",
    "all-evidence-bound-to-full-journey",
)
_RUNNER = Path(__file__).with_name("mpv_061_full_journey_semantic_qa.js")
_DERIVED_PASS = object()
_NODE_BRIDGE = r"""
const fs = require("fs");
const verifier = require("./mpv_061_full_journey_semantic_qa.js");
try {
  const request = JSON.parse(fs.readFileSync(0, "utf8"));
  const assessment = verifier.assessManifest(request.manifest, {
    evidenceRoot: request.evidenceRoot,
    identityDigests: request.identityDigests,
    checkedAt: request.checkedAt,
    installedOwnerProven: request.installedOwnerProven,
  });
  process.stdout.write(JSON.stringify({
    result: assessment.result,
    evidence: assessment.evidence.verified.map(({kind, path, sha256}) => ({
      kind,
      path,
      sha256,
    })),
  }));
} catch {
  process.stderr.write("semantic_verification_failed\n");
  process.exitCode = 2;
}
"""


class EvidenceContractError(ValueError):
    """The supplied journey cannot produce an authoritative MPV-061 receipt."""


def _invalid() -> None:
    raise EvidenceContractError("MPV-061 semantic evidence is invalid")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        _invalid()
    if parsed.tzinfo is None:
        _invalid()
    return parsed.astimezone(timezone.utc)


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _derived_result_digest(result: dict[str, object]) -> str:
    return _canonical_digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "blockers": result.get("blockers"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
            "contractVersion": result.get("contractVersion"),
            "counts": result.get("counts"),
            "evidenceDigest": result.get("evidenceDigest"),
            "fullJourneyStatus": result.get("fullJourneyStatus"),
            "gates": result.get("gates"),
            "ready": result.get("ready"),
            "receiptEvidence": result.get("_receiptEvidence"),
            "runAt": result.get("runAt"),
            "scope": result.get("scope"),
            "status": result.get("status"),
        }
    )


def _private_evidence_root(path: Path) -> Path:
    try:
        if path.is_symlink():
            _invalid()
        exact = path.resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError):
        _invalid()
    if (
        not exact.is_dir()
        or metadata.st_mode & 0o077
        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
    ):
        _invalid()
    public_root = Path(__file__).resolve().parents[3]
    try:
        exact.relative_to(public_root)
    except ValueError:
        return exact
    _invalid()


def _receipt_evidence(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw or len(raw) > 64:
        _invalid()
    verified: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"kind", "path", "sha256"}:
            _invalid()
        kind = entry.get("kind")
        relative_text = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(kind, str)
            or SAFE_KIND.fullmatch(kind) is None
            or not isinstance(relative_text, str)
            or not relative_text
            or not isinstance(digest, str)
            or SHA256.fullmatch(digest) is None
        ):
            _invalid()
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts or relative_text in seen:
            _invalid()
        seen.add(relative_text)
        verified.append({"kind": kind, "path": relative.as_posix(), "sha256": digest})
    return sorted(verified, key=lambda item: (item["kind"], item["path"]))


def assess_manifest(
    manifest: object,
    *,
    evidence_root: Path,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    installed_owner_proven: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    if (
        installed_owner_proven is not True
        or not isinstance(manifest, dict)
        or "status" in manifest
        or not isinstance(expected_candidate_digest, str)
        or SHA256.fullmatch(expected_candidate_digest) is None
        or not isinstance(expected_artifact_digest, str)
        or SHA256.fullmatch(expected_artifact_digest) is None
        or not _RUNNER.is_file()
    ):
        _invalid()
    candidate = manifest.get("candidate")
    if (
        not isinstance(candidate, dict)
        or candidate.get("candidateDigest") != expected_candidate_digest
        or candidate.get("artifactDigest") != expected_artifact_digest
    ):
        _invalid()
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _timestamp(manifest.get("runAt"))
    if run_at > checked_at + MAX_FUTURE_SKEW or checked_at - run_at > MAX_RESULT_AGE:
        _invalid()
    exact_root = _private_evidence_root(evidence_root)
    request = {
        "manifest": manifest,
        "evidenceRoot": str(exact_root),
        "identityDigests": {
            "candidateDigest": expected_candidate_digest,
            "artifactDigest": expected_artifact_digest,
        },
        "checkedAt": int(checked_at.timestamp() * 1000),
        "installedOwnerProven": True,
    }
    try:
        completed = subprocess.run(
            ["node", "-e", _NODE_BRIDGE],
            cwd=_RUNNER.parent,
            input=json.dumps(request, separators=(",", ":")),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        response = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        _invalid()
    if (
        completed.returncode != 0
        or not isinstance(response, dict)
        or set(response) != {"result", "evidence"}
        or not isinstance(response["result"], dict)
    ):
        _invalid()
    result = dict(response["result"])
    gates = result.get("gates")
    if (
        result.get("caseId") != CASE_ID
        or result.get("scope") != "full_journey"
        or not isinstance(gates, list)
        or len(gates) != len(REQUIRED_GATES)
        or [gate.get("id") for gate in gates if isinstance(gate, dict)]
        != list(REQUIRED_GATES)
        or result.get("candidateBinding")
        != {
            "matched": True,
            "candidateDigest": expected_candidate_digest,
            "artifactDigest": expected_artifact_digest,
        }
    ):
        _invalid()
    blockers = [str(gate["id"]) for gate in gates if gate.get("status") != "PASS"]
    ready = not blockers and result.get("status") == "PASS"
    result.update(
        {
            "artifactDigest": expected_artifact_digest,
            "blockers": blockers,
            "candidateDigest": expected_candidate_digest,
            "contractVersion": CONTRACT_VERSION,
            "ready": ready,
            "runAt": run_at.isoformat(),
            "_receiptEvidence": _receipt_evidence(response["evidence"]),
        }
    )
    result["_derivationDigest"] = _derived_result_digest(result)
    result["_derivedPass"] = _DERIVED_PASS if ready else None
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    if not isinstance(result, dict):
        _invalid()
    gates = result.get("gates")
    if (
        result.get("_derivedPass") is not _DERIVED_PASS
        or result.get("_derivationDigest") != _derived_result_digest(result)
        or result.get("caseId") != CASE_ID
        or result.get("contractVersion") != CONTRACT_VERSION
        or result.get("scope") != "full_journey"
        or result.get("status") != "PASS"
        or result.get("fullJourneyStatus") != "PASS"
        or result.get("ready") is not True
        or result.get("blockers") != []
        or not isinstance(gates, list)
        or len(gates) != len(REQUIRED_GATES)
        or [gate.get("id") for gate in gates if isinstance(gate, dict)]
        != list(REQUIRED_GATES)
        or any(gate.get("status") != "PASS" for gate in gates)
    ):
        _invalid()
    evidence = _receipt_evidence(result.get("_receiptEvidence"))
    if evidence != result.get("_receiptEvidence"):
        _invalid()
    return {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": _timestamp(result.get("runAt")).isoformat(),
        "status": "PASS",
        "surface": "voice",
    }
