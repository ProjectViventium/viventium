from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = REPO_ROOT / "qa"
QA_RESULTS = QA_ROOT / "results"
FEATURE_QA_ROOT = QA_ROOT / "glasshive_deep_research"
PUBLIC_EVIDENCE_ROOTS = [
    REPO_ROOT / "docs" / "requirements_and_learnings",
    QA_ROOT,
    REPO_ROOT / "viventium_v0_4" / "GlassHive" / "research" / "phase1",
]
PUBLIC_TEXT_SUFFIXES = {".md", ".json", ".txt", ".yaml", ".yml", ".py", ".js", ".cjs"}


def qa_public_evidence_roots() -> list[Path]:
    roots = [QA_RESULTS]
    roots.extend(path for path in sorted(QA_ROOT.glob("*/reports")) if path.is_dir())
    roots.extend(path for path in sorted(QA_ROOT.glob("*/scripts")) if path.is_dir())
    if FEATURE_QA_ROOT.is_dir():
        roots.append(FEATURE_QA_ROOT)
    roots.extend(path for path in PUBLIC_EVIDENCE_ROOTS if path.is_dir())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in roots:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return deduped


def public_evidence_files() -> list[Path]:
    files: set[Path] = set()
    for root in PUBLIC_EVIDENCE_ROOTS:
        if root.is_dir():
            files.update(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def is_git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


PRIVATE_PATTERNS = {
    "local_home_path": re.compile(r"/Users/(?!example(?:/|\b))[^/\s\"']+"),  # synthetic fixture path is exempt
    "personal_email": re.compile(
        r"\b(?!git@github\.com\b)[A-Za-z0-9._%+-]+@"
        r"(?!example\.com\b|viventium\.local\b|localhost\b|"
        r"[A-Za-z0-9.-]+\.(?:test|invalid|example)\b)"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    ),
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9._=-]{8,}"),
    "provider_request_id": re.compile(r"\breq_[A-Za-z0-9_-]{8,}"),
    "bearer_token": re.compile(
        r"\bBearer\s+(?!synthetic[-_])(?=[A-Za-z0-9._~+/=-]{12,}(?:\s|[\"'`]|$))"
        r"(?=[A-Za-z0-9._~+/=-]*[0-9._~+=-])[A-Za-z0-9._~+/=-]{12,}",
        re.IGNORECASE,
    ),
    "glasshive_signed_query": re.compile(r"\bgh_(?:token|sig|exp|kind)\s*=", re.IGNORECASE),
    "glasshive_runtime_id": re.compile(r"\b(?:prj|wrk|run)_[0-9A-Fa-f]{8,}\b"),
    "relationship_identity_tier": re.compile(
        r"\b(?:spouse-owned|wife-owned|husband-owned|spouse's personal|wife's personal|husband's personal)\b",  # synthetic detector vocabulary
        re.IGNORECASE,
    ),
}

CANONICAL_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
MONGO_OBJECT_ID = r"[0-9a-f]{24}"
CONTEXTUAL_PRIVATE_PATTERNS = {
    "codex_thread_uri": re.compile(rf"\bcodex://threads/(?P<identifier>{CANONICAL_UUID})\b", re.IGNORECASE),
    "conversation_url": re.compile(
        rf"(?:https?://[^\s)\"']+)?/c/(?P<identifier>{CANONICAL_UUID})\b",
        re.IGNORECASE,
    ),
    "labeled_uuid": re.compile(
        rf"\b(?:account|user|conversation|message|parent[_ -]?message|session|"
        rf"call(?:[_ -]?session)?|telegram[_ -]?chat|chat)[_ -]?id\b"
        rf"[\"'` ]{{0,3}}[:=][\"'` ]{{0,3}}(?P<identifier>{CANONICAL_UUID})\b",
        re.IGNORECASE,
    ),
    "raw_result_uuid": re.compile(
        rf"[\"'](?:session_id|uuid)[\"']\s*:\s*[\"'](?P<identifier>{CANONICAL_UUID})[\"']",
        re.IGNORECASE,
    ),
    "labeled_mongo_object_id": re.compile(
        rf"(?:[\"'`]?\b(?:_id|mongo[_ -]?id|account[_ -]?id|user[_ -]?id|conversation[_ -]?id|"
        rf"message[_ -]?id|session[_ -]?id|call[_ -]?id)\b[\"'`]?)\s*[:=]\s*"
        rf"[\"'`]?(?P<identifier>{MONGO_OBJECT_ID})\b",
        re.IGNORECASE,
    ),
    "telegram_numeric_chat_id": re.compile(
        r"\b(?:telegram[_ -]?(?:chat[_ -]?)?id|chat[_ -]?id)\b"
        r"[\"'` ]{0,3}[:=][\"'` ]{0,3}(?P<identifier>-?[0-9]{6,15})\b",
        re.IGNORECASE,
    ),
}
SYNTHETIC_MARKER = re.compile(
    r"\b(?:synthetic|fixture|placeholder|example|dummy|test(?:[-_ ]|$)|test-only|test value)",
    re.IGNORECASE,
)
SYNTHETIC_IDENTIFIER_SHA256 = {
    "0a35c47b4f43f44da14961b8101d359b3a4c4634cea51375f2b10c526440f925",
    "4e6c228e4e31457f075a681800f1382f68c99dd7ce324874398582c5933cb1d3",
    "88f40997ce5eca338ac3c7615652e0acfd5705ec38d7389d8ff59c3844cd8f85",
    "8d284ad45c0587dafda49a685cf276590a7228daba764440d94735c5e529ad80",
    "937377f056160fc4b15e0b770c67136a5f03c15205b4d3bf918268fefa2c6d0a",
    "9dd556981308657239a9b68701b1d5ef540fb154a9972b216b82a7d73f63963e",
    "d4c81d964dc5457b065dac9c046026f4d3c769c6e7c2d6df7c8ba4f291e0fbfd",
    "e7b3da72ace542d6a3c8cc1ca26c1dbc6fc98ec4980964cebddaa253b49f515a",
    "ef2d5f2cc8ee275cec18e3dbddce4f63bb139b2a4b4212a28e16c67ab706026f",
    "f3e79949d9dcbf3947f184e1b388ab88d5e7b6af0bd0bf7e1ca34238d520a463",
    "a419b139ba3943fd33591cf0ddaf45adcb030231ac577e683d459ab17156bb30",
    "bc8203a21ab8b782157c2b1cda5125af12cbb635638586b3b5fc67b2bb688863",
}


