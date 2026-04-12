from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

MUST_NOT_EXIST = [
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "liveEmailIntent.js",
]

SERVICE_SCAN_ROOT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
)
TEST_SCAN_ROOTS = [
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api" / "test",
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "__tests__",
]
ALLOWLIST_COMMENT = "runtime-nlu-allowlist: deterministic identifier extraction"

REGEX_LITERAL_RE = re.compile(r"(?<![\w$])/(?![/*])((?:\\.|[^/\n])+)/([dgimsuvy]*)")
REGEXP_CONSTRUCTOR_RE = re.compile(
    r"""\b(?:new\s+)?RegExp\(\s*(['"])((?:\\.|(?!\1).)*)\1(?:\s*,\s*(['"][dgimsuvy]*['"]|[A-Za-z_$][\w$]*))?""",
    re.VERBOSE | re.DOTALL,
)
FORBIDDEN_PROVIDER_REGEX_RE = re.compile(
    r"""
    gmail
    |outlook(?:\\\.com|\.com)?
    |ms(?:\\s\?)?365
    |office(?:\\s\?)?365
    |google(?:\\s\?)?workspace
    |onedrive
    |teams
    |planner
    |onenote
    """,
    re.IGNORECASE | re.VERBOSE,
)
ALLOWLISTED_REGEX_FRAGMENTS = (
    r"docs\.google\.com",
    r"drive\.google\.com",
    r"[?&]id=",
)

FORBIDDEN_TOKENS = [
    "LIVE_EMAIL_STATUS_PATTERNS",
    "EMAIL_CAPABILITY_PATTERN",
    "FOLLOW_UP_CHECK_PATTERN",
    "EMAIL_SCOPE_PATTERN",
    "GOOGLE_EMAIL_PROVIDER_PATTERN",
    "MS365_EMAIL_PROVIDER_PATTERN",
    "PROVIDER_SELECTION_QUESTION_PATTERN",
    "PROVIDER_DISAMBIGUATION_PATTERN",
    "ASSISTANT_EMAIL_RESULT_SCOPE_PATTERN",
    "ASSISTANT_EMAIL_RESULT_SIGNAL_PATTERN",
    "PRODUCTIVITY_PROVIDER_PATTERN",
    "PRODUCTIVITY_ACTION_SCOPE_PATTERN",
    "PRODUCTIVITY_ACTION_VERB_PATTERN",
    "PRODUCTIVITY_STATUS_PATTERNS",
    "resolveDeterministicLiveEmailActivation",
    "resolveLiveEmailProviderIntent",
    "resolveClarifiedLiveEmailProviderIntent",
    "isAssistantEmailProviderClarificationQuestion",
    "isAssistantLiveEmailContextTurn",
    "findLiveEmailClarificationContext",
    "hasExplicitProductivityRequest",
    "isProviderOnlyProductivityClarification",
    "reduceMessagesForProductivitySpecialist",
]
FORBIDDEN_TEST_HELPER_RE = re.compile(
    r"""
    \bresolve[A-Za-z0-9_]*Intent\b
    |isLiveEmailStatusRequest
    |hasExplicitProductivityRequest
    |isProviderOnlyProductivityClarification
    |reduceMessagesForProductivitySpecialist
    """,
    re.VERBOSE,
)
FORBIDDEN_TEST_MESSAGE_FRAGMENTS = (
    "check my inbox",
    "did you reply",
    "did they reply",
    "ms365",
    "outlook.",
    "gmail or outlook",
)


def _iter_js_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.js") if path.is_file())


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _has_allowlist_comment(source_lines: list[str], line_number: int) -> bool:
    for index in range(line_number - 2, max(line_number - 5, -1), -1):
        line = source_lines[index].strip()
        if not line:
            continue
        return ALLOWLIST_COMMENT in line
    return False


def _iter_regex_bodies(source: str):
    for match in REGEX_LITERAL_RE.finditer(source):
        yield match.group(1), match.start(1)
    for match in REGEXP_CONSTRUCTOR_RE.finditer(source):
        yield match.group(2), match.start(2)


def test_runtime_nlu_helper_file_is_deleted() -> None:
    for path in MUST_NOT_EXIST:
        assert not path.exists(), (
            f"{path} still exists. See 01_Key_Principles.md CRITICAL RULE: "
            "No hardcoded NLU in runtime code."
        )


def test_runtime_routing_layers_do_not_reintroduce_keyword_nlu_helpers() -> None:
    for path in _iter_js_files(SERVICE_SCAN_ROOT):
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in source, (
                f"{token} reappeared in {path}. See 01_Key_Principles.md CRITICAL RULE: "
                "No hardcoded NLU in runtime code."
            )


def test_runtime_services_do_not_use_provider_brands_in_regex_nlu() -> None:
    for path in _iter_js_files(SERVICE_SCAN_ROOT):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for body, offset in _iter_regex_bodies(source):
            if not FORBIDDEN_PROVIDER_REGEX_RE.search(body):
                continue
            line_number = _line_number(source, offset)
            is_allowlisted = (
                _has_allowlist_comment(lines, line_number)
                and any(fragment in body for fragment in ALLOWLISTED_REGEX_FRAGMENTS)
            )
            assert is_allowlisted, (
                f"Provider-branded regex reappeared in {path}:{line_number}. "
                "See 01_Key_Principles.md CRITICAL RULE: No hardcoded NLU in runtime code."
            )


def test_js_tests_do_not_reintroduce_semantic_intent_helper_cases() -> None:
    for root in TEST_SCAN_ROOTS:
        for path in _iter_js_files(root):
            source = path.read_text(encoding="utf-8")
            lower_source = source.lower()
            if not FORBIDDEN_TEST_HELPER_RE.search(source):
                continue
            assert not any(fragment in lower_source for fragment in FORBIDDEN_TEST_MESSAGE_FRAGMENTS), (
                f"{path} mixes semantic provider/email fixtures with deprecated intent-helper style tests. "
                "See 01_Key_Principles.md CRITICAL RULE: No hardcoded NLU in runtime code."
            )
