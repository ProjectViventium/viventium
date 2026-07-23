from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = ROOT / "qa"
RELEASE_TEST_ROOT = ROOT / "tests" / "release"
FEATURE_USE_CASE_CHECKLIST = QA_ROOT / "feature-user-use-case-checklist.md"

NON_FEATURE_QA_DIRS = {"_templates", "results"}
AGENT_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
]
GLASSHIVE_MCP_SERVER = (
    ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "runtime_phase1"
    / "src"
    / "workers_projects_runtime"
    / "mcp_server.py"
)

REQUIRED_LOOP_PHRASE = (
    "supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or "
    "wording step"
)

PUBLIC_SAFE_TERMS = [
    "account identifiers",
    "conversation IDs",
    "message IDs",
    "session/call IDs",
    "Telegram chat IDs",
    "Mongo `_id` values",
    "stack traces with private paths",
    "raw runtime dumps",
]
REPORT_REQUIRED_HEADINGS = [
    "## Summary",
    "## Scope Run",
    "## User-Grade Evidence",
    "## Automated Evidence",
    "## Findings",
    "## Public-Safety Review",
]
REPORT_V2_REQUIRED_HEADINGS = [
    "## Summary",
    "## Scope Run",
    "## Traceability",
    "## Full-View Evidence Checklist",
    "## User-Grade Evidence",
    "## Automated Evidence",
    "## Findings",
    "## Public-Safety Review",
]
REPORT_V2_CUTOFF = date(2026, 5, 18)
REPORT_EVIDENCE_EXEMPTION_RE = re.compile(r"<!--\s*qa-evidence-exempt:\s*.{20,}-->", re.DOTALL)
REPORT_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
REPORT_PLACEHOLDER_RE = re.compile(
    r"<(?:[^>\n]+)>|YYYY-MM-DD|TODO|TBD|`<[^`\n]+>`|<commands run>",
    re.IGNORECASE,
)
FULL_VIEW_EVIDENCE_TERMS = [
    "feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap",
    "real user path",
    "docs and nested docs",
    "logs, DB/state/persistence",
    "BLOCKED",
    "cannot replace required user-path evidence",
]
NATURAL_USE_CASE_HEADING = "## Natural User Use Case Checklist"
GENERIC_USE_CASE_PLACEHOLDER_PHRASES = [
    "Run the primary happy path a user naturally expects from this feature",
    "Run the missing auth/config, first-run/empty-state, or degraded dependency path",
    "Run persistence, reload/restart, retry/cancel/update, or cross-surface parity where applicable",
    "Real product surface for this feature",
    "owning case above",
    "Visible result and supporting evidence agree",
]
GENERIC_USE_CASE_PLACEHOLDER_PATTERNS = [
    re.compile(r"Execute `[A-Z0-9]+-\d+` \([^)]*\) through the documented primary user surface"),
    re.compile(r"Exercise `[A-Z0-9]+-\d+` \([^)]*\) with its missing setup"),
    re.compile(r"Re-run `[A-Z0-9]+-\d+` \([^)]*\) across reload, restart, retry/cancel/update"),
]
FEATURE_INVENTORY_TERMS = [
    "complete feature inventory",
    "natural user use cases",
    "happy path",
    "first-run/empty state",
    "missing auth/config",
    "degraded dependency",
    "retry/recovery",
    "persistence/reload/restart",
    "cross-surface parity",
    "generated/shipped artifact verification",
    "public/private safety",
]
REAL_USER_SURFACE_TERMS = [
    "Playwright",
    "browser",
    "computer",
    "helper",
    "Telegram",
    "voice",
    "installer",
    "CLI",
    "MCP",
    "scheduler",
    "GlassHive",
]
USER_GRADE_REQUIRED_FIELDS = [
    "Surface exercised",
    "Real user path",
    "Visible outcome",
    "Expanded/detail state",
    "Persistence/reload result",
    "Backend/log/DB confirmation",
    "Final model/runtime wording check",
]
STRICT_RELEASE_VERDICT_PATHS = sorted(
    {
        *[path for path in (QA_ROOT / "release-readiness").rglob("*.md") if path.is_file()],
        *[path for path in (QA_ROOT / "installer-resilience").rglob("*.md") if path.is_file()],
        *[path for path in (QA_ROOT / "channel-connections").rglob("*.md") if path.is_file()],
        QA_ROOT / "agent-config-continuity" / "cases.md",
    }
)
VERDICT_WORD_RE = re.compile(r"\b(?:PASS|FAIL|PARTIAL|BLOCKED)\b", re.IGNORECASE)
ADDITIONAL_VERDICT_RE = re.compile(r"\b(?:PASS|FAIL|PARTIAL|BLOCKED)\b")
VERDICT_PREFIX_RE = re.compile(r"^(PASS|FAIL|PARTIAL|BLOCKED)(?=$|[\s:;,.—])")
SUMMARY_VERDICT_RE = re.compile(
    r"^(?:[-*+]\s+)?(?:\*\*|__)?"
    r"(?P<label>(?:(?:overall|release|final|qa|publication|review|hosted|current)\s+){0,2}"
    r"(?:status|result|verdict)|last\s+run|current\s+(?:status|state))"
    r"(?::(?:\*\*|__)?|(?:\*\*|__):)\s*(?P<value>.+)$",
    re.IGNORECASE,
)
VERDICT_HEADER_RE = re.compile(
    r"^(?:(?:actual|current|overall|release|final|qa|publication|review|hosted)\s+)?"
    r"(?:status|result|verdict)\b|^last\s+run\b|^current\s+state\b",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_verdict_markdown(value: str) -> str:
    return value.replace("`", "").replace("**", "").replace("__", "").strip()


def _verdict_value_violation(value: str) -> str | None:
    normalized = _strip_verdict_markdown(value)
    verdict = VERDICT_PREFIX_RE.match(normalized)
    if not verdict:
        found = VERDICT_WORD_RE.search(normalized)
        if found:
            return f"verdict token must be exact uppercase at the start: {found.group(0)!r}"
        return f"verdict field has no standard enum: {normalized!r}"

    remainder = normalized[verdict.end() :].lstrip()
    if remainder.startswith(("/", "\\", "(", "[", "+", "&", "-")):
        return f"verdict must not encode a slash, parenthetical, or composite qualifier: {normalized!r}"
    if ADDITIONAL_VERDICT_RE.search(remainder):
        return f"verdict must not combine multiple enum values: {normalized!r}"
    return None


def _normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", _read(path))


def _feature_dirs() -> list[Path]:
    return sorted(
        path
        for path in QA_ROOT.iterdir()
        if path.is_dir() and path.name not in NON_FEATURE_QA_DIRS
    )


def _migration_features() -> set[str]:
    text = _read(QA_ROOT / "_migration.md")
    features: set[str] = set()
    for match in re.finditer(r"^\|\s+`([^`]+)`\s+\|", text, flags=re.MULTILINE):
        if match.group(1) != "Feature":
            features.add(match.group(1))
    return features


def _migration_rows() -> list[tuple[str, str]]:
    text = _read(QA_ROOT / "_migration.md")
    rows: list[tuple[str, str]] = []
    for match in re.finditer(r"^\|\s+`([^`]+)`\s+\|\s+([^|]+)\|", text, flags=re.MULTILINE):
        feature = match.group(1)
        gap = match.group(2).strip()
        if feature != "Feature":
            rows.append((feature, gap))
    return rows


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _release_test_files() -> list[str]:
    return [_relative(path) for path in sorted(RELEASE_TEST_ROOT.glob("test_*.py"))]


def _load_release_test_owners() -> dict[str, dict[str, str]]:
    mapping_path = QA_ROOT / "release-test-owners.yaml"
    payload = yaml.safe_load(_read(mapping_path))
    assert isinstance(payload, dict), f"Expected YAML mapping in {mapping_path}"
    release_tests = payload.get("release_tests")
    assert isinstance(release_tests, dict), f"Expected release_tests mapping in {mapping_path}"
    return release_tests


def _is_git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", _relative(path)],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def _is_git_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", _relative(path)],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _git_tracked_paths_under(path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", _relative(path)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _markdown_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    next_heading = re.search(r"^##\s+", text[start + len(heading) :], flags=re.MULTILINE)
    if not next_heading:
        return text[start:]
    return text[start : start + len(heading) + next_heading.start()]


def _field_value(section: str, field_name: str) -> str | None:
    match = re.search(rf"^-\s+{re.escape(field_name)}:[ \t]*(.*)$", section, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _report_template_violations(report_path: Path, text: str) -> list[str]:
    violations: list[str] = []
    required_headings = REPORT_REQUIRED_HEADINGS
    report_date = _report_date(report_path)
    if report_date is not None and report_date >= REPORT_V2_CUTOFF:
        required_headings = REPORT_V2_REQUIRED_HEADINGS
    missing = [heading for heading in required_headings if heading not in text]
    if missing:
        violations.append(f"{_relative(report_path)} missing {', '.join(missing)}")
    if "Substitution check:" not in text:
        violations.append(f"{_relative(report_path)} missing Substitution check")
    if report_date is None or report_date < REPORT_V2_CUTOFF:
        return violations

    if REPORT_PLACEHOLDER_RE.search(text):
        violations.append(f"{_relative(report_path)} still contains template placeholders")

    user_grade_section = _markdown_section(text, "## User-Grade Evidence")
    for field_name in USER_GRADE_REQUIRED_FIELDS:
        field_value = _field_value(user_grade_section, field_name)
        if not field_value or REPORT_PLACEHOLDER_RE.search(field_value):
            violations.append(f"{_relative(report_path)} has empty/placeholder {field_name}")

    user_grade_lower = user_grade_section.lower()
    if not any(term.lower() in user_grade_lower for term in REAL_USER_SURFACE_TERMS):
        violations.append(f"{_relative(report_path)} does not name a real user-path surface")

    public_safety_section = _markdown_section(text, "## Public-Safety Review")
    if "- [ ]" in public_safety_section:
        violations.append(f"{_relative(report_path)} has unchecked public-safety review items")
    return violations


def _backticked_contract_paths(markdown_path: Path) -> list[str]:
    text = _read(markdown_path)
    return [
        match.group(1)
        for match in re.finditer(r"`((?:qa|docs/requirements_and_learnings)/[^`]+)`", text)
        if "<" not in match.group(1) and ">" not in match.group(1)
    ]


def _hard_coded_qa_paths(source_path: Path) -> set[str]:
    text = _read(source_path)
    paths: set[str] = set()
    for match in re.finditer(r"(?<![A-Za-z0-9_./-])(?:\./)?(qa/[A-Za-z0-9_./-]+)", text):
        raw = match.group(1).rstrip(".,;:)'\"`]")
        if "<" not in raw and ">" not in raw:
            paths.add(raw)
    return paths


def _contract_reference_exists(reference: str) -> bool:
    if "*" in reference:
        return any(ROOT.glob(reference))
    return (ROOT / reference).exists()


def _report_date(path: Path) -> date | None:
    match = REPORT_DATE_RE.search(path.name)
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def test_qa_contract_files_and_templates_exist() -> None:
    required_paths = [
        QA_ROOT / "README.md",
        QA_ROOT / "_migration.md",
        QA_ROOT / "_templates" / "README.md",
        QA_ROOT / "_templates" / "feature-readme.md",
        QA_ROOT / "_templates" / "cases.md",
        QA_ROOT / "_templates" / "run-report.md",
        QA_ROOT / "results" / "README.md",
        QA_ROOT / "release-test-owners.yaml",
        FEATURE_USE_CASE_CHECKLIST,
    ]
    for path in required_paths:
        assert path.exists(), f"Missing QA operating-contract file: {path}"
        assert not _is_git_ignored(path), f"Required QA operating-contract file is ignored by git: {path}"
        assert _is_git_tracked(path), f"Required QA operating-contract file is not tracked: {path}"

    assert _is_git_ignored(QA_ROOT / "results" / "example-suite" / "2026-05-17" / "raw.json")


def test_user_grade_qa_loop_disallows_backend_only_substitution() -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
    ]
    for path in paths:
        assert REQUIRED_LOOP_PHRASE in _normalized(path), f"Missing substitution guard in {path}"

    qa_readme = _read(QA_ROOT / "README.md")
    assert "Playwright CLI or an equivalent real-browser harness" in qa_readme
    assert "Skipping the visible browser step is not acceptable" in qa_readme


def test_full_view_evidence_gate_is_explicit_in_agent_and_qa_docs() -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
    ]
    for path in paths:
        text = _normalized(path)
        for term in FULL_VIEW_EVIDENCE_TERMS:
            assert term in text, f"Missing full-view evidence gate term {term!r} in {path}"

    template_text = _read(QA_ROOT / "_templates" / "run-report.md")
    for required_surface in [
        "Code owning path",
        "Docs and nested docs/repos",
        "Scripts or harnesses",
        "Logs",
        "DB/state/persistence",
        "Generated/shipped artifact",
        "Real user path",
        "Visual/UX comparison",
        "Not run / blocked",
    ]:
        assert required_surface in template_text


