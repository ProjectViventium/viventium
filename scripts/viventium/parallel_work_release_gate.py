#!/usr/bin/env python3
"""Fail closed while required Parallel Work release QA remains open."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import importlib.util
import json
import os
import re
import selectors
import shlex
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import FunctionType, ModuleType

PASS = "PASS"
CONTRACT_VERSION = 1
SNAPSHOT_TTL_SECONDS = 86_400
SNAPSHOT_RENEWAL_WINDOW_SECONDS = 3_600
MAX_FUTURE_SKEW_SECONDS = 60
QA_RECEIPT_TTL_SECONDS = 86_400
QA_RECEIPT_SURFACES = {
    "api",
    "cli",
    "installer",
    "scheduler",
    "telegram",
    "voice",
    "web",
    "workbench",
}
QA_RECEIPT_CASE_SURFACES = {
    "MPV-061": "voice",
    "TGDOC-010": "telegram",
}
QA_RECEIPT_SERVICE_ACK_CASES = {
    "TR-026",
    "EMO-UC-047",
    "EMO-UC-048",
    "PWK-UC-016",
    "PWK-UC-017",
    "REL-UC-004",
}
PROMPT_PRODUCER_SCOPE = "viventium.prompt_registry.v1"
SAFE_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}")
QA_RECEIPT_ATTESTATION = re.compile(r"hmac-sha256:[0-9a-f]{64}")
QA_RECEIPT_NONCE = re.compile(r"[0-9a-f]{32}")
QA_RECEIPT_SERVICE_SESSION = re.compile(r"qa_[0-9a-f]{24}")
QA_RECEIPT_ATTESTATION_KEY_NAME = "parallel-work-qa-attestation.key"
TRUSTED_GIT_EXECUTABLE = "/usr/bin/git"
TRUSTED_PROCESS_EXECUTABLE = "/bin/ps"
MAX_WORKTREE_HASH_FILES = 100_000
MAX_WORKTREE_HASH_BYTES = 512 * 1024 * 1024
WORKTREE_HASH_CHUNK_BYTES = 1024 * 1024
GIT_COMMAND_TIMEOUT_SECONDS = 10
MAX_GIT_REVISION_BYTES = 128
MAX_READINESS_FACTS_BYTES = 1024 * 1024
QA_RECEIPT_ATTESTATION_FIELDS = {
    "attestation",
    "ownerBindingSha256",
    "receiptNonce",
    "verifierId",
    "verifierManifestSha256",
}
QA_RECEIPT_EXTERNAL_ATTESTATION_FIELDS = {
    "attestationContractVersion",
    "attestationPurpose",
    "attestationSequence",
    "producerAttestations",
    "publisherAttestation",
    "publisherIdentity",
    "serviceAcknowledgements",
}
QA_RELEASE_ATTESTATION_LEDGER_NAME = "parallel-work-release-attestation-ledger.json"
RELEASE_AUTHORITY_SYSTEM_DIRECTORY = Path(
    "/Library/Application Support/Viventium/ReleaseAuthority/v1"
)
RELEASE_AUTHORITY_BOOTSTRAP_NAMESPACE = (
    "viventium-qa-release-authority-bootstrap-v1"
)
RELEASE_AUTHORITY_BOOTSTRAP_PURPOSE = (
    "viventium.qa.release.authority-bootstrap.v1"
)
RELEASE_AUTHORITY_WITNESS_PROTECTION = (
    "externally-protected-compare-and-swap-v1"
)
RELEASE_AUTHORITY_WITNESS_DURABILITY = "root-owned-persistent-monotonic-v1"
RELEASE_AUTHORITY_WITNESS_NAMESPACE = "viventium-qa-release-witness-v1"
RELEASE_AUTHORITY_WITNESS_REQUEST_PURPOSE = "viventium.qa.release.witness-request.v1"
RELEASE_AUTHORITY_WITNESS_RESPONSE_PURPOSE = "viventium.qa.release.witness-response.v1"
RELEASE_AUTHORITY_WITNESS_SOCKET_NAME = "witness.sock"
RELEASE_AUTHORITY_WITNESS_MAX_RESPONSE_BYTES = 32 * 1024
RELEASE_AUTHORITY_WITNESS_TIMEOUT_SECONDS = 5
RELEASE_AUTHORITY_PROVIDER_MODULE = "viventium_protected_release_authority_provider"
RELEASE_AUTHORITY_FILE_LIMITS = {
    "bootstrap.json": 64 * 1024,
    "bootstrap.sig": 16 * 1024,
    "publisher.allowed_signers": 16 * 1024,
    "provider.py": 256 * 1024,
    "witness.allowed_signers": 16 * 1024,
}
RELEASE_AUTHORITY_BOOTSTRAP_FIELDS = frozenset(
    {
        "candidateDigest",
        "contractVersion",
        "ownerBindingSha256",
        "policySha256",
        "provider",
        "publisher",
        "purpose",
        "witness",
    }
)
RELEASE_AUTHORITY_PROVIDER_RESULT_FIELDS = frozenset(
    {
        "candidateDigest",
        "contractVersion",
        "ledgerWitness",
        "ownerBindingSha256",
        "policySha256",
        "publisherFingerprint",
        "publisherIdentity",
        "witnessIdentity",
    }
)
REGISTERED_SEMANTIC_VERIFIERS = {
    **{
        f"{prefix}{number:03d}": {
            "id": "viventium-installed-catalog-v1",
            "path": Path(
                "qa/parallel-orchestrator/scripts/catalog_case_semantic_verifier.py"
            ),
        }
        for prefix, stop in (
            ("PWK-", 50),
            ("PWK-UC-", 14),
            ("REL-", 7),
            ("REL-UC-", 4),
        )
        for number in range(1, stop)
    },
    **{
        f"PWK-UC-{number:03d}": {
            "id": "pwk-installed-journey-v1",
            "path": Path("qa/parallel-orchestrator/scripts/installed_journey_qa.py"),
        }
        for number in range(14, 20)
    },
    "EMO-UC-047": {
        "id": "emo047-semantic-v1",
        "path": Path("qa/emotional-cortex/scripts/run_emo_uc_047.py"),
    },
    "EMO-UC-048": {
        "id": "emo048-semantic-v1",
        "path": Path("qa/emotional-cortex/scripts/run_emo_uc_048.py"),
    },
    "MPV-061": {
        "id": "mpv061-semantic-v1",
        "path": Path(
            "qa/modern-playground-voice/scripts/mpv_061_full_journey_semantic_verifier.py"
        ),
    },
    "REL-UC-004": {
        "id": "rel004-semantic-v1",
        "path": Path("qa/release-readiness/scripts/rel_uc_004_semantic_verifier.py"),
    },
    "TGDOC-010": {
        "id": "tgd010-semantic-v1",
        "path": Path("qa/telegram-document-attachments/scripts/worker_bee_file_parity_qa.py"),
    },
    "TR-026": {
        "id": "tr026-semantic-v1",
        "path": Path("qa/telegram-runtime/scripts/tr026_installed_journey_semantic_verifier.py"),
    },
}
CANONICAL_DETACHED_OWNER_ARGV = [
    "{ownerExecutablePath}",
    "--app-support-dir",
    "{appSupportDir}",
    "--config-file",
    "{configFile}",
    "--runtime-dir",
    "{runtimeDir}",
    "--lock-file",
    "{componentsLockFile}",
    "start",
    "--restart",
]
CANONICAL_ATTACHED_OWNER_ARGV = [
    ["{ownerExecutablePath}", "{command}"],
    ["{ownerExecutablePath}", "{command}", "--restart"],
    [
        "{ownerExecutablePath}",
        "--app-support-dir",
        "{appSupportDir}",
        "--config-file",
        "{configFile}",
        "--runtime-dir",
        "{runtimeDir}",
        "--lock-file",
        "{componentsLockFile}",
        "{command}",
    ],
    [
        "{ownerExecutablePath}",
        "--app-support-dir",
        "{appSupportDir}",
        "--config-file",
        "{configFile}",
        "--runtime-dir",
        "{runtimeDir}",
        "--lock-file",
        "{componentsLockFile}",
        "{command}",
        "--restart",
    ],
    [
        "{ownerExecutablePath}",
        "--app-support-dir",
        "{appSupportDir}",
        "--config-file",
        "{configFile}",
        "--runtime-dir",
        "{runtimeDir}",
        "{command}",
    ],
]
CANONICAL_ATTACHED_FLAG_OPTIONS = [
    "--start",
    "--restart",
    "--skip-livekit",
    "--skip-librechat",
    "--skip-playground",
    "--modern-playground",
    "--classic-playground",
    "--skip-voice-gateway",
    "--skip-google-mcp",
    "--skip-ms365-mcp",
    "--skip-scheduling-mcp",
    "--skip-glasshive",
    "--skip-rag-api",
    "--skip-skyvern",
    "--skip-code-interpreter",
    "--skip-firecrawl",
    "--skip-prompt-workbench",
    "--skip-telegram",
    "--skip-v1-agent",
    "--skip-docker",
    "--skip-health-checks",
    "--skip-v1-sync",
    "--skip-voice-deps",
    "--skip-mcp-verify",
    "--no-bootstrap",
    "--private-overlay",
    "--fast",
    "--profile=isolated",
    "--profile=compat",
]
CANONICAL_ATTACHED_ENUM_OPTIONS = {
    "--profile": ["isolated", "compat"],
    "--runtime-profile": ["isolated", "compat"],
}
CANONICAL_PROCESS_WRAPPERS = [
    "",
    "/bin/bash ",
    "/bin/sh ",
    "/bin/zsh ",
    "/usr/bin/env bash ",
    "bash ",
    "sh ",
    "zsh ",
]
INSTALLED_ARTIFACT_HASH_KEYS = (
    "componentsLockSha256",
    "nestedRevisionsHash",
    "prebuiltSourceSha256",
    "prebuiltBinarySha256",
    "promptBundleSha256",
    "runtimeEnvSha256",
    "libreChatConfigSha256",
    "frontendBuildSha256",
    "apiBuildSha256",
    "runningServiceSha256",
    "runtimeServiceManifestSha256",
    "runtimeOwnerExecutableSha256",
    "ownerCommandContractSha256",
)
QA_RECEIPT_ARTIFACT_CLAIM_FIELDS = {
    "PWK-UC-015": (
        "runningServiceSha256",
        "frontendBuildSha256",
        "apiBuildSha256",
        "promptBundleSha256",
        "runtimeEnvSha256",
    ),
}
READINESS_IDENTITY_HASH_KEYS = (
    "factsSha256",
    "storagePolicySha256",
    "storageMeasurementSha256",
)
TABLE_CATALOGS = (
    ("qa/parallel-orchestrator/cases.md", re.compile(r"PWK-.+"), "CATALOG-PWK"),
    ("qa/release-readiness/cases.md", re.compile(r"REL-.+"), "CATALOG-REL"),
)
CROSS_OWNER_TABLE_CASES = (
    ("qa/emotional-cortex/cases.md", "EMO-UC-047"),
    ("qa/emotional-cortex/cases.md", "EMO-UC-048"),
    ("qa/telegram-document-attachments/cases.md", "TGDOC-010"),
)
CROSS_OWNER_DETAIL_CASES = (
    ("qa/telegram-runtime/cases.md", "TR-026"),
    ("qa/modern-playground-voice/cases.md", "MPV-061"),
)
STATUS_HEADERS = {"current status", "last run", "latest result", "status"}
STATUS_PREFIX = re.compile(
    r"^\s*(?:(?:\d{4}-\d{2}-\d{2})(?:\s+(?:local|UTC))?\s*(?:/\s*)?)*"
    r"(?:NOT YET RUN|NOT RUN|PENDING|FAIL|BLOCKED|PARTIAL|PASS)\b"
)


@dataclass(frozen=True)
class GateRecord:
    case_id: str
    status: str
    source: str
    detail: str


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class ExternalReleaseAttestationAuthority:
    """Publisher-verified trust input and an independently protected witness.

    ``expected_policy_sha256`` comes from the publisher-signed, root-protected
    system bootstrap. Its independently provisioned provider must own the
    protected witness. Runtime files and environment variables are not roots.
    """

    expected_policy_sha256: str
    ledger_path: Path
    ledger_witness: object


@dataclass(frozen=True)
class GateEvaluation:
    mode: str
    label: str
    release_ready: bool
    exposure_allowed: bool
    local_qa_override: bool
    source_defaults_valid: bool
    gates: tuple[GateRecord, ...]
    open_gates: tuple[GateRecord, ...]
    readiness_checks: tuple[ReadinessCheck, ...]
    blocking_checks: tuple[ReadinessCheck, ...]
    readiness_facts: dict[str, object]
    artifact_checks: tuple[ReadinessCheck, ...]
    blocking_artifact_checks: tuple[ReadinessCheck, ...]
    artifact_identity: dict[str, object]
    qa_receipt_summary: dict[str, object]
    owner_binding: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        def public_gate(gate: GateRecord) -> dict[str, object]:
            return {
                "case_id": gate.case_id,
                "status": gate.status,
                "source": gate.source,
                "detail": "[redacted]",
            }

        return {
            "contract_version": CONTRACT_VERSION,
            "mode": self.mode,
            "label": self.label,
            "release_ready": self.release_ready,
            "exposure_allowed": self.exposure_allowed,
            "local_qa_override": self.local_qa_override,
            "source_defaults_valid": self.source_defaults_valid,
            "gate_count": len(self.gates),
            "open_gate_count": len(self.open_gates),
            "gates": [public_gate(gate) for gate in self.gates],
            "open_gates": [public_gate(gate) for gate in self.open_gates],
            "readiness_checks": [asdict(check) for check in self.readiness_checks],
            "blocking_checks": [asdict(check) for check in self.blocking_checks],
            "readiness_facts": self.readiness_facts,
            "artifact_checks": [asdict(check) for check in self.artifact_checks],
            "blocking_artifact_checks": [
                asdict(check) for check in self.blocking_artifact_checks
            ],
            "artifact_identity": self.artifact_identity,
            "qa_receipt_summary": self.qa_receipt_summary,
            "owner_binding": self.owner_binding,
        }


def _normalize_status(value: str) -> str:
    # Catalog status markers are uppercase. Keep prose such as "fail-closed" from
    # becoming a result, and let any open marker override PASS in mixed evidence.
    patterns = (
        ("FAIL", r"\bFAIL\b"),
        ("BLOCKED", r"\bBLOCKED\b"),
        ("PARTIAL", r"\bPARTIAL\b"),
        ("NOT_RUN", r"\b(?:NOT YET RUN|NOT RUN|PENDING)\b"),
        ("PASS", r"\bPASS\b"),
    )
    for status, pattern in patterns:
        if re.search(pattern, value) is not None:
            return status
    return "UNKNOWN"


def _markdown_cells(line: str) -> list[str]:
    if not line.lstrip().startswith("|"):
        return []
    content = line.strip().strip("|")
    cells: list[str] = []
    cell: list[str] = []
    escaped = False
    in_code = False
    for character in content:
        if character == "|" and not escaped and not in_code:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(character)
        if character == "`" and not escaped:
            in_code = not in_code
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
    cells.append("".join(cell).strip())
    return cells


def _status_header_index(cells: Sequence[str]) -> int | None:
    for index, cell in enumerate(cells):
        normalized = re.sub(r"[^a-z]+", " ", cell.lower()).strip()
        if normalized in STATUS_HEADERS:
            return index
    return None


def _status_detail(cells: Sequence[str], status_index: int | None) -> str:
    if status_index is None:
        return "status column missing"
    if status_index >= len(cells):
        return "status cell missing"
    first_status_cell = cells[status_index]
    if STATUS_PREFIX.search(first_status_cell) is None:
        return first_status_cell
    return " | ".join(cells[status_index:])


def _case_id(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _table_records(
    path: Path,
    pattern: re.Pattern[str],
    *,
    source: str | None = None,
    catalog_id: str | None = None,
) -> list[GateRecord]:
    public_source = source or path.name
    if not path.is_file():
        return [
            GateRecord(
                catalog_id or f"CATALOG-{pattern.pattern}",
                "MISSING",
                public_source,
                "catalog missing",
            )
        ]
    records: list[GateRecord] = []
    status_index: int | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _markdown_cells(line)
        if not cells:
            status_index = None
            continue
        if len(cells) < 2:
            continue
        case_id = _case_id(cells[0])
        if pattern.fullmatch(case_id):
            detail = _status_detail(cells, status_index)
            records.append(
                GateRecord(case_id, _normalize_status(detail), public_source, detail)
            )
            continue
        header_index = _status_header_index(cells)
        if header_index is not None:
            status_index = header_index
    if not records and catalog_id:
        return [
            GateRecord(
                catalog_id, "MISSING", public_source, "required catalog has no cases"
            )
        ]
    return records


def _exact_table_record(path: Path, expected_id: str, source: str) -> GateRecord:
    records = _table_records(path, re.compile(re.escape(expected_id)), source=source)
    if len(records) == 1 and records[0].case_id == expected_id:
        return records[0]
    if len(records) > 1:
        raise ValueError(f"duplicate release gate {expected_id} in {source}")
    return GateRecord(expected_id, "MISSING", source, "required case missing")


def _detail_record(path: Path, expected_id: str, source: str) -> GateRecord:
    if not path.is_file():
        return GateRecord(
            expected_id, "MISSING", source, "required case catalog missing"
        )
    text = path.read_text(encoding="utf-8")
    headings = list(
        re.finditer(
            rf"^(?P<level>#{{2,6}})\s+(?:Case\s+)?{re.escape(expected_id)}\b.*$",
            text,
            flags=re.MULTILINE,
        )
    )
    if len(headings) > 1:
        raise ValueError(f"duplicate release gate {expected_id} in {source}")
    if not headings:
        return GateRecord(expected_id, "MISSING", source, "required case missing")
    heading = headings[0]
    heading_level = len(heading.group("level"))
    next_heading = re.search(
        rf"^#{{2,{heading_level}}}\s+",
        text[heading.end() :],
        flags=re.MULTILINE,
    )
    end = heading.end() + next_heading.start() if next_heading else len(text)
    section = text[heading.end() : end]
    last_run = re.search(
        r"^\s*-\s*(?:\*\*)?Last\s+run\s*:(?:\*\*)?\s*(.+)$",
        section,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if last_run is None:
        return GateRecord(expected_id, "UNKNOWN", source, "Last run missing")
    detail = last_run.group(1).strip()
    return GateRecord(expected_id, _normalize_status(detail), source, detail)


def _yaml_scalar(text: str, target_path: Sequence[str]) -> str | None:
    stack: list[tuple[int, str]] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_-]+):(?:\s*(.*))?$", line)
        if match is None:
            continue
        indent = len(match.group(1).replace("\t", "    "))
        key = match.group(2)
        raw_value = (match.group(3) or "").split(" #", 1)[0].strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = tuple(item[1] for item in stack) + (key,)
        if path == tuple(target_path):
            return raw_value.strip("'\"") or None
        if not raw_value:
            stack.append((indent, key))
    return None


def _source_default_records(root: Path) -> tuple[bool, list[GateRecord]]:
    schema_path = root / "config.schema.yaml"
    if not schema_path.is_file():
        missing = GateRecord(
            "SOURCE-DEFAULT-SCHEMA",
            "MISSING",
            "config.schema.yaml",
            "config schema missing",
        )
        return False, [missing]
    text = schema_path.read_text(encoding="utf-8")
    base = (
        "properties",
        "integrations",
        "properties",
        "glasshive",
        "properties",
        "orchestration",
        "properties",
    )
    available = _yaml_scalar(text, base + ("available", "default"))
    mode = _yaml_scalar(text, base + ("default_mode", "default"))
    failures: list[GateRecord] = []
    if available not in {"false", "true"}:
        failures.append(
            GateRecord(
                "SOURCE-DEFAULT-AVAILABLE",
                "FAIL",
                "config.schema.yaml",
                f"expected a boolean, found {available or 'missing'}",
            )
        )
    if mode not in {"focused", "parallel"}:
        failures.append(
            GateRecord(
                "SOURCE-DEFAULT-MODE",
                "FAIL",
                "config.schema.yaml",
                f"expected focused or parallel, found {mode or 'missing'}",
            )
        )
    return not failures, failures


def _safe_reason(value: object, fallback: str) -> str:
    reason = str(value or "").strip().lower()
    return reason if re.fullmatch(r"[a-z0-9_.-]{1,120}", reason) else fallback


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return ""


def _canonical_hash(value: object) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def build_prompt_registry_facts(prompt_bundle: object) -> dict[str, object]:
    """Derive the typed prompt-layer fact from an exact compiled registry bundle."""

    bundle = prompt_bundle if isinstance(prompt_bundle, dict) else {}
    prompts = bundle.get("prompts")
    prompt_count = bundle.get("prompt_count")
    projection: list[dict[str, object]] = []
    unknown_layers: set[str] = set()
    layer_names: set[str] = set()
    if isinstance(prompts, dict):
        for prompt_id, value in sorted(prompts.items()):
            entry = value if isinstance(value, dict) else {}
            metadata = (
                entry.get("metadata")
                if isinstance(entry.get("metadata"), dict)
                else {}
            )
            owner_layer = str(metadata.get("owner_layer") or "").strip()
            if SAFE_NAME.fullmatch(owner_layer):
                layer_names.add(owner_layer)
            else:
                unknown_layers.add("invalid")
            projection.append(
                {
                    "id": str(prompt_id),
                    "contentHash": str(entry.get("content_hash") or ""),
                    "ownerLayer": owner_layer,
                    "status": str(metadata.get("status") or ""),
                    "version": metadata.get("version"),
                }
            )
    valid_registry = (
        bundle.get("schema_version") == CONTRACT_VERSION
        and isinstance(prompt_count, int)
        and not isinstance(prompt_count, bool)
        and prompt_count > 0
        and isinstance(prompts, dict)
        and prompt_count == len(prompts)
        and not unknown_layers
        and all(
            item["id"]
            and item["contentHash"]
            and item["status"] in {"active", "draft", "deprecated"}
            and isinstance(item["version"], int)
            and not isinstance(item["version"], bool)
            and int(item["version"]) > 0
            for item in projection
        )
    )
    return {
        "contractVersion": CONTRACT_VERSION,
        "producerScope": PROMPT_PRODUCER_SCOPE,
        "status": "verified" if valid_registry else "unknown",
        "unknownLayerCount": len(unknown_layers),
        "unknownLayerNames": sorted(unknown_layers),
        "promptCount": prompt_count if isinstance(prompt_count, int) else 0,
        "layerCount": len(layer_names),
        "layerNames": sorted(layer_names),
        "registryHash": _canonical_hash(projection),
        **({} if valid_registry else {"reason": "prompt_registry_invalid"}),
    }


def _installed_prompt_registry_facts(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return build_prompt_registry_facts(bundle)


def _git_environment() -> dict[str, str]:
    """Return a fixed Git environment with no ambient repository/config inputs."""

    return {
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PAGER": "cat",
        "PATH": "/usr/bin:/bin",
        "XDG_CONFIG_HOME": "/var/empty",
    }


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )


def _stat_identity(details: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        details.st_dev,
        details.st_ino,
        details.st_mode,
        details.st_size,
        details.st_mtime_ns,
        details.st_ctime_ns,
    )


def _open_bound_directory(root: Path) -> tuple[Path, int, os.stat_result] | None:
    descriptor: int | None = None
    try:
        exact_root = Path(root).expanduser().resolve(strict=True)
        descriptor = os.open(exact_root, _directory_open_flags())
        opened = os.fstat(descriptor)
        named = os.stat(exact_root, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or _stat_identity(opened) != _stat_identity(named)
        ):
            os.close(descriptor)
            return None
        return exact_root, descriptor, opened
    except (OSError, RuntimeError, ValueError):
        if descriptor is not None:
            os.close(descriptor)
        return None


def _bound_directory_unchanged(
    exact_root: Path,
    descriptor: int,
    opened: os.stat_result,
) -> bool:
    try:
        current = os.fstat(descriptor)
        named = os.stat(exact_root, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(current.st_mode)
        and _stat_identity(current) == _stat_identity(opened)
        and _stat_identity(named) == _stat_identity(opened)
    )


def _git_bytes(
    root: Path,
    *args: str,
    max_output_bytes: int = MAX_WORKTREE_HASH_BYTES,
    root_descriptor: int | None = None,
) -> tuple[bool, bytes]:
    """Run trusted Git with bounded streaming output against one opened root."""

    if (
        not isinstance(max_output_bytes, int)
        or isinstance(max_output_bytes, bool)
        or not 0 <= max_output_bytes <= MAX_WORKTREE_HASH_BYTES
    ):
        return False, b""
    owned_descriptor: int | None = None
    process: subprocess.Popen[bytes] | None = None
    selector: selectors.BaseSelector | None = None
    try:
        if root_descriptor is None:
            bound = _open_bound_directory(root)
            if bound is None:
                return False, b""
            _exact_root, owned_descriptor, _opened = bound
            root_descriptor = owned_descriptor
        command = [
            TRUSTED_GIT_EXECUTABLE,
            "-c",
            "color.ui=false",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.preloadIndex=false",
            "-c",
            "core.untrackedCache=false",
            "--git-dir=.git",
            "--work-tree=.",
            *args,
        ]
        process = subprocess.Popen(
            command,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(root_descriptor,),
            preexec_fn=lambda: os.fchdir(root_descriptor),
        )
        if process.stdout is None:
            return False, b""
        output = bytearray()
        deadline = time.monotonic() + GIT_COMMAND_TIMEOUT_SECONDS
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                return False, b""
            events = selector.select(remaining_time)
            if not events:
                return False, b""
            for key, _mask in events:
                remaining_capacity = max_output_bytes - len(output)
                chunk = os.read(
                    key.fileobj.fileno(),
                    min(WORKTREE_HASH_CHUNK_BYTES, remaining_capacity + 1),
                )
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if len(chunk) > remaining_capacity:
                    return False, b""
                output.extend(chunk)
        remaining_time = deadline - time.monotonic()
        if remaining_time <= 0:
            return False, b""
        process.wait(timeout=remaining_time)
        if process.returncode != 0:
            return False, b""
        return True, bytes(output)
    except (OSError, subprocess.SubprocessError, ValueError):
        return False, b""
    finally:
        if selector is not None:
            selector.close()
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=1)
                except (OSError, subprocess.SubprocessError):
                    pass
        if owned_descriptor is not None:
            os.close(owned_descriptor)


def _git_output(root: Path, *args: str) -> tuple[bool, str]:
    ok, output = _git_bytes(root, *args, max_output_bytes=MAX_GIT_REVISION_BYTES)
    if not ok:
        return False, ""
    try:
        return True, output.decode("ascii").strip()
    except UnicodeDecodeError:
        return False, ""


def _hash_frame(digest: object, label: bytes, value: bytes) -> None:
    digest.update(label)
    digest.update(struct.pack(">Q", len(value)))
    digest.update(value)


def _nul_paths(value: bytes) -> tuple[bytes, ...] | None:
    if value and not value.endswith(b"\0"):
        return None
    paths = tuple(path for path in value.split(b"\0") if path)
    if len(paths) > MAX_WORKTREE_HASH_FILES:
        return None
    if any(
        path.startswith(b"/")
        or any(part in {b"", b".", b".."} for part in path.split(b"/"))
        for path in paths
    ):
        return None
    return paths


def _anchored_path_identity(
    root_descriptor: int,
    parts: tuple[bytes, ...],
) -> tuple[
    tuple[tuple[int, int, int, int, int, int], ...],
    tuple[int, int, int, int, int, int] | None,
] | None:
    descriptor: int | None = None
    ancestors: list[tuple[int, int, int, int, int, int]] = []
    try:
        descriptor = os.dup(root_descriptor)
        for part in parts[:-1]:
            next_descriptor = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            details = os.fstat(descriptor)
            if not stat.S_ISDIR(details.st_mode):
                return None
            ancestors.append(_stat_identity(details))
        try:
            final = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            final_identity = None
        else:
            final_identity = _stat_identity(final)
        return tuple(ancestors), final_identity
    except OSError:
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _open_anchored_parent(root_descriptor: int, parts: tuple[bytes, ...]) -> int | None:
    descriptor: int | None = None
    try:
        descriptor = os.dup(root_descriptor)
        for part in parts[:-1]:
            next_descriptor = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        return None


def _hash_worktree_path(
    digest: object,
    root_descriptor: int,
    relative: bytes,
    remaining_bytes: int,
) -> int | None:
    parts = tuple(relative.split(b"/"))
    before = _anchored_path_identity(root_descriptor, parts)
    if before is None:
        return None
    _ancestors, final_identity = before
    if final_identity is None:
        if _anchored_path_identity(root_descriptor, parts) != before:
            return None
        _hash_frame(digest, b"missing\0", relative)
        return remaining_bytes

    parent_descriptor = _open_anchored_parent(root_descriptor, parts)
    if parent_descriptor is None:
        return None
    descriptor: int | None = None
    consumed = 0
    try:
        metadata = os.stat(parts[-1], dir_fd=parent_descriptor, follow_symlinks=False)
        if _stat_identity(metadata) != final_identity:
            return None
        _hash_frame(digest, b"path\0", relative)
        digest.update(struct.pack(">I", metadata.st_mode & 0xFFFFFFFF))
        if stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(parts[-1], dir_fd=parent_descriptor)
            if not isinstance(target, bytes) or len(target) > remaining_bytes:
                return None
            _hash_frame(digest, b"symlink\0", target)
            consumed = len(target)
        elif stat.S_ISDIR(metadata.st_mode):
            digest.update(b"directory\0")
        elif stat.S_ISREG(metadata.st_mode) and metadata.st_size <= remaining_bytes:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
                os, "O_NOFOLLOW", 0
            )
            descriptor = os.open(parts[-1], flags, dir_fd=parent_descriptor)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or _stat_identity(opened) != final_identity:
                return None
            digest.update(b"regular\0")
            digest.update(struct.pack(">Q", opened.st_size))
            while True:
                chunk = os.read(descriptor, WORKTREE_HASH_CHUNK_BYTES)
                if not chunk:
                    break
                consumed += len(chunk)
                if consumed > remaining_bytes:
                    return None
                digest.update(chunk)
            if (
                consumed != opened.st_size
                or _stat_identity(os.fstat(descriptor)) != final_identity
            ):
                return None
        else:
            return None
    except OSError:
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)
    if _anchored_path_identity(root_descriptor, parts) != before:
        return None
    return remaining_bytes - consumed


def _hidden_index_flags(value: bytes) -> bool | None:
    if value and not value.endswith(b"\0"):
        return None
    for entry in (item for item in value.split(b"\0") if item):
        if len(entry) < 3 or entry[1:2] != b" ":
            return None
        tag = entry[0]
        if tag == ord("S") or ord("a") <= tag <= ord("z"):
            return True
    return False


def _git_sample(
    root: Path,
    root_descriptor: int,
    *,
    ignore_submodules: bool,
) -> dict[str, object] | None:
    remaining = MAX_WORKTREE_HASH_BYTES
    digest = hashlib.sha256()
    digest.update(b"viventium-git-sample-v3\0")

    def capture(
        label: bytes,
        command: Sequence[str],
        limit: int | None = None,
    ) -> bytes | None:
        nonlocal remaining
        command_limit = remaining if limit is None else min(remaining, limit)
        ok, output = _git_bytes(
            root,
            *command,
            max_output_bytes=command_limit,
            root_descriptor=root_descriptor,
        )
        if not ok or len(output) > remaining:
            return None
        remaining -= len(output)
        _hash_frame(digest, label, output)
        return output

    revision_output = capture(
        b"revision\0",
        ("rev-parse", "--verify", "HEAD"),
        MAX_GIT_REVISION_BYTES,
    )
    if revision_output is None:
        return None
    try:
        revision = revision_output.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        return None

    status_args = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if ignore_submodules:
        status_args.append("--ignore-submodules=all")
    status = capture(b"status\0", status_args)
    if status is None or (status and not status.endswith(b"\0")):
        return None

    index_flags = capture(b"index-flags\0", ("ls-files", "-v", "-z"))
    hidden_flags = _hidden_index_flags(index_flags) if index_flags is not None else None
    if hidden_flags is None:
        return None

    paths: set[bytes] = set()
    diff_common = ["--name-only", "-z", "--no-ext-diff", "--no-textconv"]
    if ignore_submodules:
        diff_common.append("--ignore-submodules=all")
    path_commands = (
        ("diff", *diff_common, "--cached", "HEAD", "--"),
        ("diff", *diff_common, "--"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    )
    for index, command in enumerate(path_commands):
        output = capture(f"paths-{index}\0".encode("ascii"), command)
        parsed = _nul_paths(output) if output is not None else None
        if parsed is None:
            return None
        paths.update(parsed)
        if len(paths) > MAX_WORKTREE_HASH_FILES:
            return None

    index_state = capture(b"index\0", ("ls-files", "--stage", "-z"))
    if index_state is None or (index_state and not index_state.endswith(b"\0")):
        return None
    return {
        "revision": revision,
        "dirty": bool(status),
        "hiddenIndexFlags": hidden_flags,
        "fingerprint": digest.hexdigest(),
        "paths": tuple(sorted(paths)),
        "remainingBytes": remaining,
    }


def _dirty_worktree_hash(root_descriptor: int, sample: dict[str, object]) -> str:
    fingerprint = str(sample.get("fingerprint") or "")
    paths = sample.get("paths")
    remaining = sample.get("remainingBytes")
    if (
        SHA256.fullmatch(fingerprint) is None
        or not isinstance(paths, tuple)
        or not isinstance(remaining, int)
        or isinstance(remaining, bool)
        or remaining < 0
    ):
        return ""
    digest = hashlib.sha256()
    digest.update(b"viventium-worktree-identity-v3\0")
    _hash_frame(digest, b"git-sample\0", fingerprint.encode("ascii"))
    for relative in paths:
        if not isinstance(relative, bytes):
            return ""
        remaining_result = _hash_worktree_path(
            digest,
            root_descriptor,
            relative,
            remaining,
        )
        if remaining_result is None:
            return ""
        remaining = remaining_result
    return digest.hexdigest()


def _git_identity(root: Path, *, ignore_submodules: bool = False) -> dict[str, object]:
    bound = _open_bound_directory(root)
    if bound is None:
        return {"revision": "", "clean": False, "worktreeHash": ""}
    exact_root, root_descriptor, opened = bound
    revision = ""
    try:
        first = _git_sample(
            exact_root,
            root_descriptor,
            ignore_submodules=ignore_submodules,
        )
        if first is None:
            return {"revision": "", "clean": False, "worktreeHash": ""}
        revision = str(first["revision"])
        if first["hiddenIndexFlags"] is True:
            return {"revision": revision, "clean": False, "worktreeHash": ""}
        first_hash = (
            _dirty_worktree_hash(root_descriptor, first)
            if first["dirty"] is True
            else _sha256_bytes(b"")
        )
        second = _git_sample(
            exact_root,
            root_descriptor,
            ignore_submodules=ignore_submodules,
        )
        if second is None or second["hiddenIndexFlags"] is True:
            return {"revision": revision, "clean": False, "worktreeHash": ""}
        second_hash = (
            _dirty_worktree_hash(root_descriptor, second)
            if second["dirty"] is True
            else _sha256_bytes(b"")
        )
        stable = (
            _bound_directory_unchanged(exact_root, root_descriptor, opened)
            and first["revision"] == second["revision"]
            and first["dirty"] == second["dirty"]
            and first["fingerprint"] == second["fingerprint"]
            and first_hash == second_hash
            and SHA256.fullmatch(first_hash) is not None
        )
        if not stable:
            return {"revision": revision, "clean": False, "worktreeHash": ""}
        return {
            "revision": revision,
            "clean": first["dirty"] is False,
            "worktreeHash": first_hash,
        }
    except (OSError, RuntimeError, TypeError, ValueError):
        return {"revision": revision, "clean": False, "worktreeHash": ""}
    finally:
        os.close(root_descriptor)


def _normalized_process_value(value: object) -> str:
    return " ".join(str(value or "").split())


def _owner_binding_sha256(payload: dict[str, object]) -> str:
    binding = {
        key: payload.get(key)
        for key in (
            "contractVersion",
            "repoRoot",
            "appSupportDir",
            "configFile",
            "runtimeDir",
            "componentsLockFile",
            "runtimeProfile",
            "command",
            "ownerLaunchMode",
            "ownerPid",
            "ownerExecutablePath",
            "ownerProcessCwd",
            "ownerProcessStartedAt",
            "ownerProcessCommand",
        )
    }
    return _sha256_bytes(
        json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _macos_process_cwd(pid: int) -> Path | None:
    """Read a process CWD from the macOS kernel without scanning open files."""

    class VinfoStat(ctypes.Structure):
        _fields_ = [
            ("vst_dev", ctypes.c_uint32),
            ("vst_mode", ctypes.c_uint16),
            ("vst_nlink", ctypes.c_uint16),
            ("vst_ino", ctypes.c_uint64),
            ("vst_uid", ctypes.c_uint32),
            ("vst_gid", ctypes.c_uint32),
            ("vst_atime", ctypes.c_int64),
            ("vst_atimensec", ctypes.c_int64),
            ("vst_mtime", ctypes.c_int64),
            ("vst_mtimensec", ctypes.c_int64),
            ("vst_ctime", ctypes.c_int64),
            ("vst_ctimensec", ctypes.c_int64),
            ("vst_birthtime", ctypes.c_int64),
            ("vst_birthtimensec", ctypes.c_int64),
            ("vst_size", ctypes.c_int64),
            ("vst_blocks", ctypes.c_int64),
            ("vst_blksize", ctypes.c_int32),
            ("vst_flags", ctypes.c_uint32),
            ("vst_gen", ctypes.c_uint32),
            ("vst_rdev", ctypes.c_uint32),
            ("vst_qspare", ctypes.c_int64 * 2),
        ]

    class VnodeInfo(ctypes.Structure):
        _fields_ = [
            ("vi_stat", VinfoStat),
            ("vi_type", ctypes.c_int),
            ("vi_pad", ctypes.c_int),
            ("vi_fsid", ctypes.c_int32 * 2),
        ]

    class VnodeInfoPath(ctypes.Structure):
        _fields_ = [
            ("vip_vi", VnodeInfo),
            ("vip_path", ctypes.c_char * 1024),
        ]

    class ProcVnodePathInfo(ctypes.Structure):
        _fields_ = [
            ("pvi_cdir", VnodeInfoPath),
            ("pvi_rdir", VnodeInfoPath),
        ]

    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        libproc.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        libproc.proc_pidinfo.restype = ctypes.c_int
        info = ProcVnodePathInfo()
        returned = libproc.proc_pidinfo(
            pid,
            9,  # PROC_PIDVNODEPATHINFO
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if returned != ctypes.sizeof(info):
            return None
        raw_path = bytes(info.pvi_cdir.vip_path).split(b"\0", 1)[0]
        if not raw_path:
            return None
        return Path(os.fsdecode(raw_path)).expanduser().resolve(strict=True)
    except (AttributeError, OSError, RuntimeError, ValueError):
        return None


def _process_cwd(pid: int) -> Path | None:
    if sys.platform == "darwin":
        kernel_cwd = _macos_process_cwd(pid)
        if kernel_cwd is not None:
            return kernel_cwd
    try:
        completed = subprocess.run(
            ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    paths = [line[1:] for line in completed.stdout.splitlines() if line.startswith("n")]
    if completed.returncode != 0 or len(paths) != 1 or not paths[0]:
        return None
    try:
        return Path(paths[0]).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _resolve_macos_process_executable(pid: int, raw_executable: str) -> Path | None:
    """Resolve a kernel-reported executable, including cwd-relative launch paths."""

    try:
        executable = Path(raw_executable)
        if not executable.is_absolute():
            process_cwd = _macos_process_cwd(pid)
            if process_cwd is None:
                return None
            executable = process_cwd / executable
        return executable.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None


def _macos_process_argv(pid: int) -> tuple[Path, tuple[str, ...]] | None:
    """Read the kernel-owned executable and argv without trusting process titles."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, pid
        size = ctypes.c_size_t()
        if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0 or size.value < 8:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
            return None
        raw = buffer.raw[: size.value]
        argc = int.from_bytes(raw[:4], byteorder=sys.byteorder, signed=True)
        if argc <= 0 or argc > 4096:
            return None
        position = 4
        executable_end = raw.index(b"\0", position)
        executable = _resolve_macos_process_executable(
            pid, os.fsdecode(raw[position:executable_end])
        )
        if executable is None:
            return None
        position = executable_end
        while position < len(raw) and raw[position] == 0:
            position += 1
        argv: list[str] = []
        for _ in range(argc):
            argument_end = raw.index(b"\0", position)
            argv.append(os.fsdecode(raw[position:argument_end]))
            position = argument_end + 1
        return executable, tuple(argv)
    except (AttributeError, OSError, RuntimeError, ValueError):
        return None