def is_explicitly_synthetic_identifier(line: str, identifier: str) -> bool:
    if SYNTHETIC_MARKER.search(line):
        return True
    if hashlib.sha256(identifier.encode("utf-8")).hexdigest() in SYNTHETIC_IDENTIFIER_SHA256:
        return True
    compact = identifier.lower().replace("-", "")
    return bool(compact) and len(set(compact)) <= 2


def iter_public_evidence_files() -> list[Path]:
    files: set[Path] = set()
    for root in qa_public_evidence_roots():
        if not root.exists():
            continue
        files.update(path for path in root.rglob("*") if path.is_file())
    files.update(public_evidence_files())
    authored = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8", errors="surrogateescape")
    for relative in authored.split("\0"):
        if not relative:
            continue
        path = REPO_ROOT / relative
        if path.is_file() and not {".pytest-cache", ".pytest_cache", "node_modules"} & set(path.parts):
            files.add(path)
    return sorted(files)


def test_public_requirements_and_qa_contracts_are_in_scan_scope() -> None:
    scanned = {path.resolve() for path in iter_public_evidence_files()}
    assert (REPO_ROOT / "docs/requirements_and_learnings/01_Key_Principles.md").resolve() in scanned
    assert (REPO_ROOT / "docs/requirements_and_learnings/requirement_source_coverage.yaml").resolve() in scanned
    assert (QA_ROOT / "README.md").resolve() in scanned
    assert (QA_ROOT / "main-continuity/contract.v1.json").resolve() in scanned
    assert Path(__file__).resolve() in scanned
    assert (REPO_ROOT / "scripts/viventium/native_payload.py").resolve() in scanned


def test_contextual_private_identifier_patterns_detect_runtime_values() -> None:
    synthetic_uuid_v7 = "00000000-0000-7000-8000-000000000000"
    examples = {
        "codex_thread_uri": f"codex://threads/{synthetic_uuid_v7}",
        "conversation_url": f"https://example.invalid/c/{synthetic_uuid_v7}",
        "labeled_uuid": f"conversation_id: {synthetic_uuid_v7}",
        "raw_result_uuid": f'"session_id": "{synthetic_uuid_v7}"',
        "labeled_mongo_object_id": "synthetic message_id: 65d12345abcdef6789012345",
        "telegram_numeric_chat_id": "synthetic telegram_chat_id: -123456789",
    }
    for label, value in examples.items():
        assert CONTEXTUAL_PRIVATE_PATTERNS[label].search(value), label

    assert is_explicitly_synthetic_identifier("synthetic conversation_id: 00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000")
    assert not PRIVATE_PATTERNS["personal_email"].search("git@github.com")
    assert not PRIVATE_PATTERNS["bearer_token"].search("bearer credentials")


def test_tracked_qa_results_do_not_contain_private_runtime_identifiers() -> None:
    offenders: list[str] = []
    for path in iter_public_evidence_files():
        if is_git_ignored(path):
            continue
        if path.suffix.lower() not in PUBLIC_TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PRIVATE_PATTERNS.items():
                for match in pattern.finditer(line):
                    if not SYNTHETIC_MARKER.search(line) and "never-expose" not in line:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{label}")
            for label, pattern in CONTEXTUAL_PRIVATE_PATTERNS.items():
                for match in pattern.finditer(line):
                    identifier = match.group("identifier")
                    if not is_explicitly_synthetic_identifier(line, identifier):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{label}")

    assert sorted(set(offenders)) == []