def test_feature_inventory_and_natural_use_case_gate_is_explicit() -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "cases.md",
        QA_ROOT / "_templates" / "feature-readme.md",
        QA_ROOT / "_templates" / "run-report.md",
        FEATURE_USE_CASE_CHECKLIST,
    ]
    for path in paths:
        text = _normalized(path).lower()
        assert "natural user" in text, f"Missing natural-user QA gate in {path}"
        assert "checklist" in text or "feature inventory" in text, (
            f"Missing checklist/feature-inventory QA gate in {path}"
        )

    combined_text = " ".join(_normalized(path) for path in paths)
    for term in FEATURE_INVENTORY_TERMS:
        assert term in combined_text, f"Missing feature/use-case QA term {term!r} across QA docs"

    checklist_text = _read(FEATURE_USE_CASE_CHECKLIST)
    assert NATURAL_USE_CASE_HEADING in checklist_text
    for phrase in [
        "voice + web-search",
        "Web Search capability",
        "SearXNG/Firecrawl",
        "persisted message/tool-call state",
        "generic \"search is not pulling\"",
    ]:
        assert phrase in checklist_text


def test_feature_use_case_checklist_mentions_all_requirement_docs_and_qa_owners() -> None:
    checklist_text = _read(FEATURE_USE_CASE_CHECKLIST)
    requirement_docs = {
        path.name
        for path in (ROOT / "docs" / "requirements_and_learnings").glob("*.md")
        if path.name != "45_Runtime_Feature_QA_Map.md"
    }
    missing_docs = sorted(doc_name for doc_name in requirement_docs if doc_name not in checklist_text)
    assert not missing_docs, (
        "Product-wide feature user-use-case checklist must mention every requirement doc:\n"
        + "\n".join(missing_docs)
    )

    missing_owners: list[str] = []
    for feature_dir in _feature_dirs():
        owner_ref = f"qa/{feature_dir.name}/"
        if owner_ref not in checklist_text:
            missing_owners.append(owner_ref)
    assert not missing_owners, (
        "Product-wide feature user-use-case checklist must mention every QA owner:\n"
        + "\n".join(missing_owners)
    )