def _live_process_image_and_argv(pid: int) -> tuple[Path, tuple[str, ...]] | None:
    """Return typed kernel process identity, or fail closed when it is unavailable."""

    proc_executable = Path(f"/proc/{pid}/exe")
    proc_argv = Path(f"/proc/{pid}/cmdline")
    if proc_executable.exists() and proc_argv.exists():
        try:
            executable = proc_executable.resolve(strict=True)
            argv = tuple(
                os.fsdecode(item)
                for item in proc_argv.read_bytes().split(b"\0")
                if item
            )
            return (executable, argv) if argv else None
        except (OSError, RuntimeError):
            return None
    if sys.platform == "darwin":
        return _macos_process_argv(pid)
    return None


def _script_interpreter(executable: Path) -> tuple[Path, tuple[str, ...]] | None:
    try:
        first_line = executable.read_bytes().splitlines()[0].decode("utf-8")
    except (IndexError, OSError, UnicodeDecodeError):
        return None
    if not first_line.startswith("#!"):
        return None
    tokens = tuple(first_line[2:].strip().split())
    if not tokens:
        return None
    try:
        interpreter = Path(tokens[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if interpreter == Path("/usr/bin/env").resolve():
        if len(tokens) != 2:
            return None
        resolved = shutil.which(tokens[1])
        if not resolved:
            return None
        try:
            interpreter = Path(resolved).resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        return interpreter, (tokens[1],)
    return interpreter, (tokens[0], *tokens[1:])


def _runtime_owner_command_contract(executable: Path) -> dict[str, object] | None:
    try:
        repo_root = executable.expanduser().resolve(strict=True).parents[1]
        contract_path = (
            repo_root
            / "scripts"
            / "viventium"
            / "runtime_owner_command_contract.json"
        ).resolve(strict=True)
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, IndexError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("contractVersion") != CONTRACT_VERSION:
        return None
    detached = payload.get("detached")
    attached = payload.get("attached")
    wrappers = payload.get("processWrappers")
    if (
        not isinstance(detached, dict)
        or detached.get("command") != "start"
        or detached.get("allowTrailingArguments") is not False
        or not isinstance(detached.get("argvTemplate"), list)
        or not all(isinstance(item, str) and item for item in detached["argvTemplate"])
        or not isinstance(attached, dict)
        or attached.get("allowTrailingArguments") is not False
        or attached.get("commands") != ["start", "launch"]
        or not isinstance(attached.get("argvTemplates"), list)
        or not attached["argvTemplates"]
        or not all(
            isinstance(template, list)
            and template
            and all(isinstance(item, str) and item for item in template)
            for template in attached["argvTemplates"]
        )
        or not isinstance(wrappers, list)
        or not wrappers
        or not all(isinstance(wrapper, str) for wrapper in wrappers)
        or len(set(wrappers)) != len(wrappers)
        or detached.get("argvTemplate") != CANONICAL_DETACHED_OWNER_ARGV
        or attached.get("argvTemplates") != CANONICAL_ATTACHED_OWNER_ARGV
        or attached.get("flagOptions") != CANONICAL_ATTACHED_FLAG_OPTIONS
        or attached.get("enumOptions") != CANONICAL_ATTACHED_ENUM_OPTIONS
        or wrappers != CANONICAL_PROCESS_WRAPPERS
    ):
        return None
    return payload


def _format_owner_command_template(
    template: object,
    values: dict[str, str],
) -> str | None:
    if not isinstance(template, list):
        return None
    try:
        tokens = [str(token).format_map(values) for token in template]
    except (KeyError, ValueError):
        return None
    return " ".join(tokens) if tokens and all(tokens) else None


def _format_owner_argv_template(
    template: object,
    values: dict[str, str],
) -> tuple[str, ...] | None:
    if not isinstance(template, list):
        return None
    try:
        tokens = tuple(str(token).format_map(values) for token in template)
    except (KeyError, ValueError):
        return None
    return tokens if tokens and all(tokens) else None


def _owner_executable_aliases(
    executable: Path,
    cwd: Path,
    launch_mode: str,
) -> tuple[str, ...]:
    absolute = str(executable)
    if launch_mode != "attached":
        return (absolute,)
    try:
        relative = executable.relative_to(cwd).as_posix()
    except ValueError:
        return (absolute,)
    return (absolute, relative, f"./{relative}")


def _owner_process_image_executes(
    pid: int,
    executable: Path,
    cwd: Path,
    command_name: str,
    *,
    app_support: Path,
    config_file: Path,
    runtime_dir: Path,
    components_lock_file: Path,
    launch_mode: str,
    runtime_profile: str | None = None,
) -> bool:
    live = _live_process_image_and_argv(pid)
    contract = _runtime_owner_command_contract(executable)
    if live is None or contract is None:
        return False
    live_image, live_argv = live
    values = {
        "ownerExecutablePath": str(executable),
        "appSupportDir": str(app_support),
        "configFile": str(config_file),
        "runtimeDir": str(runtime_dir),
        "componentsLockFile": str(components_lock_file),
        "command": command_name,
    }
    if launch_mode == "detached":
        detached = contract["detached"]
        assert isinstance(detached, dict)
        if command_name != detached.get("command") or cwd != executable.parents[1]:
            return False
        templates = (detached.get("argvTemplate"),)
    elif launch_mode == "attached":
        attached = contract["attached"]
        assert isinstance(attached, dict)
        if command_name not in attached.get("commands", []):
            return False
        templates = tuple(attached.get("argvTemplates", []))
    else:
        return False
    executable_aliases = _owner_executable_aliases(executable, cwd, launch_mode)
    expected_argv = tuple(
        (alias, *formatted[1:])
        for formatted in (
            _format_owner_argv_template(template, values) for template in templates
        )
        if formatted is not None and formatted[0] == str(executable)
        for alias in executable_aliases
    )
    interpreter = _script_interpreter(executable)
    allowed_interpreters: set[Path] = set()
    if interpreter is not None:
        allowed_interpreters.add(interpreter[0])
    wrappers = contract.get("processWrappers")
    if isinstance(wrappers, list):
        for wrapper in wrappers:
            try:
                wrapper_tokens = shlex.split(str(wrapper).strip())
                if not wrapper_tokens:
                    continue
                command = wrapper_tokens[-1] if wrapper_tokens[0] == "/usr/bin/env" else wrapper_tokens[0]
                resolved = shutil.which(command) if not Path(command).is_absolute() else command
                if resolved:
                    allowed_interpreters.add(Path(resolved).resolve(strict=True))
            except (OSError, RuntimeError, ValueError):
                return False

    def matches(actual: tuple[str, ...], expected: tuple[str, ...]) -> bool:
        return actual == expected or (
            launch_mode == "attached"
            and actual[:len(expected)] == expected
            and _attached_owner_options_match(
                actual[len(expected):], contract["attached"], runtime_profile,
            )
        )

    try:
        live_image = live_image.resolve(strict=True)
        executable = executable.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if live_image == executable:
        return any(matches(live_argv, expected) for expected in expected_argv)
    if interpreter is None or live_image not in allowed_interpreters:
        return False
    return any(
        matches(live_argv[1:], expected)
        and bool(live_argv)
        and (
            live_argv[0] in interpreter[1]
            or Path(live_argv[0]).name == live_image.name
            or (
                Path(live_argv[0]).is_absolute()
                and Path(live_argv[0]).resolve() == interpreter[0]
            )
        )
        for expected in expected_argv
    )


def _attached_owner_options_match(
    tokens: tuple[str, ...], attached: dict[str, object], runtime_profile: str | None,
) -> bool:
    """Accept only typed launcher flags; never paths, shell syntax, or arbitrary tails."""
    flags = attached["flagOptions"]
    enums = attached["enumOptions"]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in flags:
            if token.startswith("--profile=") and token.partition("=")[2] != runtime_profile:
                return False
            index += 1
        elif token in enums and index + 1 < len(tokens) and tokens[index + 1] in enums[token]:
            if tokens[index + 1] != runtime_profile:
                return False
            index += 2
        else:
            return False
    return True


def _owner_command_executes(
    command: str,
    executable: Path,
    cwd: Path,
    command_name: str,
    *,
    app_support: Path,
    config_file: Path,
    runtime_dir: Path,
    components_lock_file: Path,
    launch_mode: str,
    runtime_profile: str | None = None,
) -> bool:
    """Match only a canonical attached or detached Viventium owner command."""

    normalized = _normalized_process_value(command)
    contract = _runtime_owner_command_contract(executable)
    if contract is None:
        return False
    values = {
        "ownerExecutablePath": str(executable),
        "appSupportDir": str(app_support),
        "configFile": str(config_file),
        "runtimeDir": str(runtime_dir),
        "componentsLockFile": str(components_lock_file),
        "command": command_name,
    }
    if launch_mode == "detached":
        detached = contract["detached"]
        assert isinstance(detached, dict)
        if command_name != detached.get("command") or cwd != executable.parents[1]:
            return False
        templates = (detached.get("argvTemplate"),)
    elif launch_mode == "attached":
        attached = contract["attached"]
        assert isinstance(attached, dict)
        if command_name not in attached.get("commands", []):
            return False
        templates = tuple(attached.get("argvTemplates", []))
    else:
        return False
    executable_aliases = _owner_executable_aliases(executable, cwd, launch_mode)
    bases = tuple(
        " ".join((alias, *formatted[1:]))
        for formatted in (
            _format_owner_argv_template(template, values) for template in templates
        )
        if formatted is not None and formatted[0] == str(executable)
        for alias in executable_aliases
    )
    wrappers = contract["processWrappers"]
    assert isinstance(wrappers, list)
    return any(
        normalized == f"{wrapper}{base}" or (
            launch_mode == "attached"
            and normalized.startswith(f"{wrapper}{base} ")
            and _attached_owner_options_match(
                tuple(normalized[len(f"{wrapper}{base} "):].split()),
                contract["attached"], runtime_profile,
            )
        )
        for wrapper in wrappers
        for base in bases
    )


def _runtime_owner_state_proves_active(
    installed_root: Path | None,
    runtime_owner_state: Path | None,
) -> bool:
    if installed_root is None or runtime_owner_state is None:
        return False
    try:
        installed = Path(installed_root).expanduser().resolve(strict=True)
        supplied_owner_state = Path(runtime_owner_state).expanduser()
        if supplied_owner_state.is_symlink():
            return False
        owner_state_path = supplied_owner_state.resolve(strict=True)
        owner_stat = owner_state_path.stat()
        if (
            not stat.S_ISREG(owner_stat.st_mode)
            or stat.S_IMODE(owner_stat.st_mode) != 0o600
            or (hasattr(os, "getuid") and owner_stat.st_uid != os.getuid())
        ):
            return False
        payload = json.loads(
            owner_state_path.read_text(encoding="utf-8")
        )
    except (OSError, RuntimeError, json.JSONDecodeError):
        return False
    if not installed.is_dir() or not isinstance(payload, dict):
        return False
    try:
        owner_root_value = str(payload.get("repoRoot") or "").strip()
        app_support_value = str(payload.get("appSupportDir") or "").strip()
        config_file_value = str(payload.get("configFile") or "").strip()
        runtime_dir_value = str(payload.get("runtimeDir") or "").strip()
        components_lock_value = str(payload.get("componentsLockFile") or "").strip()
        runtime_profile = str(payload.get("runtimeProfile") or "").strip()
        owner_launch_mode = str(payload.get("ownerLaunchMode") or "").strip()
        if (
            not owner_root_value
            or not app_support_value
            or not config_file_value
            or not runtime_dir_value
            or not components_lock_value
            or not SAFE_NAME.fullmatch(runtime_profile)
            or owner_launch_mode not in {"attached", "detached"}
        ):
            return False
        owner_root = Path(owner_root_value).expanduser().resolve(strict=True)
        app_support = Path(app_support_value).expanduser().resolve(strict=True)
        config_file = Path(config_file_value).expanduser().resolve(strict=True)
        runtime_dir = Path(runtime_dir_value).expanduser().resolve(strict=True)
        components_lock_file = Path(components_lock_value).expanduser().resolve(
            strict=True
        )
        owner_executable = Path(
            str(payload.get("ownerExecutablePath") or "")
        ).expanduser().resolve(strict=True)
        owner_cwd = Path(str(payload.get("ownerProcessCwd") or "")).expanduser().resolve(
            strict=True
        )
        owner_pid = int(str(payload.get("ownerPid") or ""))
    except (OSError, RuntimeError, TypeError, ValueError):
        return False
    expected_started_at = _normalized_process_value(payload.get("ownerProcessStartedAt"))
    expected_command = _normalized_process_value(payload.get("ownerProcessCommand"))
    try:
        expected_executable = (installed / "bin" / "viventium").resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    canonical_payload = {
        "contractVersion": CONTRACT_VERSION,
        "repoRoot": str(owner_root),
        "appSupportDir": str(app_support),
        "configFile": str(config_file),
        "runtimeDir": str(runtime_dir),
        "componentsLockFile": str(components_lock_file),
        "runtimeProfile": runtime_profile,
        "command": str(payload.get("command") or ""),
        "ownerLaunchMode": owner_launch_mode,
        "ownerPid": str(owner_pid),
        "ownerExecutablePath": str(owner_executable),
        "ownerProcessCwd": str(owner_cwd),
        "ownerProcessStartedAt": expected_started_at,
        "ownerProcessCommand": expected_command,
    }
    if (
        payload.get("contractVersion") != CONTRACT_VERSION
        or owner_root != installed
        or owner_executable != expected_executable
        or str(payload.get("repoRoot") or "") != str(owner_root)
        or str(payload.get("appSupportDir") or "") != str(app_support)
        or str(payload.get("configFile") or "") != str(config_file)
        or str(payload.get("runtimeDir") or "") != str(runtime_dir)
        or str(payload.get("componentsLockFile") or "")
        != str(components_lock_file)
        or runtime_dir != (app_support / "runtime").resolve(strict=True)
        or config_file.parent != app_support
        or components_lock_file != (installed / "components.lock.json").resolve(strict=True)
        or str(payload.get("ownerExecutablePath") or "") != str(owner_executable)
        or str(payload.get("ownerProcessCwd") or "") != str(owner_cwd)
        or owner_state_path
        != (app_support / "state" / "runtime" / runtime_profile / "stack-owner.json").resolve()
        or owner_pid <= 1
        or str(payload.get("command") or "") not in {"start", "launch"}
        or not expected_started_at
        or not expected_command
        or str(payload.get("ownerBindingSha256") or "")
        != _owner_binding_sha256(canonical_payload)
    ):
        return False
    try:
        started = subprocess.run(
            [TRUSTED_PROCESS_EXECUTABLE, "-p", str(owner_pid), "-o", "lstart="],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        command = subprocess.run(
            [TRUSTED_PROCESS_EXECUTABLE, "-p", str(owner_pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    live_cwd = _process_cwd(owner_pid)
    return (
        started.returncode == 0
        and command.returncode == 0
        and _normalized_process_value(started.stdout) == expected_started_at
        and _normalized_process_value(command.stdout) == expected_command
        and live_cwd == owner_cwd
        and _owner_command_executes(
            expected_command,
            expected_executable,
            owner_cwd,
            str(payload.get("command") or ""),
            app_support=app_support,
            config_file=config_file,
            runtime_dir=runtime_dir,
            components_lock_file=components_lock_file,
            launch_mode=owner_launch_mode,
            runtime_profile=runtime_profile,
        )
        and _owner_process_image_executes(
            owner_pid,
            expected_executable,
            owner_cwd,
            str(payload.get("command") or ""),
            app_support=app_support,
            config_file=config_file,
            runtime_dir=runtime_dir,
            components_lock_file=components_lock_file,
            launch_mode=owner_launch_mode,
            runtime_profile=runtime_profile,
        )
    )


def _runtime_owner_projection(
    installed_root: Path | None,
    runtime_owner_state: Path | None,
) -> dict[str, object]:
    """Return a public-safe binding to the exact live runtime owner."""

    if not _runtime_owner_state_proves_active(installed_root, runtime_owner_state):
        return {}
    assert installed_root is not None and runtime_owner_state is not None
    try:
        installed = Path(installed_root).expanduser().resolve(strict=True)
        owner_state_path = Path(runtime_owner_state).expanduser().resolve(strict=True)
        payload = json.loads(owner_state_path.read_text(encoding="utf-8"))
        runtime_dir = Path(str(payload["runtimeDir"])).expanduser().resolve(strict=True)
        config_file = Path(str(payload["configFile"])).expanduser().resolve(strict=True)
        components_lock_file = Path(str(payload["componentsLockFile"])).expanduser().resolve(
            strict=True
        )
        executable = Path(str(payload["ownerExecutablePath"])).expanduser().resolve(
            strict=True
        )
        process_cwd = Path(str(payload["ownerProcessCwd"])).expanduser().resolve(
            strict=True
        )
    except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return {}
    generated_at = datetime.now(timezone.utc)
    expires_at = generated_at + timedelta(seconds=SNAPSHOT_TTL_SECONDS)
    return {
        "contractVersion": CONTRACT_VERSION,
        "runtimeProfile": str(payload["runtimeProfile"]),
        "command": str(payload["command"]),
        "ownerLaunchMode": str(payload["ownerLaunchMode"]),
        "ownerPid": str(payload["ownerPid"]),
        "ownerProcessStartedAt": _normalized_process_value(
            payload["ownerProcessStartedAt"]
        ),
        "ownerBindingSha256": str(payload["ownerBindingSha256"]),
        "ownerStateSha256": _sha256_file(owner_state_path),
        "repoRootSha256": _sha256_bytes(str(installed).encode("utf-8")),
        "runtimeDirSha256": _sha256_bytes(str(runtime_dir).encode("utf-8")),
        "configFileSha256": _sha256_bytes(str(config_file).encode("utf-8")),
        "componentsLockFileSha256": _sha256_bytes(
            str(components_lock_file).encode("utf-8")
        ),
        "ownerExecutablePathSha256": _sha256_bytes(
            str(executable).encode("utf-8")
        ),
        "ownerProcessCwdSha256": _sha256_bytes(
            str(process_cwd).encode("utf-8")
        ),
        "ownerProcessCommandSha256": _sha256_bytes(
            _normalized_process_value(payload["ownerProcessCommand"]).encode("utf-8")
        ),
        "generatedAt": generated_at.isoformat(),
        "expiresAt": expires_at.isoformat(),
        "maxAgeSeconds": SNAPSHOT_TTL_SECONDS,
    }


def _qa_receipt_attestation_authority(
    installed_root: Path | None,
    runtime_owner_state: Path | None,
    *,
    create: bool = False,
) -> tuple[bytes, str] | None:
    """Load the private signing authority for the proven, active runtime owner."""

    if not _runtime_owner_state_proves_active(installed_root, runtime_owner_state):
        return None
    assert runtime_owner_state is not None
    try:
        owner = json.loads(Path(runtime_owner_state).read_text(encoding="utf-8"))
        runtime_dir = Path(str(owner["runtimeDir"])).resolve(strict=True)
        runtime_stat = runtime_dir.stat()
        if (
            not stat.S_ISDIR(runtime_stat.st_mode)
            or stat.S_IMODE(runtime_stat.st_mode) != 0o700
            or (hasattr(os, "getuid") and runtime_stat.st_uid != os.getuid())
        ):
            return None
        binding = _canonical_hash(
            {
                "contractVersion": CONTRACT_VERSION,
                "ownerUid": runtime_stat.st_uid,
                "repoRootSha256": _sha256_bytes(
                    str(owner["repoRoot"]).encode("utf-8")
                ),
                "runtimeDirSha256": _sha256_bytes(
                    str(runtime_dir).encode("utf-8")
                ),
                "runtimeProfile": str(owner["runtimeProfile"]),
            }
        )
        key_path = runtime_dir / QA_RECEIPT_ATTESTATION_KEY_NAME
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        if create and not key_path.exists():
            temporary_path: Path | None = None
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{QA_RECEIPT_ATTESTATION_KEY_NAME}.",
                    suffix=".tmp",
                    dir=runtime_dir,
                )
                temporary_path = Path(temporary_name)
                with os.fdopen(descriptor, "wb") as key_file:
                    os.fchmod(key_file.fileno(), 0o600)
                    key_file.write(os.urandom(32))
                    key_file.flush()
                    os.fsync(key_file.fileno())
                try:
                    os.link(temporary_path, key_path, follow_symlinks=False)
                except FileExistsError:
                    pass
                temporary_path.unlink(missing_ok=True)
                temporary_path = None
                directory_fd = os.open(
                    runtime_dir,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | no_follow,
                )
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        descriptor = os.open(key_path, os.O_RDONLY | no_follow)
        try:
            key_stat = os.fstat(descriptor)
            key = os.read(descriptor, 33)
        finally:
            os.close(descriptor)
        current_stat = key_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(key_stat.st_mode)
            or stat.S_IMODE(key_stat.st_mode) != 0o600
            or key_stat.st_nlink != 1
            or len(key) != 32
            or (hasattr(os, "getuid") and key_stat.st_uid != os.getuid())
            or (key_stat.st_dev, key_stat.st_ino)
            != (current_stat.st_dev, current_stat.st_ino)
        ):
            return None
        return key, binding
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _sign_qa_receipt(
    receipt: dict[str, object],
    authority: tuple[bytes, str] | None,
) -> str:
    if (
        not isinstance(authority, tuple)
        or len(authority) != 2
        or not isinstance(authority[0], bytes)
        or len(authority[0]) != 32
        or SHA256.fullmatch(str(authority[1])) is None
        or receipt.get("ownerBindingSha256") != authority[1]
    ):
        raise ValueError("authenticated QA receipt authority is unavailable")
    payload = {key: value for key, value in receipt.items() if key != "attestation"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "hmac-sha256:" + hmac.new(authority[0], encoded, hashlib.sha256).hexdigest()


def _qa_receipt_attestation_valid(
    receipt: dict[str, object],
    authority: tuple[bytes, str] | None,
) -> bool:
    presented = str(receipt.get("attestation") or "")
    if QA_RECEIPT_ATTESTATION.fullmatch(presented) is None:
        return False
    try:
        expected = _sign_qa_receipt(receipt, authority)
    except ValueError:
        return False
    return hmac.compare_digest(presented, expected)


def canonical_runtime_claim_paths(
    installed_root: Path | None,
    runtime_owner_state: Path | None,
) -> dict[str, Path] | None:
    if not _runtime_owner_state_proves_active(installed_root, runtime_owner_state):
        return None
    assert installed_root is not None and runtime_owner_state is not None
    try:
        installed = Path(installed_root).expanduser().resolve(strict=True)
        owner_state = Path(runtime_owner_state).expanduser().resolve(strict=True)
        payload = json.loads(owner_state.read_text(encoding="utf-8"))
        runtime_dir = Path(str(payload["runtimeDir"])).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return {
        "installed_root": installed,
        "runtime_owner_state": owner_state,
        "readiness_facts": runtime_dir / "parallel-work-readiness-facts.json",
        "artifact_identity": runtime_dir / "parallel-work-artifact-identity.json",
        "qa_case_receipts": runtime_dir / "parallel-work-qa-case-receipts.json",
        "installed_prompt_bundle": runtime_dir / "prompt-bundle.json",
        "output": runtime_dir / "parallel-work-release-gate.json",
    }


def _load_component_lock(root: Path) -> tuple[list[dict[str, object]], str]:
    lock_path = root / "components.lock.json"
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], ""
    components = payload.get("components") if isinstance(payload, dict) else None
    if payload.get("version") != CONTRACT_VERSION or not isinstance(components, list):
        return [], _sha256_file(lock_path)
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    root_resolved = root.resolve()
    for raw in components:
        if not isinstance(raw, dict):
            return [], _sha256_file(lock_path)
        name = str(raw.get("name") or "").strip()
        relative = str(raw.get("path") or "").strip()
        pin = str(raw.get("ref") or "").strip().lower()
        if (
            not SAFE_NAME.fullmatch(name)
            or name in seen
            or not relative
            or not re.fullmatch(r"[0-9a-f]{40}", pin)
        ):
            return [], _sha256_file(lock_path)
        component_path = (root / relative).resolve()
        try:
            component_path.relative_to(root_resolved)
        except ValueError:
            return [], _sha256_file(lock_path)
        seen.add(name)
        identity = _git_identity(component_path)
        normalized.append(
            {
                "name": name,
                "pin": pin,
                **identity,
            }
        )
    return sorted(normalized, key=lambda item: str(item["name"])), _sha256_file(lock_path)


def _helper_source_hash(helper_root: Path) -> str:
    # Load the sibling verifier so standalone release-gate callers share its contract.
    spec = importlib.util.spec_from_file_location(
        "viventium_helper_artifact_verify", Path(__file__).with_name("helper_artifact_verify.py")
    )
    if spec is None or spec.loader is None:
        return ""
    verifier = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(verifier)
        return verifier.helper_source_hash(helper_root)
    except (OSError, RuntimeError):
        return ""


def _declared_hash(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    return value if SHA256.fullmatch(value) else ""


def _prebuilt_helper_identity(root: Path) -> dict[str, object]:
    helper_root = root / "apps" / "macos" / "ViventiumHelper"
    prebuilt_root = helper_root / "prebuilt"
    binary_path = prebuilt_root / "ViventiumHelper-universal"
    return {
        "sourceDeclaredSha256": _declared_hash(prebuilt_root / "source.sha256"),
        "sourceMeasuredSha256": _helper_source_hash(helper_root),
        "binaryDeclaredSha256": _declared_hash(prebuilt_root / "binary.sha256"),
        "binaryMeasuredSha256": _sha256_file(binary_path),
        "binaryExecutable": binary_path.is_file() and os.access(binary_path, os.X_OK),
    }


def _nested_revision_hash(nested: object) -> str:
    if not isinstance(nested, list):
        return ""
    return _canonical_hash(
        [
            {
                "name": item.get("name"),
                "pin": item.get("pin"),
                "revision": item.get("revision"),
            }
            for item in nested
            if isinstance(item, dict)
        ]
    )


def _sha256_tree(root: Path) -> str:
    try:
        exact_root = root.resolve(strict=True)
        files = sorted(path for path in exact_root.rglob("*") if path.is_file())
        if not files or any(path.is_symlink() for path in files):
            return ""
        digest = hashlib.sha256()
        for path in files:
            relative = path.relative_to(exact_root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    except (OSError, RuntimeError, ValueError):
        return ""


def _git_tracked_files(
    target: Path,
    repository_cache: dict[Path, set[Path]],
) -> set[Path] | None:
    try:
        exact_target = target.resolve(strict=True)
        cwd = exact_target if exact_target.is_dir() else exact_target.parent
        repo_root = next(
            (candidate for candidate in (cwd, *cwd.parents) if (candidate / ".git").exists()),
            None,
        )
        if repo_root is None:
            return None
        repo_root = repo_root.resolve(strict=True)
        if not exact_target.is_relative_to(repo_root):
            return None
        if repo_root not in repository_cache:
            inside_ok, inside = _git_bytes(
                repo_root,
                "rev-parse",
                "--is-inside-work-tree",
                max_output_bytes=16,
            )
            tracked_ok, tracked = _git_bytes(repo_root, "ls-files", "-z")
            raw_files = _nul_paths(tracked) if tracked_ok else None
            if not inside_ok or inside.strip() != b"true" or raw_files is None:
                return None
            files: set[Path] = set()
            for raw_relative in raw_files:
                candidate = repo_root / os.fsdecode(raw_relative)
                try:
                    resolved_candidate = candidate.resolve(strict=True)
                except FileNotFoundError:
                    continue
                if not resolved_candidate.is_relative_to(repo_root):
                    return None
                files.add(resolved_candidate)
            repository_cache[repo_root] = files
        return {
            path
            for path in repository_cache[repo_root]
            if path == exact_target
            or (exact_target.is_dir() and path.is_relative_to(exact_target))
        }
    except (OSError, RuntimeError, ValueError):
        return None


def _runtime_service_artifact_digests(installed_root: Path) -> tuple[str, str]:
    try:
        exact_root = installed_root.resolve(strict=True)
        manifest_path = (
            exact_root
            / "scripts"
            / "viventium"
            / "parallel_work_runtime_artifact_manifest.json"
        ).resolve(strict=True)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if payload.get("contractVersion") != CONTRACT_VERSION or not isinstance(entries, list):
            return "", ""
        if not entries:
            return "", ""
        seen: set[str] = set()
        measured: list[dict[str, str]] = []
        tracked_repository_cache: dict[Path, set[Path]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                return "", ""
            relative = str(entry.get("path") or "")
            kind = str(entry.get("kind") or "")
            tracked_only = entry.get("trackedOnly")
            relative_path = Path(relative)
            if (
                not relative
                or "\\" in relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.as_posix() != relative
                or relative in seen
                or kind not in {"file", "tree"}
                or not isinstance(tracked_only, bool)
            ):
                return "", ""
            seen.add(relative)
            target = (exact_root / relative_path).resolve(strict=True)
            if not target.is_relative_to(exact_root) or target.is_symlink():
                return "", ""
            tracked_files: set[Path] | None = None
            if kind == "file":
                if set(entry) != {"kind", "path", "trackedOnly"} or not target.is_file():
                    return "", ""
                files = [target]
            else:
                extensions = entry.get("extensions")
                excluded = entry.get("excludeDirectories")
                excluded_suffixes = entry.get("excludeFileSuffixes")
                if (
                    set(entry)
                    != {
                        "excludeDirectories",
                        "excludeFileSuffixes",
                        "extensions",
                        "kind",
                        "path",
                        "trackedOnly",
                    }
                    or not target.is_dir()
                    or not isinstance(extensions, list)
                    or not extensions
                    or len(set(extensions)) != len(extensions)
                    or not all(
                        isinstance(extension, str)
                        and re.fullmatch(r"\.[A-Za-z0-9]{1,16}", extension)
                        for extension in extensions
                    )
                    or not isinstance(excluded, list)
                    or len(set(excluded)) != len(excluded)
                    or not all(SAFE_NAME.fullmatch(str(name)) for name in excluded)
                    or not isinstance(excluded_suffixes, list)
                    or len(set(excluded_suffixes)) != len(excluded_suffixes)
                    or not all(
                        isinstance(suffix, str)
                        and suffix.startswith(".")
                        and len(suffix) <= 40
                        and re.fullmatch(r"\.[A-Za-z0-9_.-]+", suffix)
                        for suffix in excluded_suffixes
                    )
                ):
                    return "", ""
                excluded_names = {str(name) for name in excluded}
                excluded_file_suffixes = tuple(str(value) for value in excluded_suffixes)
                tracked_files = (
                    _git_tracked_files(target, tracked_repository_cache)
                    if tracked_only
                    else None
                )
                candidates = tracked_files if tracked_only else set(target.rglob("*"))
                if candidates is None:
                    return "", ""
                files = sorted(
                    path
                    for path in candidates
                    if path.is_file()
                    and path.suffix in extensions
                    and not any(part in excluded_names for part in path.relative_to(target).parts)
                    and not path.name.endswith(excluded_file_suffixes)
                )
                if not files:
                    return "", ""
            if tracked_only:
                tracked_files = tracked_files or _git_tracked_files(
                    target,
                    tracked_repository_cache,
                )
                if tracked_files is None or any(path not in tracked_files for path in files):
                    return "", ""
            for path in files:
                if path.is_symlink():
                    return "", ""
                measured.append(
                    {
                        "path": path.relative_to(exact_root).as_posix(),
                        "sha256": _sha256_file(path),
                    }
                )
        if not measured or any(not SHA256.fullmatch(item["sha256"]) for item in measured):
            return "", ""
        return _sha256_file(manifest_path), _canonical_hash(measured)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        return "", ""


def _installed_runtime_artifact_hashes(
    installed_root: Path,
    prompt_bundle_path: Path | None,
    runtime_owner_state: Path,
) -> dict[str, str]:
    empty = {key: "" for key in INSTALLED_ARTIFACT_HASH_KEYS[5:]}
    try:
        owner = json.loads(runtime_owner_state.read_text(encoding="utf-8"))
        runtime_dir = Path(str(owner["runtimeDir"])).resolve(strict=True)
        prompt_path = Path(prompt_bundle_path).resolve(strict=True)
        if prompt_path != (runtime_dir / "prompt-bundle.json").resolve(strict=True):
            return empty
        librechat_root = (installed_root / "viventium_v0_4" / "LibreChat").resolve(
            strict=True
        )
        contract_path = (
            installed_root
            / "scripts"
            / "viventium"
            / "runtime_owner_command_contract.json"
        ).resolve(strict=True)
        owner_executable = (installed_root / "bin" / "viventium").resolve(strict=True)
        if _runtime_owner_command_contract(owner_executable) is None:
            return empty
        runtime_manifest_hash, running_service_hash = _runtime_service_artifact_digests(
            installed_root
        )
        values = {
            "runtimeEnvSha256": _sha256_file(runtime_dir / "runtime.env"),
            "libreChatConfigSha256": _sha256_file(runtime_dir / "librechat.yaml"),
            "frontendBuildSha256": _sha256_tree(librechat_root / "client" / "dist"),
            "apiBuildSha256": _sha256_tree(librechat_root / "packages" / "api" / "dist"),
            "runningServiceSha256": running_service_hash,
            "runtimeServiceManifestSha256": runtime_manifest_hash,
            "runtimeOwnerExecutableSha256": _sha256_file(owner_executable),
            "ownerCommandContractSha256": _sha256_file(contract_path),
        }
    except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return empty
    return values if all(SHA256.fullmatch(value) for value in values.values()) else empty


def _measured_artifact_identity(
    root: Path,
    prompt_bundle_path: Path | None,
    installed_root: Path | None = None,
    runtime_owner_state: Path | None = None,
) -> dict[str, object]:
    root = Path(root).resolve()
    source = _git_identity(root, ignore_submodules=True)
    nested, lock_hash = _load_component_lock(root)
    source["componentsLockSha256"] = lock_hash
    prebuilt = _prebuilt_helper_identity(root)
    resolved_installed_root = (
        Path(installed_root).expanduser().resolve()
        if installed_root is not None
        else None
    )
    installed_root_valid = (
        resolved_installed_root is not None and resolved_installed_root.is_dir()
    )
    installed_runtime_active = _runtime_owner_state_proves_active(
        resolved_installed_root, runtime_owner_state
    )
    installed_identity_available = installed_root_valid and installed_runtime_active
    installed_source = (
        _git_identity(resolved_installed_root, ignore_submodules=True)
        if installed_identity_available
        else {"revision": "", "clean": False, "worktreeHash": ""}
    )
    installed_nested, installed_lock_hash = (
        _load_component_lock(resolved_installed_root)
        if installed_identity_available
        else ([], "")
    )
    installed_prebuilt = (
        _prebuilt_helper_identity(resolved_installed_root)
        if installed_identity_available
        else {
            "sourceDeclaredSha256": "",
            "sourceMeasuredSha256": "",
            "binaryDeclaredSha256": "",
            "binaryMeasuredSha256": "",
            "binaryExecutable": False,
        }
    )
    installed_runtime_hashes = (
        _installed_runtime_artifact_hashes(
            resolved_installed_root,
            prompt_bundle_path,
            Path(runtime_owner_state).expanduser().resolve(strict=True),
        )
        if installed_identity_available
        and resolved_installed_root is not None
        and runtime_owner_state is not None
        else {key: "" for key in INSTALLED_ARTIFACT_HASH_KEYS[5:]}
    )
    return {
        "contractVersion": CONTRACT_VERSION,
        "readiness": _readiness_identity_from_prompt_bundle(prompt_bundle_path),
        "source": source,
        "nestedComponents": nested,
        "prebuiltHelper": prebuilt,
        "installed": {
            "rootRevision": installed_source.get("revision"),
            "componentsLockSha256": installed_lock_hash,
            "nestedRevisionsHash": _nested_revision_hash(installed_nested),
            "prebuiltSourceSha256": installed_prebuilt.get("sourceMeasuredSha256"),
            "prebuiltBinarySha256": installed_prebuilt.get("binaryMeasuredSha256"),
            "promptBundleSha256": (
                _sha256_file(Path(prompt_bundle_path))
                if installed_identity_available and prompt_bundle_path is not None
                else ""
            ),
            **installed_runtime_hashes,
        },
    }


def build_release_artifact_identity(
    root: Path,
    prompt_bundle_path: Path,
    installed_root: Path | None = None,
    runtime_owner_state: Path | None = None,
) -> dict[str, object]:
    """Build the public-safe identity receipt installed beside compiled runtime files."""

    return _measured_artifact_identity(
        Path(root), Path(prompt_bundle_path), installed_root, runtime_owner_state
    )


def _public_artifact_identity(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}

    def public_revision(item: object) -> str:
        return item if isinstance(item, str) and re.fullmatch(r"[0-9a-f]{40}", item) else ""

    def public_hash(item: object) -> str:
        return item if isinstance(item, str) and SHA256.fullmatch(item) else ""

    def public_boolean(item: object) -> bool:
        return item if isinstance(item, bool) else False

    source = value.get("source") if isinstance(value.get("source"), dict) else {}
    nested = value.get("nestedComponents")
    prebuilt = (
        value.get("prebuiltHelper")
        if isinstance(value.get("prebuiltHelper"), dict)
        else {}
    )
    installed = (
        value.get("installed") if isinstance(value.get("installed"), dict) else {}
    )
    readiness = (
        value.get("readiness") if isinstance(value.get("readiness"), dict) else {}
    )
    safe_nested: list[dict[str, object]] = []
    if isinstance(nested, list):
        for item in nested:
            if not isinstance(item, dict) or not SAFE_NAME.fullmatch(
                str(item.get("name") or "")
            ):
                continue
            safe_nested.append(
                {
                    "name": str(item["name"]),
                    "pin": public_revision(item.get("pin")),
                    "revision": public_revision(item.get("revision")),
                    "clean": public_boolean(item.get("clean")),
                    "worktreeHash": public_hash(item.get("worktreeHash")),
                }
            )
    return {
        "contractVersion": (
            CONTRACT_VERSION if value.get("contractVersion") == CONTRACT_VERSION else 0
        ),
        "readiness": {
            key: public_hash(readiness.get(key))
            for key in READINESS_IDENTITY_HASH_KEYS
        },
        "source": {
            "revision": public_revision(source.get("revision")),
            "clean": public_boolean(source.get("clean")),
            "worktreeHash": public_hash(source.get("worktreeHash")),
            "componentsLockSha256": public_hash(source.get("componentsLockSha256")),
        },
        "nestedComponents": safe_nested,
        "prebuiltHelper": {
            key: (
                public_boolean(prebuilt.get(key))
                if key == "binaryExecutable"
                else public_hash(prebuilt.get(key))
            )
            for key in (
                "sourceDeclaredSha256",
                "sourceMeasuredSha256",
                "binaryDeclaredSha256",
                "binaryMeasuredSha256",
                "binaryExecutable",
            )
        },
        "installed": {
            key: (
                public_revision(installed.get(key))
                if key == "rootRevision"
                else public_hash(installed.get(key))
            )
            for key in (
                "rootRevision",
                "componentsLockSha256",
                "nestedRevisionsHash",
                "prebuiltSourceSha256",
                "prebuiltBinarySha256",
                "promptBundleSha256",
                "runtimeEnvSha256",
                "libreChatConfigSha256",
                "frontendBuildSha256",
                "apiBuildSha256",
                "runningServiceSha256",
                "runtimeServiceManifestSha256",
                "runtimeOwnerExecutableSha256",
                "ownerCommandContractSha256",
            )
        },
    }


def _artifact_identity_shape_valid(value: object) -> bool:
    if not isinstance(value, dict) or value.get("contractVersion") != CONTRACT_VERSION:
        return False
    source = value.get("source")
    nested = value.get("nestedComponents")
    prebuilt = value.get("prebuiltHelper")
    installed = value.get("installed")
    readiness = value.get("readiness")
    if not all(
        isinstance(item, dict) for item in (source, prebuilt, installed, readiness)
    ):
        return False
    assert isinstance(source, dict)
    assert isinstance(prebuilt, dict)
    assert isinstance(installed, dict)
    assert isinstance(readiness, dict)
    readiness_valid = all(
        SHA256.fullmatch(str(readiness.get(key) or "")) is not None
        for key in READINESS_IDENTITY_HASH_KEYS
    )
    source_valid = (
        re.fullmatch(r"[0-9a-f]{40}", str(source.get("revision") or ""))
        is not None
        and isinstance(source.get("clean"), bool)
        and SHA256.fullmatch(str(source.get("worktreeHash") or "")) is not None
        and SHA256.fullmatch(str(source.get("componentsLockSha256") or ""))
        is not None
    )
    nested_names = (
        [str(item.get("name") or "") for item in nested if isinstance(item, dict)]
        if isinstance(nested, list)
        else []
    )
    nested_valid = (
        isinstance(nested, list)
        and bool(nested)
        and len(nested_names) == len(nested)
        and len(set(nested_names)) == len(nested)
        and nested_names == sorted(nested_names)
        and all(
            isinstance(item, dict)
            and SAFE_NAME.fullmatch(str(item.get("name") or "")) is not None
            and re.fullmatch(r"[0-9a-f]{40}", str(item.get("pin") or ""))
            is not None
            and re.fullmatch(r"[0-9a-f]{40}", str(item.get("revision") or ""))
            is not None
            and isinstance(item.get("clean"), bool)
            and SHA256.fullmatch(str(item.get("worktreeHash") or "")) is not None
            for item in nested
        )
    )
    prebuilt_valid = (
        all(
            SHA256.fullmatch(str(prebuilt.get(key) or "")) is not None
            for key in (
                "sourceDeclaredSha256",
                "sourceMeasuredSha256",
                "binaryDeclaredSha256",
                "binaryMeasuredSha256",
            )
        )
        and isinstance(prebuilt.get("binaryExecutable"), bool)
    )
    installed_valid = (
        re.fullmatch(r"[0-9a-f]{40}", str(installed.get("rootRevision") or ""))
        is not None
        and all(
            SHA256.fullmatch(str(installed.get(key) or "")) is not None
            for key in (
                *INSTALLED_ARTIFACT_HASH_KEYS,
            )
        )
    )
    return (
        readiness_valid
        and source_valid
        and nested_valid
        and prebuilt_valid
        and installed_valid
    )


def _artifact_identity_checks(
    root: Path,
    artifact_identity: object,
    installed_prompt_bundle_path: Path | None,
    installed_root: Path | None,
    runtime_owner_state: Path | None,
) -> tuple[tuple[ReadinessCheck, ...], dict[str, object]]:
    measured = _measured_artifact_identity(
        root, installed_prompt_bundle_path, installed_root, runtime_owner_state
    )
    source = measured["source"]
    nested = measured["nestedComponents"]
    prebuilt = measured["prebuiltHelper"]
    source_shape_ok = (
        isinstance(source, dict)
        and bool(source.get("revision"))
        and bool(source.get("componentsLockSha256"))
        and SHA256.fullmatch(str(source.get("worktreeHash") or "")) is not None
    )
    source_hash_unavailable = (
        isinstance(source, dict)
        and bool(source.get("revision"))
        and source.get("clean") is False
        and SHA256.fullmatch(str(source.get("worktreeHash") or "")) is None
    )
    source_ok = source_shape_ok and source.get("clean") is True
    nested_pin_ok = bool(nested) and all(
        isinstance(item, dict)
        and item.get("pin") == item.get("revision")
        and SHA256.fullmatch(str(item.get("worktreeHash") or "")) is not None
        for item in nested
    )
    nested_clean = nested_pin_ok and all(
        isinstance(item, dict) and item.get("clean") is True for item in nested
    )
    nested_hash_unavailable = bool(nested) and any(
        isinstance(item, dict)
        and bool(item.get("revision"))
        and item.get("clean") is False
        and SHA256.fullmatch(str(item.get("worktreeHash") or "")) is None
        for item in nested
    )
    nested_ok = nested_pin_ok and nested_clean
    prebuilt_ok = (
        isinstance(prebuilt, dict)
        and prebuilt.get("binaryExecutable") is True
        and bool(prebuilt.get("sourceDeclaredSha256"))
        and prebuilt.get("sourceDeclaredSha256") == prebuilt.get("sourceMeasuredSha256")
        and bool(prebuilt.get("binaryDeclaredSha256"))
        and prebuilt.get("binaryDeclaredSha256") == prebuilt.get("binaryMeasuredSha256")
    )
    public_identity = _public_artifact_identity(artifact_identity)
    identity_matches = (
        _artifact_identity_shape_valid(artifact_identity)
        and public_identity == measured
    )
    installed = measured["installed"]
    installed_root_path = (
        Path(installed_root).expanduser().resolve()
        if installed_root is not None
        else None
    )
    installed_root_valid = (
        installed_root_path is not None
        and installed_root_path.is_dir()
    )
    installed_runtime_active = _runtime_owner_state_proves_active(
        installed_root_path, runtime_owner_state
    )
    installed_nested = (
        _load_component_lock(installed_root_path)[0]
        if installed_root_valid
        else []
    )
    installed_prebuilt = (
        _prebuilt_helper_identity(installed_root_path)
        if installed_root_valid
        else {}
    )
    installed_source = (
        _git_identity(installed_root_path, ignore_submodules=True)
        if installed_root_valid
        else {"revision": "", "clean": False, "worktreeHash": ""}
    )
    installed_nested_pin_ok = bool(installed_nested) and all(
        isinstance(item, dict)
        and item.get("pin") == item.get("revision")
        and SHA256.fullmatch(str(item.get("worktreeHash") or "")) is not None
        for item in installed_nested
    )
    installed_candidate_clean = (
        installed_source.get("clean") is True
        and installed_nested_pin_ok
        and all(
            isinstance(item, dict) and item.get("clean") is True
            for item in installed_nested
        )
    )
    installed_hash_unavailable = installed_runtime_active and (
        (
            bool(installed_source.get("revision"))
            and installed_source.get("clean") is False
            and SHA256.fullmatch(str(installed_source.get("worktreeHash") or ""))
            is None
        )
        or any(
            isinstance(item, dict)
            and bool(item.get("revision"))
            and item.get("clean") is False
            and SHA256.fullmatch(str(item.get("worktreeHash") or "")) is None
            for item in installed_nested
        )
    )
    installed_non_dirty_alignment_ok = (
        installed_root_valid
        and installed_runtime_active
        and bool(installed.get("rootRevision"))
        and isinstance(installed, dict)
        and bool(installed_source.get("revision"))
        and SHA256.fullmatch(str(installed_source.get("worktreeHash") or ""))
        is not None
        and installed_nested_pin_ok
        and installed_prebuilt.get("binaryExecutable") is True
        and installed_prebuilt.get("sourceDeclaredSha256")
        == installed_prebuilt.get("sourceMeasuredSha256")
        and installed_prebuilt.get("binaryDeclaredSha256")
        == installed_prebuilt.get("binaryMeasuredSha256")
        and installed.get("rootRevision") == source.get("revision")
        and installed.get("componentsLockSha256")
        == source.get("componentsLockSha256")
        and installed.get("nestedRevisionsHash") == _nested_revision_hash(nested)
        and installed.get("prebuiltSourceSha256")
        == prebuilt.get("sourceMeasuredSha256")
        and installed.get("prebuiltBinarySha256")
        == prebuilt.get("binaryMeasuredSha256")
        and all(
            SHA256.fullmatch(str(installed.get(key) or "")) is not None
            for key in INSTALLED_ARTIFACT_HASH_KEYS[5:]
        )
    )
    installed_alignment_ok = (
        installed_non_dirty_alignment_ok and installed_candidate_clean
    )
    installed_ok = (
        public_identity.get("contractVersion") == CONTRACT_VERSION
        and bool(measured["installed"].get("promptBundleSha256"))
        and installed_alignment_ok
        and identity_matches
    )
    source_reason = (
        "source_worktree_hash_unavailable"
        if source_hash_unavailable
        else (
            "source_dirty"
            if identity_matches and source_shape_ok and source.get("clean") is False
            else "source_identity_mismatch"
        )
    )
    nested_reason = (
        "nested_worktree_hash_unavailable"
        if nested_hash_unavailable
        else (
            "nested_dirty"
            if identity_matches and nested_pin_ok and not nested_clean
            else "nested_pin_mismatch"
        )
    )
    installed_dirty = (
        identity_matches
        and public_identity.get("contractVersion") == CONTRACT_VERSION
        and bool(measured["installed"].get("promptBundleSha256"))
        and installed_non_dirty_alignment_ok
        and not installed_candidate_clean
    )
    checks = (
        ReadinessCheck(
            "SOURCE-IDENTITY",
            PASS if source_ok else "FAIL",
            "" if source_ok else source_reason,
        ),
        ReadinessCheck(
            "NESTED-PINS",
            PASS if nested_ok else "FAIL",
            "" if nested_ok else nested_reason,
        ),
        ReadinessCheck(
            "PREBUILT-IDENTITY",
            PASS if prebuilt_ok else "FAIL",
            "" if prebuilt_ok else "prebuilt_identity_mismatch",
        ),
        ReadinessCheck(
            "INSTALLED-ARTIFACT",
            PASS if installed_ok else "FAIL",
            ""
            if installed_ok
            else (
                "installed_root_missing"
                if installed_root is None
                else (
                    "installed_root_invalid"
                    if not installed_root_valid
                    else (
                        "installed_runtime_not_active"
                        if not installed_runtime_active
                        else (
                            "installed_worktree_hash_unavailable"
                            if installed_hash_unavailable
                            else (
                                "installed_candidate_dirty"
                                if installed_dirty
                                else "installed_artifact_mismatch"
                            )
                        )
                    )
                )
            ),
        ),
    )
    return checks, public_identity


def _unknown_readiness_checks(reason: str) -> tuple[ReadinessCheck, ...]:
    return (
        ReadinessCheck("PROMPT-LAYERS", "UNKNOWN", reason),
        ReadinessCheck("STORAGE-PRESSURE", "UNKNOWN", reason),
    )


def _public_readiness_facts(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    prompt = (
        value.get("promptLayers")
        if isinstance(value.get("promptLayers"), dict)
        else {}
    )
    storage = (
        value.get("storagePressure")
        if isinstance(value.get("storagePressure"), dict)
        else {}
    )

    def public_number(item: object) -> int | float:
        return item if isinstance(item, (int, float)) and not isinstance(item, bool) else 0

    def public_prompt_value(key: str) -> object:
        item = prompt.get(key)
        if key == "reason":
            return _safe_reason(item, "prompt_layers_unknown")
        if key == "producerScope":
            return item if item == PROMPT_PRODUCER_SCOPE else "unknown"
        if key == "status":
            return (
                item
                if isinstance(item, str) and item in {"verified", "unknown", "mismatch"}
                else "unknown"
            )
        if key in {"unknownLayerNames", "layerNames"}:
            if not isinstance(item, list):
                return []
            return [name for name in item if isinstance(name, str) and SAFE_NAME.fullmatch(name)]
        if key == "registryHash":
            return item if isinstance(item, str) and SHA256.fullmatch(item) else ""
        return public_number(item)

    def public_storage_value(key: str) -> object:
        item = storage.get(key)
        if key == "reason":
            return _safe_reason(item, "storage_pressure_unknown")
        if key == "status":
            return (
                item
                if isinstance(item, str) and item in {"healthy", "warning", "critical"}
                else "unknown"
            )
        return public_number(item)

    return {
        "contractVersion": public_number(value.get("contractVersion")),
        "promptLayers": {
            key: public_prompt_value(key)
            for key in (
                "contractVersion",
                "producerScope",
                "status",
                "unknownLayerCount",
                "unknownLayerNames",
                "promptCount",
                "layerCount",
                "layerNames",
                "registryHash",
                "reason",
            )
            if key in prompt
        },
        "storagePressure": {
            key: public_storage_value(key)
            for key in (
                "version",
                "status",
                "usedPercent",
                "availableBytes",
                "thresholdPercent",
                "warningMarginPercent",
                "reason",
            )
            if key in storage
        },
    }


def _storage_pressure_shape_valid(storage: object) -> bool:
    if not isinstance(storage, dict):
        return False
    storage_status = str(storage.get("status") or "").strip().lower()
    used_percent = storage.get("usedPercent")
    available_bytes = storage.get("availableBytes")
    threshold_percent = storage.get("thresholdPercent")
    warning_margin_percent = storage.get("warningMarginPercent")
    return (
        storage.get("version") == CONTRACT_VERSION
        and storage_status in {"healthy", "warning", "critical"}
        and isinstance(used_percent, (int, float))
        and not isinstance(used_percent, bool)
        and 0 <= used_percent <= 100
        and isinstance(available_bytes, int)
        and not isinstance(available_bytes, bool)
        and 0 <= available_bytes <= 2**63 - 1
        and isinstance(threshold_percent, (int, float))
        and not isinstance(threshold_percent, bool)
        and 0 < threshold_percent <= 100
        and isinstance(warning_margin_percent, (int, float))
        and not isinstance(warning_margin_percent, bool)
        and 0 < warning_margin_percent < threshold_percent
    )


def _remeasure_storage_pressure(
    readiness_facts: object,
    installed_prompt_bundle_path: Path | None,
) -> object:
    if not isinstance(readiness_facts, dict) or installed_prompt_bundle_path is None:
        return readiness_facts
    storage = readiness_facts.get("storagePressure")
    if not _storage_pressure_shape_valid(storage):
        return readiness_facts
    assert isinstance(storage, dict)
    threshold_percent = float(storage["thresholdPercent"])
    warning_margin_percent = float(storage["warningMarginPercent"])
    try:
        canonical_artifact = Path(installed_prompt_bundle_path).expanduser().resolve(
            strict=True
        )
        if not canonical_artifact.is_file():
            raise ValueError("prompt artifact is not a regular file")
        probe_path = canonical_artifact.parent
        usage = shutil.disk_usage(probe_path)
        total = int(usage.total)
        used = int(usage.used)
        available = int(usage.free)
        if total <= 0 or used < 0 or available < 0 or used > total:
            raise ValueError("invalid storage probe")
        used_percent = round((used * 100.0) / total, 3)
        warning_threshold = max(
            0.0,
            threshold_percent - warning_margin_percent,
        )
        storage_status = (
            "critical"
            if used_percent >= threshold_percent
            else "warning"
            if used_percent >= warning_threshold
            else "healthy"
        )
        reason: dict[str, str] = {}
    except (AttributeError, OSError, TypeError, ValueError, ZeroDivisionError):
        used_percent = 100.0
        available = 0
        storage_status = "critical"
        reason = {"reason": "storage_probe_unavailable"}
    effective_storage = {
        **storage,
        "status": storage_status,
        "usedPercent": float(used_percent),
        "availableBytes": available,
    }
    effective_storage.pop("reason", None)
    effective_storage.update(reason)
    return {
        **readiness_facts,
        "storagePressure": effective_storage,
    }


def _typed_readiness_checks(
    readiness_facts: object,
    installed_prompt_bundle_path: Path | None = None,
) -> tuple[ReadinessCheck, ...]:
    if not isinstance(readiness_facts, dict):
        return _unknown_readiness_checks("readiness_facts_missing")
    if readiness_facts.get("contractVersion") != CONTRACT_VERSION:
        return _unknown_readiness_checks("readiness_facts_invalid")

    prompt = readiness_facts.get("promptLayers")
    prompt_check = ReadinessCheck(
        "PROMPT-LAYERS",
        "UNKNOWN",
        "prompt_layer_capability_invalid",
    )
    if isinstance(prompt, dict):
        prompt_status = str(prompt.get("status") or "").strip().lower()
        unknown_layer_count = prompt.get("unknownLayerCount")
        unknown_layer_names = prompt.get("unknownLayerNames")
        prompt_count = prompt.get("promptCount")
        layer_count = prompt.get("layerCount")
        layer_names = prompt.get("layerNames")
        registry_hash = str(prompt.get("registryHash") or "").strip().lower()
        prompt_shape_valid = (
            prompt.get("contractVersion") == CONTRACT_VERSION
            and prompt.get("producerScope") == PROMPT_PRODUCER_SCOPE
            and prompt_status in {"verified", "unknown", "mismatch"}
            and isinstance(unknown_layer_count, int)
            and not isinstance(unknown_layer_count, bool)
            and 0 <= unknown_layer_count <= 10_000
            and isinstance(unknown_layer_names, list)
            and len(unknown_layer_names) == unknown_layer_count
            and all(
                isinstance(name, str) and SAFE_NAME.fullmatch(name)
                for name in unknown_layer_names
            )
            and len(set(unknown_layer_names)) == len(unknown_layer_names)
            and isinstance(prompt_count, int)
            and not isinstance(prompt_count, bool)
            and 0 < prompt_count <= 100_000
            and isinstance(layer_count, int)
            and not isinstance(layer_count, bool)
            and isinstance(layer_names, list)
            and layer_count == len(layer_names)
            and all(
                isinstance(name, str) and SAFE_NAME.fullmatch(name)
                for name in layer_names
            )
            and len(set(layer_names)) == len(layer_names)
            and SHA256.fullmatch(registry_hash) is not None
        )
        installed_prompt_fact = _installed_prompt_registry_facts(
            installed_prompt_bundle_path
        )
        prompt_matches_installed = installed_prompt_fact is None or all(
            prompt.get(key) == installed_prompt_fact.get(key)
            for key in (
                "contractVersion",
                "producerScope",
                "status",
                "unknownLayerCount",
                "unknownLayerNames",
                "promptCount",
                "layerCount",
                "layerNames",
                "registryHash",
            )
        )
        if (
            prompt_shape_valid
            and prompt_matches_installed
            and prompt_status == "verified"
            and unknown_layer_count == 0
        ):
            prompt_check = ReadinessCheck("PROMPT-LAYERS", PASS, "")
        elif prompt_shape_valid and prompt_matches_installed:
            prompt_check = ReadinessCheck(
                "PROMPT-LAYERS",
                "FAIL",
                _safe_reason(prompt.get("reason"), "prompt_layers_unknown"),
            )
        elif prompt_shape_valid:
            prompt_check = ReadinessCheck(
                "PROMPT-LAYERS", "FAIL", "prompt_layer_hash_mismatch"
            )

    storage = readiness_facts.get("storagePressure")
    storage_check = ReadinessCheck(
        "STORAGE-PRESSURE",
        "UNKNOWN",
        "storage_capability_invalid",
    )
    if isinstance(storage, dict):
        storage_status = str(storage.get("status") or "").strip().lower()
        used_percent = storage.get("usedPercent")
        threshold_percent = storage.get("thresholdPercent")
        warning_margin_percent = storage.get("warningMarginPercent")
        storage_shape_valid = _storage_pressure_shape_valid(storage)
        if storage_shape_valid:
            warning_threshold = max(0.0, threshold_percent - warning_margin_percent)
            measured_status = (
                "critical"
                if used_percent >= threshold_percent
                else "warning"
                if used_percent >= warning_threshold
                else "healthy"
            )
            if measured_status != storage_status:
                storage_check = ReadinessCheck(
                    "STORAGE-PRESSURE", "UNKNOWN", "storage_capability_invalid"
                )
            elif measured_status == "healthy":
                storage_check = ReadinessCheck("STORAGE-PRESSURE", PASS, "")
            else:
                storage_check = ReadinessCheck(
                    "STORAGE-PRESSURE",
                    "FAIL",
                    "storage_pressure",
                )
    return (prompt_check, storage_check)


def _empty_readiness_identity() -> dict[str, str]:
    return {key: "" for key in READINESS_IDENTITY_HASH_KEYS}


def _canonical_readiness_facts(value: object) -> dict[str, object]:
    public = _public_readiness_facts(value)
    checks = _typed_readiness_checks(public)
    if not public or any(check.status == "UNKNOWN" for check in checks):
        return {}
    storage = public.get("storagePressure")
    if not isinstance(storage, dict):
        return {}
    normalized_storage = dict(storage)
    for key in ("usedPercent", "thresholdPercent", "warningMarginPercent"):
        if key in normalized_storage:
            normalized_storage[key] = float(normalized_storage[key])
    for key in ("version", "availableBytes"):
        if key in normalized_storage:
            normalized_storage[key] = int(normalized_storage[key])
    return {**public, "storagePressure": normalized_storage}


def _readiness_identity(value: object) -> dict[str, str]:
    canonical = _canonical_readiness_facts(value)
    if not canonical:
        return _empty_readiness_identity()
    storage = canonical["storagePressure"]
    assert isinstance(storage, dict)
    policy = {
        key: storage[key]
        for key in ("version", "thresholdPercent", "warningMarginPercent")
    }
    measurement = {
        key: storage[key]
        for key in ("version", "status", "usedPercent", "availableBytes", "reason")
        if key in storage
    }
    return {
        "factsSha256": _canonical_hash(canonical),
        "storagePolicySha256": _canonical_hash(policy),
        "storageMeasurementSha256": _canonical_hash(measurement),
    }


def _readiness_identity_from_prompt_bundle(
    prompt_bundle_path: Path | None,
) -> dict[str, str]:
    if prompt_bundle_path is None:
        return _empty_readiness_identity()
    runtime_descriptor: int | None = None
    facts_descriptor: int | None = None
    try:
        exact_prompt = Path(prompt_bundle_path).expanduser().resolve(strict=True)
        if not exact_prompt.is_file():
            return _empty_readiness_identity()
        bound = _open_bound_directory(exact_prompt.parent)
        if bound is None:
            return _empty_readiness_identity()
        exact_runtime, runtime_descriptor, opened_runtime = bound
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        facts_descriptor = os.open(
            "parallel-work-readiness-facts.json",
            flags,
            dir_fd=runtime_descriptor,
        )
        before = os.fstat(facts_descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size < 0
            or before.st_size > MAX_READINESS_FACTS_BYTES
        ):
            return _empty_readiness_identity()
        raw = bytearray()
        while True:
            remaining = MAX_READINESS_FACTS_BYTES - len(raw)
            chunk = os.read(
                facts_descriptor,
                min(WORKTREE_HASH_CHUNK_BYTES, remaining + 1),
            )
            if not chunk:
                break
            if len(chunk) > remaining:
                return _empty_readiness_identity()
            raw.extend(chunk)
        after = os.fstat(facts_descriptor)
        named = os.stat(
            "parallel-work-readiness-facts.json",
            dir_fd=runtime_descriptor,
            follow_symlinks=False,
        )
        if (
            len(raw) != before.st_size
            or _stat_identity(after) != _stat_identity(before)
            or _stat_identity(named) != _stat_identity(before)
            or not _bound_directory_unchanged(
                exact_runtime, runtime_descriptor, opened_runtime
            )
        ):
            return _empty_readiness_identity()
        return _readiness_identity(json.loads(bytes(raw).decode("utf-8")))
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return _empty_readiness_identity()
    finally:
        if facts_descriptor is not None:
            os.close(facts_descriptor)
        if runtime_descriptor is not None:
            os.close(runtime_descriptor)


def load_required_gates(root: Path) -> tuple[GateRecord, ...]:
    root = Path(root).resolve()
    records: list[GateRecord] = []
    for relative, pattern, catalog_id in TABLE_CATALOGS:
        records.extend(
            _table_records(
                root / relative, pattern, source=relative, catalog_id=catalog_id
            )
        )
    for relative, case_id in CROSS_OWNER_TABLE_CASES:
        records.append(_exact_table_record(root / relative, case_id, relative))
    for relative, case_id in CROSS_OWNER_DETAIL_CASES:
        records.append(_detail_record(root / relative, case_id, relative))

    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        if record.case_id in seen:
            duplicates.append(record.case_id)
        seen.add(record.case_id)
    if duplicates:
        raise ValueError(
            f"duplicate release gates: {', '.join(sorted(set(duplicates)))}"
        )
    return tuple(sorted(records, key=lambda record: record.case_id))


def _qa_candidate_digests(
    artifact_identity: object,
    readiness_facts: object = None,
) -> tuple[str, str]:
    public = _public_artifact_identity(artifact_identity)
    if not _artifact_identity_shape_valid(public):
        return "", ""
    readiness = (
        _readiness_identity(readiness_facts)
        if readiness_facts is not None
        else public["readiness"]
    )
    if readiness != public["readiness"] or any(
        SHA256.fullmatch(str(readiness.get(key) or "")) is None
        for key in READINESS_IDENTITY_HASH_KEYS
    ):
        return "", ""
    candidate = {
        "readiness": readiness,
        "source": public["source"],
        "nestedComponents": public["nestedComponents"],
        "prebuiltHelper": public["prebuiltHelper"],
    }
    return _canonical_hash(candidate), _canonical_hash(public["installed"])


def _qa_receipt_artifact_claims(
    case_id: str,
    artifact_identity: object,
) -> dict[str, str]:
    fields = QA_RECEIPT_ARTIFACT_CLAIM_FIELDS.get(case_id)
    public = _public_artifact_identity(artifact_identity)
    if fields is None or not _artifact_identity_shape_valid(public):
        return {}
    installed = public["installed"]
    assert isinstance(installed, dict)
    claims = {field: str(installed.get(field) or "") for field in fields}
    return (
        claims
        if all(SHA256.fullmatch(value) is not None for value in claims.values())
        else {}
    )


def _qa_receipt_artifact_claims_match(
    case_id: str,
    claims: object,
    artifact_identity: object,
) -> bool:
    expected = _qa_receipt_artifact_claims(case_id, artifact_identity)
    return (
        bool(expected)
        and isinstance(claims, dict)
        and set(claims) == set(expected)
        and all(
            isinstance(claims[field], str)
            and SHA256.fullmatch(claims[field]) is not None
            and hmac.compare_digest(claims[field], expected[field])
            for field in expected
        )
    )


def _load_external_release_attestation():
    path = Path(__file__).with_name("qa_release_attestation.py").resolve(strict=True)
    name = "viventium_qa_release_attestation"
    cached = sys.modules.get(name)
    if cached is not None:
        try:
            cached_path = Path(str(cached.__file__)).resolve(strict=True)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError("external release attestation provenance is invalid") from exc
        if cached_path != path:
            raise RuntimeError("external release attestation provenance is invalid")
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("external release attestation is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _release_authority_fstat(descriptor: int) -> os.stat_result:
    return os.fstat(descriptor)


def _open_system_release_authority_directory() -> tuple[Path, int] | None:
    """Open one fixed, root-owned, owner-unwritable system trust directory."""

    if not hasattr(os, "getuid") or os.getuid() == 0:
        return None
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor: int | None = None
    current = Path("/")
    try:
        descriptor = os.open(current, flags)
        for part in ("", *RELEASE_AUTHORITY_SYSTEM_DIRECTORY.parts[1:]):
            if part:
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
                current /= part
            details = _release_authority_fstat(descriptor)
            if (
                not stat.S_ISDIR(details.st_mode)
                or details.st_uid != 0
                or details.st_mode & 0o022
                or os.access(current, os.W_OK)
            ):
                os.close(descriptor)
                return None
        return current, descriptor
    except (OSError, RuntimeError, TypeError, ValueError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        return None


def _read_system_release_authority_file(
    directory: Path,
    directory_descriptor: int,
    name: str,
) -> tuple[bytes, int] | None:
    """Keep an immutable, root-owned, no-follow trust artifact pinned by FD."""

    maximum = RELEASE_AUTHORITY_FILE_LIMITS.get(name)
    if maximum is None:
        return None
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
        before = _release_authority_fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != 0
            or before.st_uid == os.getuid()
            or before.st_mode & 0o222
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > maximum
            or os.access(directory / name, os.W_OK)
        ):
            os.close(descriptor)
            return None
        payload = bytearray()
        while len(payload) <= maximum:
            chunk = os.read(descriptor, min(65_536, maximum + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        after = _release_authority_fstat(descriptor)
        current = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if (
            len(payload) > maximum
            or before.st_size != len(payload)
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)
        ):
            os.close(descriptor)
            return None
        os.lseek(descriptor, 0, os.SEEK_SET)
        return bytes(payload), descriptor
    except (OSError, RuntimeError, TypeError, ValueError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        return None


def _release_authority_socket_peer_uid(connection: socket.socket) -> int | None:
    """Obtain kernel-authenticated UNIX peer ownership, never provider claims."""

    if hasattr(socket, "SO_PEERCRED"):
        try:
            credentials = connection.getsockopt(
                socket.SOL_SOCKET,
                socket.SO_PEERCRED,
                struct.calcsize("3i"),
            )
            _pid, uid, _gid = struct.unpack("3i", credentials)
            return int(uid)
        except (OSError, struct.error, TypeError, ValueError):
            return None

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        getpeereid = libc.getpeereid
        getpeereid.argtypes = (
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
        )
        getpeereid.restype = ctypes.c_int
        uid = ctypes.c_uint()
        gid = ctypes.c_uint()
        if getpeereid(connection.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
            return None
        return int(uid.value)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


class _ProtectedExternalReleaseLedgerWitness:
    """Root-peer RPC witness whose independently signed checkpoints cannot be forged."""

    __slots__ = (
        "_attestation",
        "_candidate_digest",
        "_endpoint",
        "_owner_binding",
        "_signer_roots",
        "witness_identity",
    )
    protection = RELEASE_AUTHORITY_WITNESS_PROTECTION

    def __init__(
        self,
        *,
        attestation: object,
        candidate_digest: str,
        endpoint: Path,
        owner_binding: str,
        signer_roots: bytes,
        witness_identity: str,
    ) -> None:
        self._attestation = attestation
        self._candidate_digest = candidate_digest
        self._endpoint = endpoint
        self._owner_binding = owner_binding
        self._signer_roots = signer_roots
        self.witness_identity = witness_identity

    def _head_payload(self, head: object | None) -> dict[str, object] | None:
        if head is None:
            return None
        if (
            not isinstance(head, self._attestation.LedgerHead)
            or isinstance(head.sequence, bool)
            or not isinstance(head.sequence, int)
            or head.sequence < 1
            or SHA256.fullmatch(str(head.entry_digest)) is None
        ):
            raise RuntimeError("protected release witness checkpoint is invalid")
        return {"sequence": head.sequence, "entryDigest": head.entry_digest}

    def _decoded_head(self, payload: object) -> object | None:
        if payload is None:
            return None
        if (
            type(payload) is not dict
            or set(payload) != {"sequence", "entryDigest"}
            or isinstance(payload["sequence"], bool)
            or not isinstance(payload["sequence"], int)
            or payload["sequence"] < 1
            or not isinstance(payload["entryDigest"], str)
            or SHA256.fullmatch(payload["entryDigest"]) is None
        ):
            raise RuntimeError("protected release witness returned an invalid checkpoint")
        return self._attestation.LedgerHead(
            sequence=payload["sequence"], entry_digest=payload["entryDigest"]
        )

    def _verify_response_signature(self, payload: bytes, signature: object) -> None:
        armored = self._attestation._signature_text(signature, "protected release witness")
        with tempfile.TemporaryFile(mode="w+b") as signers:
            with tempfile.TemporaryFile(mode="w+b") as signed:
                signers.write(self._signer_roots)
                signers.flush()
                signers.seek(0)
                signed.write(armored.encode("ascii"))
                signed.flush()
                signed.seek(0)
                result = subprocess.run(
                    [
                        self._attestation._trusted_ssh_keygen(),
                        "-Y",
                        "verify",
                        "-f",
                        f"/dev/fd/{signers.fileno()}",
                        "-I",
                        self.witness_identity,
                        "-n",
                        RELEASE_AUTHORITY_WITNESS_NAMESPACE,
                        "-s",
                        f"/dev/fd/{signed.fileno()}",
                    ],
                    input=payload,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                    pass_fds=(signers.fileno(), signed.fileno()),
                    check=False,
                    timeout=15,
                )
        if result.returncode != 0:
            raise RuntimeError("protected release witness signature is invalid")

    def _request(
        self,
        operation: str,
        scope: str,
        *,
        expected: object | None = None,
        head: object | None = None,
    ) -> tuple[bool, object | None]:
        if operation not in {"probe", "current", "advance"}:
            raise RuntimeError("protected release witness operation is invalid")
        if not isinstance(scope, str) or SHA256.fullmatch(scope) is None:
            raise RuntimeError("protected release witness scope is invalid")
        request = {
            "candidateDigest": self._candidate_digest,
            "contractVersion": CONTRACT_VERSION,
            "expected": self._head_payload(expected),
            "head": self._head_payload(head),
            "nonce": os.urandom(32).hex(),
            "operation": operation,
            "ownerBindingSha256": self._owner_binding,
            "purpose": RELEASE_AUTHORITY_WITNESS_REQUEST_PURPOSE,
            "scope": scope,
            "witnessIdentity": self.witness_identity,
        }
        encoded_request = self._attestation._canonical_bytes(request)

        details = self._endpoint.stat(follow_symlinks=False)
        if not stat.S_ISSOCK(details.st_mode) or details.st_uid != 0:
            raise RuntimeError("protected release witness endpoint is not root-owned")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(RELEASE_AUTHORITY_WITNESS_TIMEOUT_SECONDS)
            connection.connect(str(self._endpoint))
            if _release_authority_socket_peer_uid(connection) != 0:
                raise RuntimeError("protected release witness peer is not root-owned")
            connection.sendall(encoded_request)
            received = bytearray()
            while len(received) <= RELEASE_AUTHORITY_WITNESS_MAX_RESPONSE_BYTES:
                chunk = connection.recv(
                    min(
                        65_536,
                        RELEASE_AUTHORITY_WITNESS_MAX_RESPONSE_BYTES + 1 - len(received),
                    )
                )
                if not chunk:
                    break
                received.extend(chunk)
                if b"\n" in chunk:
                    break
        raw_response = bytes(received)
        if (
            not raw_response.endswith(b"\n")
            or raw_response.count(b"\n") != 1
            or len(raw_response) > RELEASE_AUTHORITY_WITNESS_MAX_RESPONSE_BYTES
        ):
            raise RuntimeError("protected release witness response is invalid")
        decoded = json.loads(
            raw_response,
            object_pairs_hook=self._attestation._json_no_duplicates,
        )
        if self._attestation._canonical_bytes(decoded) != raw_response:
            raise RuntimeError("protected release witness response is not canonical")
        if type(decoded) is not dict or set(decoded) != {
            "accepted",
            "candidateDigest",
            "contractVersion",
            "durability",
            "head",
            "nonce",
            "operation",
            "ownerBindingSha256",
            "purpose",
            "requestDigest",
            "scope",
            "signature",
            "witnessIdentity",
        }:
            raise RuntimeError("protected release witness response shape is invalid")
        unsigned = dict(decoded)
        signature = unsigned.pop("signature")
        self._verify_response_signature(
            self._attestation._canonical_bytes(unsigned), signature
        )
        if (
            decoded["contractVersion"] != CONTRACT_VERSION
            or decoded["purpose"] != RELEASE_AUTHORITY_WITNESS_RESPONSE_PURPOSE
            or decoded["durability"] != RELEASE_AUTHORITY_WITNESS_DURABILITY
            or decoded["witnessIdentity"] != self.witness_identity
            or decoded["candidateDigest"] != self._candidate_digest
            or decoded["ownerBindingSha256"] != self._owner_binding
            or decoded["operation"] != operation
            or decoded["scope"] != scope
            or decoded["nonce"] != request["nonce"]
            or decoded["requestDigest"] != hashlib.sha256(encoded_request).hexdigest()
            or type(decoded["accepted"]) is not bool
        ):
            raise RuntimeError("protected release witness response does not match its request")
        return decoded["accepted"], self._decoded_head(decoded["head"])

    def prove(self) -> bool:
        accepted, head = self._request("probe", self._candidate_digest)
        return accepted is True and head is None

    def current(self, scope: str) -> object | None:
        accepted, head = self._request("current", scope)
        if accepted is not True:
            raise RuntimeError("protected release witness rejected the current checkpoint")
        return head

    def advance(self, scope: str, *, expected: object | None, head: object) -> bool:
        next_head = self._head_payload(head)
        assert next_head is not None
        previous_head = self._head_payload(expected)
        required_sequence = (
            int(previous_head["sequence"]) + 1 if previous_head is not None else 1
        )
        if next_head["sequence"] != required_sequence:
            raise RuntimeError("protected release witness checkpoint is not monotonic")
        accepted, confirmed = self._request(
            "advance", scope, expected=expected, head=head
        )
        if accepted and confirmed != head:
            raise RuntimeError("protected release witness did not persist its checkpoint")
        return accepted


def _protected_release_authority_witness(
    provider: ModuleType,
    provider_path: Path,
    witness: object,
    witness_identity: str,
) -> bool:
    witness_class = type(witness)
    if (
        witness_class.__module__ != provider.__name__
        or hasattr(witness, "__dict__")
        or getattr(witness, "protection", None)
        != RELEASE_AUTHORITY_WITNESS_PROTECTION
        or getattr(witness, "witness_identity", None) != witness_identity
    ):
        return False
    for name in ("current", "advance"):
        function = witness_class.__dict__.get(name)
        method = getattr(witness, name, None)
        if (
            not isinstance(function, FunctionType)
            or function.__module__ != provider.__name__
            or function.__code__.co_filename != str(provider_path)
            or not callable(method)
            or getattr(method, "__self__", None) is not witness
            or getattr(method, "__func__", None) is not function
        ):
            return False
    return True


def _resolve_external_release_attestation_authority(
    *,
    installed_root: Path | None,
    runtime_owner_state: Path | None,
    candidate_digest: str,
) -> ExternalReleaseAttestationAuthority | None:
    """Resolve only an independently provisioned, publisher-signed authority."""

    if (
        installed_root is None
        or runtime_owner_state is None
        or not isinstance(candidate_digest, str)
        or SHA256.fullmatch(candidate_digest) is None
    ):
        return None
    owner_binding = _qa_receipt_owner_binding(installed_root, runtime_owner_state)
    if SHA256.fullmatch(owner_binding) is None:
        return None
    opened = _open_system_release_authority_directory()
    if opened is None:
        return None
    directory, directory_descriptor = opened
    descriptors = [directory_descriptor]
    try:
        directory_details = os.fstat(directory_descriptor)
        if (
            directory != RELEASE_AUTHORITY_SYSTEM_DIRECTORY
            or not stat.S_ISDIR(directory_details.st_mode)
            or directory_details.st_uid != 0
            or directory_details.st_mode & 0o022
            or os.access(directory, os.W_OK)
        ):
            return None
        files: dict[str, tuple[bytes, int]] = {}
        for name in RELEASE_AUTHORITY_FILE_LIMITS:
            artifact = _read_system_release_authority_file(
                directory, directory_descriptor, name
            )
            if artifact is None:
                return None
            files[name] = artifact
            descriptors.append(artifact[1])

        attestation = _load_external_release_attestation()
        bootstrap_bytes = files["bootstrap.json"][0]
        try:
            decoded = json.loads(
                bootstrap_bytes, object_pairs_hook=attestation._json_no_duplicates
            )
        except (UnicodeError, ValueError, json.JSONDecodeError):
            return None
        if attestation._canonical_bytes(decoded) != bootstrap_bytes:
            return None
        bootstrap = attestation._exact_dict(
            decoded,
            RELEASE_AUTHORITY_BOOTSTRAP_FIELDS,
            "protected release authority bootstrap",
        )
        publisher = attestation._exact_dict(
            bootstrap["publisher"],
            {"identity", "fingerprint"},
            "protected release publisher",
        )
        provider_claim = attestation._exact_dict(
            bootstrap["provider"],
            {"file", "sha256"},
            "protected release authority provider",
        )
        witness_claim = attestation._exact_dict(
            bootstrap["witness"],
            {"durability", "fingerprint", "identity", "protection", "socket"},
            "protected release witness",
        )
        identity = attestation._identity(
            publisher["identity"], "protected release publisher"
        )
        fingerprint = attestation._fingerprint(
            publisher["fingerprint"], "protected release publisher"
        )
        policy_sha256 = attestation._hash(
            bootstrap["policySha256"], "protected release policy"
        )
        provider_sha256 = attestation._hash(
            provider_claim["sha256"], "protected release authority provider"
        )
        witness_identity = attestation._safe_name(
            witness_claim["identity"], "protected release witness"
        )
        witness_fingerprint = attestation._fingerprint(
            witness_claim["fingerprint"], "protected release witness"
        )
        if (
            bootstrap["contractVersion"] != CONTRACT_VERSION
            or bootstrap["purpose"] != RELEASE_AUTHORITY_BOOTSTRAP_PURPOSE
            or bootstrap["candidateDigest"] != candidate_digest
            or bootstrap["ownerBindingSha256"] != owner_binding
            or provider_claim["file"] != "provider.py"
            or witness_claim["protection"]
            != RELEASE_AUTHORITY_WITNESS_PROTECTION
            or witness_claim["durability"]
            != RELEASE_AUTHORITY_WITNESS_DURABILITY
            or witness_claim["socket"] != RELEASE_AUTHORITY_WITNESS_SOCKET_NAME
        ):
            return None
        pinned_roots = attestation._allowed_signer_roots(
            files["publisher.allowed_signers"][0]
        )
        if pinned_roots != {identity: fingerprint}:
            return None
        pinned_witness_roots = attestation._allowed_signer_roots(
            files["witness.allowed_signers"][0]
        )
        if (
            pinned_witness_roots != {witness_identity: witness_fingerprint}
            or witness_fingerprint == fingerprint
        ):
            return None
        attestation._signature_text(
            files["bootstrap.sig"][0], "protected release bootstrap"
        )
        verification = subprocess.run(
            [
                attestation._trusted_ssh_keygen(),
                "-Y",
                "verify",
                "-f",
                f"/dev/fd/{files['publisher.allowed_signers'][1]}",
                "-I",
                identity,
                "-n",
                RELEASE_AUTHORITY_BOOTSTRAP_NAMESPACE,
                "-s",
                f"/dev/fd/{files['bootstrap.sig'][1]}",
            ],
            input=bootstrap_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            pass_fds=(
                files["publisher.allowed_signers"][1],
                files["bootstrap.sig"][1],
            ),
            check=False,
            timeout=15,
        )
        if verification.returncode != 0:
            return None

        root = Path(installed_root).expanduser().resolve(strict=True)
        owner = json.loads(Path(runtime_owner_state).read_text(encoding="utf-8"))
        runtime = Path(str(owner["runtimeDir"])).resolve(strict=True)
        policy = attestation.load_trust_policy(
            root,
            expected_policy_sha256=policy_sha256,
            expected_candidate_digest=candidate_digest,
        )
        if (
            policy.publisher_identity != identity
            or policy.publisher_fingerprint != fingerprint
            or any(
                producer.fingerprint == witness_fingerprint
                for producer in policy.producers.values()
            )
        ):
            return None

        provider_bytes = files["provider.py"][0]
        if hashlib.sha256(provider_bytes).hexdigest() != provider_sha256:
            return None
        provider_path = directory / "provider.py"
        provider = ModuleType(RELEASE_AUTHORITY_PROVIDER_MODULE)
        provider.__file__ = str(provider_path)
        provider.__package__ = None
        exec(compile(provider_bytes, str(provider_path), "exec"), provider.__dict__)
        resolve = provider.__dict__.get("resolve_release_attestation_authority")
        if (
            not isinstance(resolve, FunctionType)
            or resolve.__module__ != provider.__name__
            or resolve.__code__.co_filename != str(provider_path)
        ):
            return None
        result = resolve(
            candidate_digest=candidate_digest,
            owner_binding_sha256=owner_binding,
            policy_sha256=policy_sha256,
            publisher_identity=identity,
            publisher_fingerprint=fingerprint,
            witness_identity=witness_identity,
        )
        if type(result) is not dict or set(result) != (
            RELEASE_AUTHORITY_PROVIDER_RESULT_FIELDS
        ):
            return None
        expected = {
            "contractVersion": CONTRACT_VERSION,
            "candidateDigest": candidate_digest,
            "ownerBindingSha256": owner_binding,
            "policySha256": policy_sha256,
            "publisherIdentity": identity,
            "publisherFingerprint": fingerprint,
            "witnessIdentity": witness_identity,
        }
        if any(result.get(name) != value for name, value in expected.items()):
            return None
        witness = result["ledgerWitness"]
        if not _protected_release_authority_witness(
            provider, provider_path, witness, witness_identity
        ):
            return None
        protected_witness = _ProtectedExternalReleaseLedgerWitness(
            attestation=attestation,
            candidate_digest=candidate_digest,
            endpoint=directory / RELEASE_AUTHORITY_WITNESS_SOCKET_NAME,
            owner_binding=owner_binding,
            signer_roots=files["witness.allowed_signers"][0],
            witness_identity=witness_identity,
        )
        if not protected_witness.prove():
            return None
        attestation._require_witness(protected_witness)
        return ExternalReleaseAttestationAuthority(
            expected_policy_sha256=policy_sha256,
            ledger_path=runtime / QA_RELEASE_ATTESTATION_LEDGER_NAME,
            ledger_witness=protected_witness,
        )
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        SyntaxError,
        TypeError,
        UnicodeError,
        ValueError,
        subprocess.SubprocessError,
    ):
        return None
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _qa_receipt_owner_binding(
    installed_root: Path | None,
    runtime_owner_state: Path | None,
) -> str:
    if not _runtime_owner_state_proves_active(installed_root, runtime_owner_state):
        return ""
    assert runtime_owner_state is not None
    try:
        owner = json.loads(Path(runtime_owner_state).read_text(encoding="utf-8"))
        runtime_dir = Path(str(owner["runtimeDir"])).resolve(strict=True)
        details = runtime_dir.stat()
        if (
            not stat.S_ISDIR(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o700
            or details.st_uid != os.getuid()
        ):
            return ""
        return _canonical_hash(
            {
                "contractVersion": CONTRACT_VERSION,
                "ownerUid": details.st_uid,
                "repoRootSha256": _sha256_bytes(
                    str(owner["repoRoot"]).encode("utf-8")
                ),
                "runtimeDirSha256": _sha256_bytes(str(runtime_dir).encode("utf-8")),
                "runtimeProfile": str(owner["runtimeProfile"]),
            }
        )
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return ""


def _external_release_attestation_context(
    authority: ExternalReleaseAttestationAuthority | None,
    *,
    installed_root: Path | None,
    runtime_owner_state: Path | None,
    candidate_digest: str,
) -> tuple[object, object, Path, object] | None:
    if (
        authority is None
        or not isinstance(authority, ExternalReleaseAttestationAuthority)
        or installed_root is None
        or runtime_owner_state is None
        or SHA256.fullmatch(str(authority.expected_policy_sha256 or "")) is None
        or not _qa_receipt_owner_binding(installed_root, runtime_owner_state)
    ):
        return None
    try:
        module = _load_external_release_attestation()
        root = Path(installed_root).expanduser().resolve(strict=True)
        owner = json.loads(Path(runtime_owner_state).read_text(encoding="utf-8"))
        runtime = Path(str(owner["runtimeDir"])).resolve(strict=True)
        ledger = Path(authority.ledger_path).expanduser().resolve(strict=False)
        if ledger != runtime / QA_RELEASE_ATTESTATION_LEDGER_NAME:
            return None
        policy = module.load_trust_policy(
            root,
            expected_policy_sha256=authority.expected_policy_sha256,
            expected_candidate_digest=candidate_digest,
        )
        witness = module._require_witness(authority.ledger_witness)
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ):
        return None
    return module, policy, ledger, witness


def _bind_catalog_gates_to_qa_receipts(
    records: tuple[GateRecord, ...],
    qa_case_receipts: object,
    artifact_identity: object,
    *,
    readiness_facts: object = None,
    mode: str,
    installed_root: Path | None,
    runtime_owner_state: Path | None,
    external_attestation_authority: ExternalReleaseAttestationAuthority | None = None,
) -> tuple[tuple[GateRecord, ...], dict[str, object]]:
    expected_ids = {
        record.case_id
        for record in records
        if record.source.startswith("qa/") and not record.case_id.startswith("CATALOG-")
    }
    candidate_digest, artifact_digest = _qa_candidate_digests(
        artifact_identity,
        readiness_facts,
    )
    raw_receipts = (
        qa_case_receipts.get("receipts")
        if isinstance(qa_case_receipts, dict)
        else None
    )
    summary = {
        "contractVersion": CONTRACT_VERSION,
        "status": "blocked",
        "receiptCount": len(raw_receipts) if isinstance(raw_receipts, list) else 0,
        "receiptDigest": _canonical_hash(qa_case_receipts),
        "candidateDigest": candidate_digest,
        "artifactDigest": artifact_digest,
        "maxAgeSeconds": QA_RECEIPT_TTL_SECONDS,
    }
    if not candidate_digest or not artifact_digest:
        reason = "qa_receipt_candidate_unavailable"
        return (
            tuple(
                GateRecord(record.case_id, "UNKNOWN", record.source, reason)
                if record.case_id in expected_ids and record.status == PASS
                else record
                for record in records
            ),
            summary,
        )
    if (
        not isinstance(qa_case_receipts, dict)
        or set(qa_case_receipts) != {"contractVersion", "receipts"}
        or qa_case_receipts.get("contractVersion") != CONTRACT_VERSION
        or not isinstance(raw_receipts, list)
    ):
        reason = "qa_receipt_set_missing" if qa_case_receipts is None else "qa_receipt_set_invalid"
        return (
            tuple(
                GateRecord(record.case_id, "UNKNOWN", record.source, reason)
                if record.case_id in expected_ids and record.status == PASS
                else record
                for record in records
            ),
            summary,
        )

    authority = _qa_receipt_attestation_authority(
        installed_root, runtime_owner_state
    )
    owner_binding = _qa_receipt_owner_binding(installed_root, runtime_owner_state)
    supplied_external = external_attestation_authority
    if mode != "local-qa":
        # Dependency injection is available only to explicit PRE-GATE local QA.
        # A production caller cannot introduce, replace, or "confirm" authority.
        supplied_external = (
            None
            if supplied_external is not None
            else _resolve_external_release_attestation_authority(
                installed_root=installed_root,
                runtime_owner_state=runtime_owner_state,
                candidate_digest=candidate_digest,
            )
        )
    external_context = _external_release_attestation_context(
        supplied_external,
        installed_root=installed_root,
        runtime_owner_state=runtime_owner_state,
        candidate_digest=candidate_digest,
    )
    indexed: dict[str, dict[str, object]] = {}
    invalid_ids: set[str] = set()
    replayed_ids: set[str] = set()
    nonce_owners: dict[str, str] = {}
    set_invalid = False
    now = datetime.now(timezone.utc)
    for raw in raw_receipts:
        if not isinstance(raw, dict):
            set_invalid = True
            continue
        case_id = str(raw.get("caseId") or "")
        if case_id in indexed or case_id in invalid_ids:
            invalid_ids.add(case_id)
            indexed.pop(case_id, None)
            continue
        if case_id not in expected_ids:
            set_invalid = True
            continue
        indexed[case_id] = raw
        nonce = str(raw.get("receiptNonce") or "")
        if raw.get("status") == PASS and QA_RECEIPT_NONCE.fullmatch(nonce):
            previous_case = nonce_owners.get(nonce)
            if previous_case is not None:
                replayed_ids.update((previous_case, case_id))
            else:
                nonce_owners[nonce] = case_id

    bound: list[GateRecord] = []
    all_verified = (
        not set_invalid
        and set(indexed) == expected_ids
        and not invalid_ids
        and not replayed_ids
    )
    for record in records:
        if record.case_id not in expected_ids:
            bound.append(record)
            continue
        receipt = indexed.get(record.case_id)
        uses_external_attestation = isinstance(receipt, dict) and (
            "publisherAttestation" in receipt
        )
        uses_artifact_claims = isinstance(receipt, dict) and (
            "artifactClaims" in receipt
        )
        reason = ""
        if record.case_id in invalid_ids:
            reason = "qa_receipt_duplicate"
        elif record.case_id in replayed_ids:
            reason = "qa_receipt_replay"
        elif receipt is None:
            reason = "qa_receipt_missing"
        elif (
            receipt.get("status") == PASS
            and "attestation" not in receipt
            and not uses_external_attestation
        ):
            reason = "qa_receipt_attestation_missing"
        elif set(receipt) != {
            "artifactDigest",
            *(("artifactClaims",) if uses_artifact_claims else ()),
            "candidateDigest",
            "caseId",
            "evidenceDigest",
            "runAt",
            "status",
            "surface",
            *(
                (
                    QA_RECEIPT_EXTERNAL_ATTESTATION_FIELDS
                    | (QA_RECEIPT_ATTESTATION_FIELDS - {"attestation"})
                    if uses_external_attestation
                    else QA_RECEIPT_ATTESTATION_FIELDS
                )
                if receipt.get("status") == PASS
                else ()
            ),
            *(
                ("serviceAckDigest", "serviceAckSessionRef")
                if record.case_id in QA_RECEIPT_SERVICE_ACK_CASES
                and receipt.get("status") == PASS
                else ()
            ),
        }:
            reason = "qa_receipt_invalid"
        else:
            try:
                run_at = datetime.fromisoformat(str(receipt.get("runAt") or ""))
            except ValueError:
                run_at = datetime.min.replace(tzinfo=timezone.utc)
            if (
                run_at.tzinfo is None
                or run_at > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS)
                or now - run_at > timedelta(seconds=QA_RECEIPT_TTL_SECONDS)
            ):
                reason = "qa_receipt_stale"
            elif receipt.get("status") != PASS:
                reason = "qa_receipt_not_pass"
            elif str(receipt.get("surface") or "") not in QA_RECEIPT_SURFACES:
                reason = "qa_receipt_surface_invalid"
            elif (
                required_surface := QA_RECEIPT_CASE_SURFACES.get(record.case_id)
            ) is not None and receipt.get("surface") != required_surface:
                reason = "qa_receipt_surface_mismatch"
            elif SHA256.fullmatch(str(receipt.get("evidenceDigest") or "")) is None:
                reason = "qa_receipt_evidence_invalid"
            elif (
                record.case_id in QA_RECEIPT_SERVICE_ACK_CASES
                and (
                    SHA256_REF.fullmatch(
                        str(receipt.get("serviceAckDigest") or "")
                    )
                    is None
                    or QA_RECEIPT_SERVICE_SESSION.fullmatch(
                        str(receipt.get("serviceAckSessionRef") or "")
                    )
                    is None
                )
            ):
                reason = "qa_receipt_service_ack_invalid"
            elif uses_artifact_claims and not _qa_receipt_artifact_claims_match(
                record.case_id,
                receipt.get("artifactClaims"),
                artifact_identity,
            ):
                reason = "qa_receipt_artifact_claim_mismatch"
            elif (
                (mode != "local-qa" or uses_external_attestation)
                and receipt.get("candidateDigest") != candidate_digest
            ):
                reason = "qa_receipt_candidate_mismatch"
            elif (
                (mode != "local-qa" or uses_external_attestation or not uses_artifact_claims)
                and receipt.get("artifactDigest") != artifact_digest
            ):
                reason = "qa_receipt_artifact_mismatch"
            elif SHA256.fullmatch(
                str(receipt.get("ownerBindingSha256") or "")
            ) is None:
                reason = "qa_receipt_owner_invalid"
            elif QA_RECEIPT_NONCE.fullmatch(
                str(receipt.get("receiptNonce") or "")
            ) is None:
                reason = "qa_receipt_nonce_invalid"
            elif SAFE_NAME.fullmatch(str(receipt.get("verifierId") or "")) is None:
                reason = "qa_receipt_verifier_invalid"
            elif SHA256.fullmatch(
                str(receipt.get("verifierManifestSha256") or "")
            ) is None:
                reason = "qa_receipt_verifier_invalid"
            elif not owner_binding:
                reason = "qa_receipt_attestation_authority_unavailable"
            elif not hmac.compare_digest(
                str(receipt.get("ownerBindingSha256") or ""), owner_binding
            ):
                reason = "qa_receipt_owner_mismatch"
            elif not uses_external_attestation and authority is None:
                reason = "qa_receipt_attestation_authority_unavailable"
            elif not uses_external_attestation and not _qa_receipt_attestation_valid(
                receipt, authority
            ):
                reason = "qa_receipt_attestation_invalid"
            elif (
                registration := REGISTERED_SEMANTIC_VERIFIERS.get(record.case_id)
            ) is None or receipt.get("verifierId") != registration.get("id"):
                reason = "qa_receipt_verifier_unregistered"
            elif uses_external_attestation:
                if external_context is None:
                    reason = "qa_receipt_external_attestation_missing"
                else:
                    verifier, policy, ledger_path, witness = external_context
                    try:
                        verifier.verify_release_receipt(
                            receipt,
                            policy=policy,
                            ledger_path=ledger_path,
                            ledger_witness=witness,
                            expected_case_id=record.case_id,
                            expected_surface=str(receipt["surface"]),
                            expected_candidate_digest=candidate_digest,
                            expected_artifact_digest=artifact_digest,
                            expected_owner_binding=owner_binding,
                            expected_evidence_digest=str(receipt["evidenceDigest"]),
                            expected_verifier_id=str(registration["id"]),
                            expected_verifier_manifest_sha256=str(
                                receipt["verifierManifestSha256"]
                            ),
                            expected_service_ack_digest=(
                                str(receipt["serviceAckDigest"])
                                if record.case_id in QA_RECEIPT_SERVICE_ACK_CASES
                                else None
                            ),
                            expected_service_ack_session_ref=(
                                str(receipt["serviceAckSessionRef"])
                                if record.case_id in QA_RECEIPT_SERVICE_ACK_CASES
                                else None
                            ),
                            now=now,
                        )
                    except (AttributeError, RuntimeError, TypeError, ValueError):
                        reason = "qa_receipt_external_attestation_invalid"
            elif mode != "local-qa":
                reason = "qa_receipt_external_attestation_missing"
        if reason:
            all_verified = False
            bound.append(
                GateRecord(record.case_id, "UNKNOWN", record.source, reason)
                if record.status == PASS
                else record
            )
        else:
            bound.append(GateRecord(record.case_id, PASS, record.source, "qa_receipt_verified"))
    if all_verified:
        summary["status"] = "verified"
    return tuple(bound), summary


def evaluate_release_gate(
    root: Path,
    *,
    mode: str = "release",
    allow_local_qa_override: bool = False,
    readiness_facts: object = None,
    artifact_identity: object = None,
    qa_case_receipts: object = None,
    installed_prompt_bundle_path: Path | None = None,
    installed_root: Path | None = None,
    runtime_owner_state: Path | None = None,
    external_attestation_authority: ExternalReleaseAttestationAuthority | None = None,
) -> GateEvaluation:
    if mode not in {"default", "release", "local-qa"}:
        raise ValueError(f"unsupported release-gate mode: {mode}")
    if mode == "local-qa" and not allow_local_qa_override:
        raise ValueError("local-qa mode requires an explicit local QA override")
    if mode != "local-qa" and allow_local_qa_override:
        raise ValueError("local QA override is valid only in local-qa mode")

    source_defaults_valid, source_failures = _source_default_records(
        Path(root).resolve()
    )
    catalog_gates, qa_receipt_summary = _bind_catalog_gates_to_qa_receipts(
        load_required_gates(Path(root)),
        qa_case_receipts,
        artifact_identity,
        readiness_facts=readiness_facts,
        mode=mode,
        installed_root=installed_root,
        runtime_owner_state=runtime_owner_state,
        external_attestation_authority=external_attestation_authority,
    )
    gates = catalog_gates + tuple(source_failures)
    open_gates = tuple(gate for gate in gates if gate.status != PASS)
    effective_readiness_facts = _remeasure_storage_pressure(
        readiness_facts,
        installed_prompt_bundle_path,
    )
    readiness_checks = _typed_readiness_checks(
        effective_readiness_facts, installed_prompt_bundle_path
    )
    blocking_checks = tuple(check for check in readiness_checks if check.status != PASS)
    artifact_checks, public_artifact_identity = _artifact_identity_checks(
        Path(root).resolve(),
        artifact_identity,
        installed_prompt_bundle_path,
        installed_root,
        runtime_owner_state,
    )
    blocking_artifact_checks = tuple(
        check for check in artifact_checks if check.status != PASS
    )
    owner_binding = _runtime_owner_projection(installed_root, runtime_owner_state)
    integrity_ready = not blocking_checks and not blocking_artifact_checks
    candidate_ready = (
        not open_gates
        and source_defaults_valid
        and integrity_ready
        and qa_receipt_summary["status"] == "verified"
        and bool(owner_binding)
    )
    local_qa_shape_valid = (
        all(check.status != "UNKNOWN" for check in readiness_checks)
        and _artifact_identity_shape_valid(artifact_identity)
        and bool(owner_binding)
    )
    release_ready = candidate_ready and mode != "local-qa"

    if mode == "local-qa":
        exposure_allowed = source_defaults_valid and local_qa_shape_valid
        label = "PRE-GATE / NOT READY"
    else:
        exposure_allowed = release_ready
        label = "READY" if release_ready else "NOT READY"

    return GateEvaluation(
        mode=mode,
        label=label,
        release_ready=release_ready,
        exposure_allowed=exposure_allowed,
        local_qa_override=mode == "local-qa",
        source_defaults_valid=source_defaults_valid,
        gates=gates,
        open_gates=open_gates,
        readiness_checks=readiness_checks,
        blocking_checks=blocking_checks,
        readiness_facts=_public_readiness_facts(effective_readiness_facts),
        artifact_checks=artifact_checks,
        blocking_artifact_checks=blocking_artifact_checks,
        artifact_identity=public_artifact_identity,
        qa_receipt_summary=qa_receipt_summary,
        owner_binding=owner_binding,
    )


def _text_report(result: GateEvaluation) -> str:
    lines = [
        f"Parallel Work: {result.label}",
        f"Required gates: {len(result.gates) - len(result.open_gates)}/{len(result.gates)} PASS",
    ]
    if result.open_gates:
        lines.append("Open gates:")
        lines.extend(f"- {gate.case_id}: {gate.status}" for gate in result.open_gates)
    if result.blocking_checks:
        lines.append("Readiness blockers:")
        lines.extend(
            f"- {check.check_id}: {check.status} ({check.reason})"
            for check in result.blocking_checks
        )
    if result.blocking_artifact_checks:
        lines.append("Artifact blockers:")
        lines.extend(
            f"- {check.check_id}: {check.status} ({check.reason})"
            for check in result.blocking_artifact_checks
        )
    return "\n".join(lines)


def _load_readiness_facts(path: Path | None) -> object:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload


def _load_artifact_identity(path: Path | None) -> object:
    return _load_readiness_facts(path)


def _load_qa_case_receipts(path: Path | None) -> object:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return {}


def _write_snapshot(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        os.chmod(path, 0o600)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _serialized_check_map(
    value: object,
    expected_ids: set[str],
) -> dict[str, dict[str, object]] | None:
    if not isinstance(value, list) or len(value) != len(expected_ids):
        return None
    checks: dict[str, dict[str, object]] = {}
    for raw in value:
        if not isinstance(raw, dict):
            return None
        check_id = str(raw.get("check_id") or "")
        status = str(raw.get("status") or "")
        reason = str(raw.get("reason") or "")
        if (
            check_id not in expected_ids
            or check_id in checks
            or status not in {PASS, "FAIL", "UNKNOWN"}
            or (status == PASS and reason)
            or (status != PASS and not _safe_reason(reason, ""))
        ):
            return None
        checks[check_id] = {
            "check_id": check_id,
            "status": status,
            "reason": reason,
        }
    return checks if set(checks) == expected_ids else None


def _serialized_gate_list(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list) or not value:
        return None
    gates: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            return None
        case_id = str(raw.get("case_id") or "")
        status = str(raw.get("status") or "")
        source = str(raw.get("source") or "")
        if (
            not SAFE_NAME.fullmatch(case_id)
            or case_id in seen
            or status
            not in {PASS, "FAIL", "BLOCKED", "PARTIAL", "NOT_RUN", "UNKNOWN", "MISSING"}
            or not source
            or Path(source).is_absolute()
            or ".." in Path(source).parts
            or not (source == "config.schema.yaml" or source.startswith("qa/"))
            or raw.get("detail") != "[redacted]"
        ):
            return None
        seen.add(case_id)
        gates.append(
            {
                "case_id": case_id,
                "status": status,
                "source": source,
                "detail": "[redacted]",
            }
        )
    return gates


def _live_qa_receipt_contract_matches(
    payload: dict[str, object],
    gates: list[dict[str, object]],
    runtime_dir: Path,
    *,
    external_attestation_authority: ExternalReleaseAttestationAuthority | None = None,
) -> bool:
    projection = payload.get("owner_binding")
    if not isinstance(projection, dict):
        return False
    try:
        profile = str(projection["runtimeProfile"])
        owner_state = (
            runtime_dir.parent
            / "state"
            / "runtime"
            / profile
            / "stack-owner.json"
        ).resolve(strict=True)
        owner = json.loads(owner_state.read_text(encoding="utf-8"))
        installed_root = Path(str(owner["repoRoot"])).expanduser().resolve(strict=True)
        owner_runtime = Path(str(owner["runtimeDir"])).expanduser().resolve(strict=True)
        source_defaults_valid, source_failures = _source_default_records(installed_root)
        trusted_records = load_required_gates(installed_root) + tuple(source_failures)
        live_readiness = json.loads(
            (runtime_dir / "parallel-work-readiness-facts.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    if owner_runtime != runtime_dir or source_defaults_valid is not payload.get(
        "source_defaults_valid"
    ):
        return False

    receipt_path = runtime_dir / "parallel-work-qa-case-receipts.json"
    live_receipts = _load_qa_case_receipts(receipt_path)
    rebound, expected_summary = _bind_catalog_gates_to_qa_receipts(
        trusted_records,
        live_receipts,
        payload.get("artifact_identity"),
        readiness_facts=live_readiness,
        mode=str(payload.get("mode") or ""),
        installed_root=installed_root,
        runtime_owner_state=owner_state,
        external_attestation_authority=external_attestation_authority,
    )
    expected_gates = [
        {
            "case_id": gate.case_id,
            "status": gate.status,
            "source": gate.source,
            "detail": "[redacted]",
        }
        for gate in rebound
    ]
    summary = payload.get("qa_receipt_summary")
    return expected_gates == gates and summary == expected_summary


def _expected_artifact_check_statuses(
    identity: dict[str, object],
    runtime_dir: Path,
) -> dict[str, str]:
    source = identity["source"]
    nested = identity["nestedComponents"]
    prebuilt = identity["prebuiltHelper"]
    installed = identity["installed"]
    assert isinstance(source, dict)
    assert isinstance(nested, list)
    assert isinstance(prebuilt, dict)
    assert isinstance(installed, dict)
    source_ok = (
        source.get("clean") is True
        and bool(source.get("revision"))
        and bool(source.get("componentsLockSha256"))
        and source.get("worktreeHash") == _sha256_bytes(b"")
    )
    nested_ok = bool(nested) and all(
        isinstance(item, dict)
        and item.get("clean") is True
        and item.get("worktreeHash") == _sha256_bytes(b"")
        and item.get("pin") == item.get("revision")
        for item in nested
    )
    prebuilt_ok = (
        prebuilt.get("binaryExecutable") is True
        and prebuilt.get("sourceDeclaredSha256")
        == prebuilt.get("sourceMeasuredSha256")
        and prebuilt.get("binaryDeclaredSha256")
        == prebuilt.get("binaryMeasuredSha256")
    )
    installed_ok = (
        source_ok
        and nested_ok
        and prebuilt_ok
        and installed.get("rootRevision") == source.get("revision")
        and installed.get("componentsLockSha256")
        == source.get("componentsLockSha256")
        and installed.get("nestedRevisionsHash") == _nested_revision_hash(nested)
        and installed.get("prebuiltSourceSha256")
        == prebuilt.get("sourceMeasuredSha256")
        and installed.get("prebuiltBinarySha256")
        == prebuilt.get("binaryMeasuredSha256")
        and installed.get("promptBundleSha256")
        == _sha256_file(runtime_dir / "prompt-bundle.json")
        and all(
            SHA256.fullmatch(str(installed.get(key) or "")) is not None
            for key in INSTALLED_ARTIFACT_HASH_KEYS[5:]
        )
    )
    return {
        "SOURCE-IDENTITY": PASS if source_ok else "FAIL",
        "NESTED-PINS": PASS if nested_ok else "FAIL",
        "PREBUILT-IDENTITY": PASS if prebuilt_ok else "FAIL",
        "INSTALLED-ARTIFACT": PASS if installed_ok else "FAIL",
    }


def _owner_projection_matches_live_runtime(
    value: object,
    runtime_dir: Path,
) -> bool:
    if not isinstance(value, dict) or value.get("contractVersion") != CONTRACT_VERSION:
        return False
    required_hashes = (
        "ownerBindingSha256",
        "ownerStateSha256",
        "repoRootSha256",
        "runtimeDirSha256",
        "configFileSha256",
        "componentsLockFileSha256",
        "ownerExecutablePathSha256",
        "ownerProcessCwdSha256",
        "ownerProcessCommandSha256",
    )
    if (
        not SAFE_NAME.fullmatch(str(value.get("runtimeProfile") or ""))
        or str(value.get("command") or "") not in {"start", "launch"}
        or str(value.get("ownerLaunchMode") or "") not in {"attached", "detached"}
        or not str(value.get("ownerPid") or "").isdigit()
        or int(str(value.get("ownerPid"))) <= 1
        or not _normalized_process_value(value.get("ownerProcessStartedAt"))
        or any(SHA256.fullmatch(str(value.get(key) or "")) is None for key in required_hashes)
        or value.get("maxAgeSeconds") != SNAPSHOT_TTL_SECONDS
    ):
        return False
    try:
        generated_at = datetime.fromisoformat(str(value.get("generatedAt") or ""))
        expires_at = datetime.fromisoformat(str(value.get("expiresAt") or ""))
        runtime = runtime_dir.expanduser().resolve(strict=True)
        app_support = runtime.parent
        profile = str(value["runtimeProfile"])
        owner_state = (
            app_support / "state" / "runtime" / profile / "stack-owner.json"
        ).resolve(strict=True)
        payload = json.loads(owner_state.read_text(encoding="utf-8"))
        installed_root = Path(str(payload["repoRoot"])).expanduser().resolve(strict=True)
        config_file = Path(str(payload["configFile"])).expanduser().resolve(strict=True)
        components_lock_file = Path(str(payload["componentsLockFile"])).expanduser().resolve(
            strict=True
        )
        executable = Path(str(payload["ownerExecutablePath"])).expanduser().resolve(
            strict=True
        )
        owner_cwd = Path(str(payload["ownerProcessCwd"])).expanduser().resolve(
            strict=True
        )
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    if (
        generated_at.tzinfo is None
        or expires_at.tzinfo is None
        or generated_at > datetime.now(timezone.utc)
        + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS)
        or expires_at <= datetime.now(timezone.utc)
        or expires_at - generated_at != timedelta(seconds=SNAPSHOT_TTL_SECONDS)
    ):
        return False
    expected = {
        "contractVersion": CONTRACT_VERSION,
        "runtimeProfile": profile,
        "command": str(payload.get("command") or ""),
        "ownerLaunchMode": str(payload.get("ownerLaunchMode") or ""),
        "ownerPid": str(payload.get("ownerPid") or ""),
        "ownerProcessStartedAt": _normalized_process_value(
            payload.get("ownerProcessStartedAt")
        ),
        "ownerBindingSha256": str(payload.get("ownerBindingSha256") or ""),
        "ownerStateSha256": _sha256_file(owner_state),
        "repoRootSha256": _sha256_bytes(str(installed_root).encode("utf-8")),
        "runtimeDirSha256": _sha256_bytes(str(runtime).encode("utf-8")),
        "configFileSha256": _sha256_bytes(str(config_file).encode("utf-8")),
        "componentsLockFileSha256": _sha256_bytes(
            str(components_lock_file).encode("utf-8")
        ),
        "ownerExecutablePathSha256": _sha256_bytes(
            str(executable).encode("utf-8")
        ),
        "ownerProcessCwdSha256": _sha256_bytes(str(owner_cwd).encode("utf-8")),
        "ownerProcessCommandSha256": _sha256_bytes(
            _normalized_process_value(payload.get("ownerProcessCommand")).encode(
                "utf-8"
            )
        ),
        "maxAgeSeconds": SNAPSHOT_TTL_SECONDS,
    }
    return (
        str(payload.get("runtimeDir") or "") == str(runtime)
        and all(value.get(key) == expected[key] for key in expected)
        and _runtime_owner_state_proves_active(installed_root, owner_state)
    )


def _live_runtime_claim_inputs_match(
    payload: dict[str, object],
    runtime: Path,
) -> bool:
    projection = payload.get("owner_binding")
    if not isinstance(projection, dict):
        return False
    try:
        profile = str(projection["runtimeProfile"])
        owner_state = (
            runtime.parent
            / "state"
            / "runtime"
            / profile
            / "stack-owner.json"
        ).resolve(strict=True)
        owner = json.loads(owner_state.read_text(encoding="utf-8"))
        installed_root = Path(str(owner["repoRoot"])).expanduser().resolve(strict=True)
        readiness_path = (runtime / "parallel-work-readiness-facts.json").resolve(
            strict=True
        )
        identity_path = (runtime / "parallel-work-artifact-identity.json").resolve(
            strict=True
        )
        prompt_path = (runtime / "prompt-bundle.json").resolve(strict=True)
        live_readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        live_identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return False
    effective_live_readiness = _remeasure_storage_pressure(
        live_readiness,
        prompt_path,
    )
    if (
        _stable_readiness_claim_inputs(effective_live_readiness)
        != _stable_readiness_claim_inputs(payload.get("readiness_facts"))
        or _public_artifact_identity(live_identity) != payload.get("artifact_identity")
    ):
        return False
    measured_identity = _public_artifact_identity(
        _measured_artifact_identity(
            installed_root,
            prompt_path,
            installed_root,
            owner_state,
        )
    )
    if measured_identity != payload.get("artifact_identity"):
        return False
    try:
        source_defaults_valid, _source_failures = _source_default_records(installed_root)
    except (OSError, RuntimeError, ValueError):
        return False
    return source_defaults_valid is payload.get("source_defaults_valid")


def _stable_readiness_claim_inputs(value: object) -> dict[str, object]:
    """Bind runtime readiness policy without pinning volatile disk measurements."""

    public = _public_readiness_facts(value)
    prompt = public.get("promptLayers")
    storage = public.get("storagePressure")
    if (
        public.get("contractVersion") != CONTRACT_VERSION
        or not isinstance(prompt, dict)
        or not _storage_pressure_shape_valid(storage)
    ):
        return {}
    assert isinstance(storage, dict)
    stable_storage = {
        key: item
        for key, item in storage.items()
        if key not in {"status", "usedPercent", "availableBytes"}
    }
    return {
        "contractVersion": CONTRACT_VERSION,
        "promptLayers": prompt,
        "storagePolicy": stable_storage,
    }


def _serialized_readiness_remains_conservative(
    current: tuple[ReadinessCheck, ...],
    serialized: object,
    *,
    allow_storage_improvement: bool,
) -> bool:
    if not isinstance(serialized, list) or len(serialized) != len(current):
        return False
    for current_check, serialized_check in zip(current, serialized):
        current_record = asdict(current_check)
        if current_record == serialized_check:
            continue
        storage_improved = (
            allow_storage_improvement
            and current_record
            == {"check_id": "STORAGE-PRESSURE", "status": PASS, "reason": ""}
            and serialized_check
            == {
                "check_id": "STORAGE-PRESSURE",
                "status": "FAIL",
                "reason": "storage_pressure",
            }
        )
        if not storage_improved:
            return False
    return True


def _storage_pressure_did_not_worsen(
    current_readiness_facts: object,
    serialized_readiness_facts: object,
) -> bool:
    """Allow volatile storage drift only when its pressure state is no worse."""

    current_storage = _public_readiness_facts(current_readiness_facts).get(
        "storagePressure"
    )
    serialized_storage = _public_readiness_facts(serialized_readiness_facts).get(
        "storagePressure"
    )
    if not (
        _storage_pressure_shape_valid(current_storage)
        and _storage_pressure_shape_valid(serialized_storage)
    ):
        return False
    assert isinstance(current_storage, dict)
    assert isinstance(serialized_storage, dict)
    if current_storage.get("reason") == "storage_probe_unavailable":
        return False
    pressure_rank = {"healthy": 0, "warning": 1, "critical": 2}
    return pressure_rank[str(current_storage["status"])] <= pressure_rank[
        str(serialized_storage["status"])
    ]


def validate_serialized_release_snapshot(
    payload: object,
    runtime_dir: Path,
    *,
    external_attestation_authority: ExternalReleaseAttestationAuthority | None = None,
) -> bool:
    """Validate the full public release contract against the live runtime."""

    if not isinstance(payload, dict) or payload.get("contract_version") != CONTRACT_VERSION:
        return False
    mode = str(payload.get("mode") or "")
    if mode not in {"default", "release", "local-qa"}:
        return False
    booleans = (
        "release_ready",
        "exposure_allowed",
        "local_qa_override",
        "source_defaults_valid",
    )
    if any(not isinstance(payload.get(key), bool) for key in booleans):
        return False
    local_qa = mode == "local-qa"
    if payload["local_qa_override"] is not local_qa:
        return False

    gates = _serialized_gate_list(payload.get("gates"))
    open_gates = payload.get("open_gates")
    if gates is None or not isinstance(open_gates, list):
        return False
    expected_open = [gate for gate in gates if gate["status"] != PASS]
    if (
        open_gates != expected_open
        or payload.get("gate_count") != len(gates)
        or payload.get("open_gate_count") != len(expected_open)
    ):
        return False

    readiness = _serialized_check_map(
        payload.get("readiness_checks"), {"PROMPT-LAYERS", "STORAGE-PRESSURE"}
    )
    artifacts = _serialized_check_map(
        payload.get("artifact_checks"),
        {"SOURCE-IDENTITY", "NESTED-PINS", "PREBUILT-IDENTITY", "INSTALLED-ARTIFACT"},
    )
    if readiness is None or artifacts is None:
        return False
    expected_blocking_readiness = [
        check for check in payload["readiness_checks"] if check["status"] != PASS
    ]
    expected_blocking_artifacts = [
        check for check in payload["artifact_checks"] if check["status"] != PASS
    ]
    if (
        payload.get("blocking_checks") != expected_blocking_readiness
        or payload.get("blocking_artifact_checks") != expected_blocking_artifacts
    ):
        return False

    try:
        runtime = runtime_dir.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if not _live_qa_receipt_contract_matches(
        payload,
        gates,
        runtime,
        external_attestation_authority=external_attestation_authority,
    ):
        return False
    readiness_facts = payload.get("readiness_facts")
    current_readiness_facts = _remeasure_storage_pressure(
        readiness_facts,
        runtime / "prompt-bundle.json",
    )
    if not _storage_pressure_did_not_worsen(
        current_readiness_facts,
        readiness_facts,
    ):
        return False
    expected_readiness = _typed_readiness_checks(
        current_readiness_facts, runtime / "prompt-bundle.json"
    )
    if any(check.status == "UNKNOWN" for check in expected_readiness):
        return False
    if not _serialized_readiness_remains_conservative(
        expected_readiness,
        payload["readiness_checks"],
        allow_storage_improvement=mode == "local-qa",
    ):
        return False

    identity = payload.get("artifact_identity")
    if not _artifact_identity_shape_valid(identity):
        return False
    assert isinstance(identity, dict)
    expected_artifacts = _expected_artifact_check_statuses(identity, runtime)
    if any(
        artifacts[check_id]["status"] != status
        for check_id, status in expected_artifacts.items()
    ):
        return False
    source_identity = identity["source"]
    nested_identity = identity["nestedComponents"]
    assert isinstance(source_identity, dict)
    assert isinstance(nested_identity, list)
    source_dirty = source_identity.get("clean") is False
    nested_pins_match = bool(nested_identity) and all(
        isinstance(item, dict) and item.get("pin") == item.get("revision")
        for item in nested_identity
    )
    nested_dirty = nested_pins_match and any(
        isinstance(item, dict) and item.get("clean") is False
        for item in nested_identity
    )
    expected_artifact_reasons = {
        "SOURCE-IDENTITY": (
            "source_dirty" if source_dirty else "source_identity_mismatch"
        ),
        "NESTED-PINS": "nested_dirty" if nested_dirty else "nested_pin_mismatch",
        "PREBUILT-IDENTITY": "prebuilt_identity_mismatch",
        "INSTALLED-ARTIFACT": (
            "installed_candidate_dirty"
            if (source_dirty or nested_dirty)
            and expected_artifacts["PREBUILT-IDENTITY"] == PASS
            else "installed_artifact_mismatch"
        ),
    }
    if any(
        artifacts[check_id]["reason"]
        != ("" if status == PASS else expected_artifact_reasons[check_id])
        for check_id, status in expected_artifacts.items()
    ):
        return False
    if not _owner_projection_matches_live_runtime(payload.get("owner_binding"), runtime):
        return False
    if not _live_runtime_claim_inputs_match(payload, runtime):
        return False

    all_release_checks_pass = (
        payload["source_defaults_valid"] is True
        and not expected_open
        and all(check["status"] == PASS for check in readiness.values())
        and all(check["status"] == PASS for check in artifacts.values())
        and isinstance(payload.get("qa_receipt_summary"), dict)
        and payload["qa_receipt_summary"].get("status") == "verified"
    )
    expected_release_ready = all_release_checks_pass and not local_qa
    expected_exposure = (
        payload["source_defaults_valid"] is True
        if local_qa
        else expected_release_ready
    )
    expected_label = (
        "PRE-GATE / NOT READY"
        if local_qa
        else "READY"
        if expected_release_ready
        else "NOT READY"
    )
    return (
        payload.get("release_ready") is expected_release_ready
        and payload.get("exposure_allowed") is expected_exposure
        and payload.get("label") == expected_label
    )


def _load_canonical_snapshot(path: Path) -> tuple[Path, Path, dict[str, object]] | None:
    try:
        snapshot_path = path.expanduser().resolve(strict=True)
        runtime = snapshot_path.parent.resolve(strict=True)
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, json.JSONDecodeError):
        return None
    if (
        snapshot_path != runtime / "parallel-work-release-gate.json"
        or not isinstance(payload, dict)
    ):
        return None
    return snapshot_path, runtime, payload


def validate_snapshot_file(path: Path) -> bool:
    loaded = _load_canonical_snapshot(path)
    if loaded is None:
        return False
    _snapshot_path, runtime, payload = loaded
    return validate_serialized_release_snapshot(payload, runtime)


def renew_local_qa_snapshot(path: Path) -> bool:
    """Renew a still-valid active local-QA receipt after full live revalidation."""

    loaded = _load_canonical_snapshot(path)
    if loaded is None:
        return False
    snapshot_path, runtime, payload = loaded
    original_bytes = snapshot_path.read_bytes()
    if (
        payload.get("mode") != "local-qa"
        or payload.get("local_qa_override") is not True
        or payload.get("release_ready") is not False
        or payload.get("exposure_allowed") is not True
        or payload.get("label") != "PRE-GATE / NOT READY"
        or not validate_serialized_release_snapshot(payload, runtime)
    ):
        return False
    try:
        expires_at = datetime.fromisoformat(
            str(payload["owner_binding"]["expiresAt"])
        )
    except (KeyError, TypeError, ValueError):
        return False
    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining > SNAPSHOT_RENEWAL_WINDOW_SECONDS:
        return True
    if remaining <= 0:
        return False
    projection = payload["owner_binding"]
    assert isinstance(projection, dict)
    profile = str(projection["runtimeProfile"])
    owner_state = (
        runtime.parent / "state" / "runtime" / profile / "stack-owner.json"
    )
    try:
        owner = json.loads(owner_state.read_text(encoding="utf-8"))
        installed_root = Path(str(owner["repoRoot"])).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return False
    renewed_projection = _runtime_owner_projection(installed_root, owner_state)
    if not renewed_projection:
        return False
    renewed = json.loads(json.dumps(payload))
    renewed["owner_binding"] = renewed_projection
    if (
        snapshot_path.read_bytes() != original_bytes
        or not validate_serialized_release_snapshot(payload, runtime)
        or not validate_serialized_release_snapshot(renewed, runtime)
    ):
        return False
    _write_snapshot(snapshot_path, renewed)
    return validate_snapshot_file(snapshot_path)


def _require_canonical_claim_inputs(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    supplied = {
        "readiness_facts": args.readiness_facts,
        "artifact_identity": args.artifact_identity,
        "qa_case_receipts": args.qa_case_receipts,
        "installed_prompt_bundle": args.installed_prompt_bundle,
        "installed_root": args.installed_root,
        "runtime_owner_state": args.runtime_owner_state,
        "output": args.output,
    }
    if not any(value is not None for value in supplied.values()):
        return
    expected = canonical_runtime_claim_paths(
        args.installed_root, args.runtime_owner_state
    )
    if expected is None:
        parser.error("release claim requires the exact active runtime owner")
    for name in (
        "readiness_facts",
        "artifact_identity",
        "qa_case_receipts",
        "installed_prompt_bundle",
        "installed_root",
        "runtime_owner_state",
    ):
        value = supplied[name]
        if value is None:
            parser.error(f"release claim requires canonical --{name.replace('_', '-')}")
        try:
            actual = Path(value).expanduser().resolve(
                strict=name != "qa_case_receipts"
            )
        except (OSError, RuntimeError):
            parser.error(f"release claim input is unavailable: --{name.replace('_', '-')}")
        if actual != expected[name]:
            parser.error(
                f"release claim input is not owned by the active runtime: "
                f"--{name.replace('_', '-')}"
            )
    if args.output is not None:
        try:
            actual_output = args.output.expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            parser.error("release claim output is invalid")
        if actual_output != expected["output"]:
            parser.error("release claim output is not owned by the active runtime")


def validate_runtime_owner_state_file(owner_state: Path) -> bool:
    try:
        exact_state = owner_state.expanduser().resolve(strict=True)
        payload = json.loads(exact_state.read_text(encoding="utf-8"))
        installed_root = Path(str(payload.get("repoRoot") or "")).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, json.JSONDecodeError):
        return False
    return _runtime_owner_state_proves_active(installed_root, exact_state)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--mode", choices=("default", "release", "local-qa"), default="release"
    )
    parser.add_argument("--allow-local-qa-override", action="store_true")
    parser.add_argument("--readiness-facts", type=Path)
    parser.add_argument("--artifact-identity", type=Path)
    parser.add_argument("--qa-case-receipts", type=Path)
    parser.add_argument("--installed-prompt-bundle", type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--runtime-owner-state", type=Path)
    parser.add_argument("--output", type=Path)
    snapshot_actions = parser.add_mutually_exclusive_group()
    snapshot_actions.add_argument("--validate-snapshot", type=Path)
    snapshot_actions.add_argument("--renew-local-qa-snapshot", type=Path)
    snapshot_actions.add_argument("--validate-owner-state", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if (
        args.validate_snapshot is not None
        or args.renew_local_qa_snapshot is not None
        or args.validate_owner_state is not None
    ):
        claim_values = (
            args.readiness_facts,
            args.artifact_identity,
            args.qa_case_receipts,
            args.installed_prompt_bundle,
            args.installed_root,
            args.runtime_owner_state,
            args.output,
        )
        if (
            any(value is not None for value in claim_values)
            or args.mode != "release"
            or args.allow_local_qa_override
            or args.json
        ):
            parser.error("snapshot validation and renewal accept no claim inputs")
        if args.validate_snapshot is not None:
            return 0 if validate_snapshot_file(args.validate_snapshot) else 1
        if args.renew_local_qa_snapshot is not None:
            return 0 if renew_local_qa_snapshot(args.renew_local_qa_snapshot) else 1
        assert args.validate_owner_state is not None
        return 0 if validate_runtime_owner_state_file(args.validate_owner_state) else 1
    _require_canonical_claim_inputs(parser, args)
    try:
        installed_prompt_bundle = args.installed_prompt_bundle
        if installed_prompt_bundle is None and args.artifact_identity is not None:
            installed_prompt_bundle = args.artifact_identity.parent / "prompt-bundle.json"
        result = evaluate_release_gate(
            args.root,
            mode=args.mode,
            allow_local_qa_override=args.allow_local_qa_override,
            readiness_facts=_load_readiness_facts(args.readiness_facts),
            artifact_identity=_load_artifact_identity(args.artifact_identity),
            qa_case_receipts=_load_qa_case_receipts(args.qa_case_receipts),
            installed_prompt_bundle_path=installed_prompt_bundle,
            installed_root=args.installed_root,
            runtime_owner_state=args.runtime_owner_state,
        )
    except ValueError as exc:
        parser.error(str(exc))
    payload = result.to_dict()
    if args.output is not None:
        _write_snapshot(args.output, payload)
    print(
        json.dumps(payload, indent=2, sort_keys=True)
        if args.json
        else _text_report(result)
    )
    if result.mode == "local-qa":
        return 0 if result.exposure_allowed else 1
    return 0 if result.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