def test_feature_case_catalogs_have_natural_user_use_case_checklists() -> None:
    missing: list[str] = []
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        text = _read(cases_path)
        if NATURAL_USE_CASE_HEADING not in text:
            missing.append(_relative(cases_path))
            continue
        section = _markdown_section(text, NATURAL_USE_CASE_HEADING)
        for required in [
            "Natural user action",
            "Real surface",
            "Supporting evidence",
            "Expected visible result",
            "Last run",
        ]:
            if required not in section:
                missing.append(f"{_relative(cases_path)} missing {required}")

    assert not missing, "Feature case catalogs must carry natural user use-case checklists:\n" + "\n".join(
        missing
    )


def test_natural_user_use_case_checklists_reject_generic_placeholder_rows() -> None:
    violations: list[str] = []
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        if cases_path.parent.name == "_templates":
            continue
        section = _markdown_section(_read(cases_path), NATURAL_USE_CASE_HEADING)
        for phrase in GENERIC_USE_CASE_PLACEHOLDER_PHRASES:
            if phrase in section:
                violations.append(f"{_relative(cases_path)} contains generic placeholder phrase: {phrase}")
        for pattern in GENERIC_USE_CASE_PLACEHOLDER_PATTERNS:
            if pattern.search(section):
                violations.append(
                    f"{_relative(cases_path)} contains generic placeholder pattern: {pattern.pattern}"
                )

    assert not violations, (
        "Natural user use-case checklists must name feature-specific user actions, not template rows:\n"
        + "\n".join(violations)
    )


def test_cataloged_not_yet_run_cases_do_not_stagnate_silently() -> None:
    today = date.today()
    max_age_days = 90
    violations: list[str] = []
    pattern = re.compile(r"NOT YET RUN \(cataloged (\d{4})-(\d{2})-(\d{2})")
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        for line_number, line in enumerate(_read(cases_path).splitlines(), start=1):
            match = pattern.search(line)
            if not match:
                continue
            cataloged = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if (today - cataloged).days > max_age_days:
                violations.append(f"{_relative(cases_path)}:{line_number}: {line.strip()}")

    assert not violations, (
        "Cataloged but unrun QA cases older than 90 days must be run, re-triaged, or moved to "
        "qa/_migration.md:\n" + "\n".join(violations)
    )


def test_release_facing_verdict_fields_use_standard_enum() -> None:
    violations: list[str] = []

    for path in STRICT_RELEASE_VERDICT_PATHS:
        text = _read(path)
        for line_number, line in enumerate(text.splitlines(), start=1):
            summary_verdict = SUMMARY_VERDICT_RE.search(line.strip())
            if summary_verdict:
                violation = _verdict_value_violation(summary_verdict.group("value"))
            else:
                violation = None
            if violation:
                violations.append(
                    f"{_relative(path)}:{line_number}: summary {violation}"
                )

        lines = text.splitlines()
        table_status_columns: list[int] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.startswith("|"):
                table_status_columns = []
                continue

            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            is_separator = all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)
            if is_separator:
                continue

            next_is_separator = False
            if line_number < len(lines) and lines[line_number].startswith("|"):
                next_cells = [
                    cell.strip() for cell in lines[line_number].strip().strip("|").split("|")
                ]
                next_is_separator = bool(next_cells) and all(
                    re.fullmatch(r":?-{3,}:?", cell) for cell in next_cells
                )

            if next_is_separator:
                table_status_columns = [
                    index
                    for index, cell in enumerate(cells)
                    if VERDICT_HEADER_RE.search(_strip_verdict_markdown(cell))
                ]
                continue

            for index in table_status_columns:
                if index >= len(cells):
                    continue
                value = cells[index]
                violation = _verdict_value_violation(value)
                if violation:
                    violations.append(
                        f"{_relative(path)}:{line_number}: {violation}"
                    )

    assert not violations, (
        "Release-facing verdict fields must use PASS, FAIL, PARTIAL, or BLOCKED; put scope and "
        "evidence qualifiers in the surrounding text:\n" + "\n".join(violations)
    )


def test_release_verdict_parser_rejects_qualified_or_noncanonical_tokens() -> None:
    for value in [
        "pass",
        "Partial 2026-07-22",
        "PASS/PARTIAL",
        "FAIL / NOT STARTED",
        "PASS (supporting only)",
        "PASS-ONLY",
        "PARTIAL + BLOCKED",
        "PARTIAL; source checks PASS but the user path remains open",
    ]:
        assert _verdict_value_violation(value), value

    for value in [
        "PASS",
        "FAIL. The attempted path did not complete.",
        "PARTIAL 2026-07-22; the remaining user path is documented.",
        "BLOCKED; signing authority is unavailable.",
    ]:
        assert _verdict_value_violation(value) is None, value

    for header in [
        "Status",
        "Result / sanitized pointer",
        "Actual result",
        "Verdict",
        "Last Run",
        "Current state",
    ]:
        assert VERDICT_HEADER_RE.search(header), header
    for non_verdict_header in ["Expected result", "Visible result", "Resulting origin ref"]:
        assert not VERDICT_HEADER_RE.search(non_verdict_header), non_verdict_header

    for summary in [
        "Status: PASS",
        "- **Review verdict:** PARTIAL",
        "Overall release status: BLOCKED",
        "Hosted review result: PASS",
        "Last run: BLOCKED 2026-07-22",
    ]:
        assert SUMMARY_VERDICT_RE.search(summary), summary
    for non_verdict_summary in [
        "Expected result: a visible answer",
        "Test result: 12 passed",
        "Visible result: the setup screen opens",
    ]:
        assert not SUMMARY_VERDICT_RE.search(non_verdict_summary), non_verdict_summary


def test_current_agent_continuity_reports_use_standard_summary_verdicts() -> None:
    report_root = QA_ROOT / "agent-config-continuity" / "reports"
    paths = sorted(report_root.glob("2026-07-22-*.md"))
    assert paths, "Expected dated agent-continuity release reports"

    violations: list[str] = []
    for path in paths:
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            summary_verdict = SUMMARY_VERDICT_RE.search(line.strip())
            if not summary_verdict:
                continue
            violation = _verdict_value_violation(summary_verdict.group("value"))
            if violation:
                violations.append(f"{_relative(path)}:{line_number}: {violation}")

    assert not violations, (
        "Current agent-continuity report summaries must use a standard verdict enum:\n"
        + "\n".join(violations)
    )


def test_voice_web_search_escaped_case_is_promoted_to_feature_cases() -> None:
    owners = [
        "web-search",
        "modern-playground-voice",
        "web-search-telegram",
        "agent-config-continuity",
        "config-alignment",
        "citation-rendering",
    ]
    for owner in owners:
        text = _read(QA_ROOT / owner / "cases.md")
        for phrase in [
            "Web Search",
            "look something up",
            "SearXNG/Firecrawl",
            "web_search",
            "persisted",
            (
                "FAIL; escaped 2026-05-18"
                if owner == "agent-config-continuity"
                else "FAIL (escaped 2026-05-18"
            ),
        ]:
            assert phrase in text, f"Missing escaped voice/web-search case phrase {phrase!r} in {owner}"


def test_evidence_retrieval_failures_have_classification_prereq_and_fallback_contract() -> None:
    core_paths = [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        ROOT / "docs" / "requirements_and_learnings" / "10_Open_Source_Web_Search.md",
        QA_ROOT / "README.md",
        QA_ROOT / "web-search" / "README.md",
        QA_ROOT / "web-search" / "cases.md",
    ]
    for path in core_paths:
        text = _normalized(path)
        for term in [
            "provider unavailable",
            "timeout",
            "rate limit",
            "auth/config missing",
            "request rejected",
            "Docker",
        ]:
            assert term in text, f"Missing evidence-retrieval QA term {term!r} in {path}"

    combined_paths = core_paths + [
        ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md",
        QA_ROOT / "_templates" / "cases.md",
        QA_ROOT / "_templates" / "feature-readme.md",
        QA_ROOT / "_templates" / "run-report.md",
        QA_ROOT / "feature-user-use-case-checklist.md",
        QA_ROOT / "modern-playground-voice" / "cases.md",
    ]
    combined_text = " ".join(_normalized(path) for path in combined_paths)
    for term in [
        "provider unavailable",
        "timeout",
        "rate limit",
        "auth/config missing",
        "request rejected",
        "successful-empty",
        "local prerequisite",
        "Docker",
        "browser/computer/local-delegation fallback",
    ]:
        assert term in combined_text, f"Missing evidence-retrieval QA term {term!r} across QA docs"

    cases_text = _read(QA_ROOT / "web-search" / "cases.md")
    assert "WEB-005" in cases_text
    assert "WEB-UC-004" in cases_text
    assert "search is not pulling" in cases_text


def test_glasshive_delegation_contract_avoids_canned_status_and_exposes_audit() -> None:
    source = _read(GLASSHIVE_MCP_SERVER)
    qa_cases = _read(QA_ROOT / "glasshive_host_workers" / "cases.md")
    docs = _read(ROOT / "docs" / "requirements_and_learnings" / "48_GlassHive_Workstation_Sandbox_Runtime.md")

    for term in [
        "acknowledgement_guidance",
        "delegation_audit",
        "own voice",
        "canned template",
        "submitted_instruction",
    ]:
        assert term in source, f"Missing GlassHive delegation runtime contract term {term!r}"

    assert '"user_status"' not in source
    assert "submitted instruction is diagnostics-only" in docs
    assert "GHHOST-003" in qa_cases
    assert "GHHOST-UC-004" in qa_cases
    assert "forced canned phrase" in qa_cases


def test_public_safe_qa_evidence_terms_stay_in_sync() -> None:
    paths = [
        QA_ROOT / "README.md",
        QA_ROOT / "results" / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
    ]
    for path in paths:
        text = _normalized(path)
        for term in PUBLIC_SAFE_TERMS:
            assert term in text, f"Missing public-safety term {term!r} in {path}"


def test_legacy_qa_folder_gaps_are_tracked() -> None:
    migration_features = _migration_features()
    assert migration_features, "Expected qa/_migration.md to list legacy QA folders"

    missing_readme_or_cases = {
        path.name
        for path in _feature_dirs()
        if not (path / "README.md").exists() or not (path / "cases.md").exists()
    }
    assert missing_readme_or_cases <= migration_features


def test_standard_feature_qa_folders_have_case_catalogs_and_report_home() -> None:
    missing: list[str] = []
    for path in _feature_dirs():
        for required_name in ("README.md", "cases.md", "reports"):
            required_path = path / required_name
            if not required_path.exists():
                missing.append(f"{_relative(path)} missing {required_name}")
            elif required_name != "reports" and not _is_git_tracked(required_path):
                missing.append(f"{_relative(required_path)} is not tracked")
        reports_path = path / "reports"
        if reports_path.exists() and not _git_tracked_paths_under(reports_path):
            missing.append(f"{_relative(path)} reports/ has no tracked placeholder or report")

    assert not missing, "Standard QA feature folders need README.md, cases.md, and reports/:\n" + "\n".join(
        missing
    )


def test_dated_qa_reports_use_evidence_template_or_explicit_exemption() -> None:
    violations: list[str] = []
    for report_path in sorted(QA_ROOT.glob("*/reports/*.md")):
        if report_path.name == "README.md":
            continue
        if _is_git_ignored(report_path):
            continue
        text = _read(report_path)
        if REPORT_EVIDENCE_EXEMPTION_RE.search(text):
            continue
        violations.extend(_report_template_violations(report_path, text))

    assert not violations, (
        "Dated QA reports must follow the evidence template or carry an explicit "
        "`qa-evidence-exempt` marker:\n" + "\n".join(violations)
    )


def test_v2_report_gate_rejects_synthetic_handwaved_report() -> None:
    bad_report = """
# Bad QA Run - 2026-05-18

## Summary

- Result: pass

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `<FEATURE>-001` | `<pass/fail/blocked>` | `<sanitized link/count/hash>` | `<notes>` |

## Traceability

- Feature:
- Requirement:
- Use case:
- QA case:
- Expected result:
- Actual evidence:
- Remaining gap or fix:

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Real user path | Which path was used? | |

## User-Grade Evidence

- Surface exercised:
- Real user path: unit test only
- Visible outcome:
- Expanded/detail state:
- Persistence/reload result:
- Backend/log/DB confirmation:
- Final model/runtime wording check:
- Substitution check: logs are enough

## Automated Evidence

```bash
<commands run>
```

## Findings

- Defects:

## Public-Safety Review

- [ ] No secrets.
""".strip()
    violations = _report_template_violations(
        ROOT / "qa" / "synthetic" / "reports" / "2026-05-18-bad-report.md",
        bad_report,
    )

    assert any("template placeholders" in violation for violation in violations)
    assert any("empty/placeholder Surface exercised" in violation for violation in violations)
    assert any("does not name a real user-path surface" in violation for violation in violations)
    assert any("unchecked public-safety review items" in violation for violation in violations)


def test_requirement_docs_have_runtime_feature_qa_map_rows() -> None:
    matrix_text = _read(ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md")
    requirement_docs = {
        path.name
        for path in (ROOT / "docs" / "requirements_and_learnings").glob("*.md")
        if path.name != "45_Runtime_Feature_QA_Map.md"
    }
    mapped_docs = set(re.findall(r"\[`([^`]+\.md)`\]\(\1\)", matrix_text))
    missing = sorted(requirement_docs - mapped_docs)

    assert not missing, "Requirement docs missing from 45_Runtime_Feature_QA_Map.md:\n" + "\n".join(
        missing
    )


def test_agent_instruction_backticked_qa_and_requirement_paths_resolve() -> None:
    missing: list[str] = []
    for doc_path in AGENT_DOCS:
        for reference in _backticked_contract_paths(doc_path):
            if not _contract_reference_exists(reference):
                missing.append(f"{_relative(doc_path)} -> {reference}")

    assert not missing, "Backticked agent-instruction paths must resolve:\n" + "\n".join(missing)


def test_release_tests_have_central_qa_ownership() -> None:
    release_tests = set(_release_test_files())
    owner_map = _load_release_test_owners()

    assert set(owner_map) == release_tests

    for test_path, entry in owner_map.items():
        assert isinstance(entry, dict), f"{test_path} owner entry must be a mapping"
        qa_owner = entry.get("qa_owner")
        exemption = entry.get("exemption")
        assert bool(qa_owner) != bool(exemption), f"{test_path} needs exactly one qa_owner or exemption"

        if qa_owner:
            owner_path = ROOT / qa_owner
            assert owner_path.exists(), f"{test_path} qa_owner does not exist: {qa_owner}"
            assert qa_owner.startswith("qa/"), f"{test_path} qa_owner must stay under qa/: {qa_owner}"
            assert qa_owner.endswith("/cases.md"), f"{test_path} qa_owner must point to cases.md: {qa_owner}"
            assert not _is_git_ignored(owner_path), f"{test_path} qa_owner is ignored by git: {qa_owner}"
            assert _is_git_tracked(owner_path), f"{test_path} qa_owner is not tracked: {qa_owner}"
            assert test_path in _read(owner_path), f"{test_path} is not referenced by {qa_owner}"
        else:
            assert len(exemption) >= 40, f"{test_path} exemption must explain the low-level scope"


def test_hard_coded_qa_paths_in_release_tests_resolve() -> None:
    missing: list[str] = []
    for test_path in sorted(RELEASE_TEST_ROOT.glob("test_*.py")):
        for reference in sorted(_hard_coded_qa_paths(test_path)):
            if not (ROOT / reference).exists():
                missing.append(f"{_relative(test_path)} -> {reference}")

    assert not missing, "Hard-coded qa/... paths in release tests must exist:\n" + "\n".join(missing)


def test_migration_backlog_readme_and_cases_gaps_are_current() -> None:
    stale_rows: list[str] = []
    for feature, gap in _migration_rows():
        feature_dir = QA_ROOT / feature
        if "Missing `README.md`" in gap and (feature_dir / "README.md").exists():
            stale_rows.append(f"{feature}: README.md exists but backlog still says missing")
        if "Missing `cases.md`" in gap and (feature_dir / "cases.md").exists():
            stale_rows.append(f"{feature}: cases.md exists but backlog still says missing")

    assert not stale_rows, "qa/_migration.md has stale README/cases backlog rows:\n" + "\n".join(stale_rows)


def test_cataloged_case_rows_do_not_look_like_completed_runs() -> None:
    violations: list[str] = []
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        for line_number, line in enumerate(_read(cases_path).splitlines(), start=1):
            if (
                "cataloged" in line
                and "NOT YET RUN" not in line
                and not re.search(r"\bBLOCKED(?:\s|;|$)", line)
            ):
                violations.append(f"{_relative(cases_path)}:{line_number}: {line.strip()}")

    assert not violations, (
        "Cataloged-only cases must be marked NOT YET RUN or BLOCKED:\n"
        + "\n".join(violations)
    )


def test_background_agent_browser_loop_case_entrypoint_is_pinned() -> None:
    cases_text = _read(QA_ROOT / "background_agents" / "cases.md")
    for phrase in [
        "real browser prompt/action",
        "activated background agents are visible by name",
        "expanded cards show why/result/status/error details",
        "stored `messages.content` cortex parts match",
        "the main answer does not claim background work has not started",
    ]:
        assert phrase in cases_text
