from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = ROOT / "qa"
RELEASE_TEST_ROOT = ROOT / "tests" / "release"
FEATURE_USE_CASE_CHECKLIST = QA_ROOT / "feature-user-use-case-checklist.md"
REQUIREMENT_SOURCE_COVERAGE = (
    ROOT / "docs" / "requirements_and_learnings" / "requirement_source_coverage.yaml"
)
STALE_CASE_TRIAGE = QA_ROOT / "stale-case-triage.yaml"
CONFIG_COMPILER = ROOT / "scripts" / "viventium" / "config_compiler.py"
GLASSHIVE_RUNTIME_REQUIREMENTS = (
    ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "runtime_phase1"
    / "src"
    / "workers_projects_runtime"
    / "runtime_requirements.py"
)
GLASSHIVE_DOCKER_SANDBOX = GLASSHIVE_RUNTIME_REQUIREMENTS.with_name("docker_sandbox.py")

NON_FEATURE_QA_DIRS = {"_templates", "results"}
AGENT_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
    ROOT / "viventium_v0_4" / "LibreChat" / "CLAUDE.md",
    ROOT / "viventium_v0_4" / "GlassHive" / "AGENTS.md",
    ROOT / "viventium_v0_4" / "GlassHive" / "CLAUDE.md",
]
# Codex does not auto-load above a nested git root. The local overlays explicitly require reading
# the parent contract; the combined sets below model the contract after that required read.
EFFECTIVE_AGENT_DOCS = {
    "Codex at Viventium root": [ROOT / "AGENTS.md"],
    "Claude at Viventium root": [ROOT / "CLAUDE.md", ROOT / "AGENTS.md"],
    "Codex in nested LibreChat after required parent read": [
        ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
        ROOT / "AGENTS.md",
    ],
    "Claude in nested LibreChat": [
        ROOT / "viventium_v0_4" / "LibreChat" / "CLAUDE.md",
        ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "AGENTS.md",
    ],
    "Codex in nested GlassHive after required parent read": [
        ROOT / "viventium_v0_4" / "GlassHive" / "AGENTS.md",
        ROOT / "AGENTS.md",
    ],
    "Claude in nested GlassHive": [
        ROOT / "viventium_v0_4" / "GlassHive" / "CLAUDE.md",
        ROOT / "viventium_v0_4" / "GlassHive" / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "AGENTS.md",
    ],
}
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
CANONICAL_OVERALL_RESULTS = ("PASS", "FAIL", "PARTIAL", "BLOCKED", "NOT RUN")
EXPECTED_SOURCE_POINTER_DIGESTS = {
    "SRC-PARALLEL-WORK-001": "bdbfb7ae0cd76ed6f619d8d5b9ef43abd0cabf6ad959ee27f4929b9df84e883f",
    "SRC-CONSCIOUSNESS-CONTINUITY-001": "3a50dd3eaaded3754687a849b9051a1af34eaf89ef1641fead77b7943fb65dc1",
    "SRC-HOSTED-GLASSHIVE-001": "3761c3ed55accbcd69fcec8d9e74b4296589f0c468ff8e8a32fc02d54f60ee7e",
    "SRC-GLASSHIVE-MAIN-LIFE-001": "6fb6576c294ba948fbc120fb0f81ca42ec4ee0539155575f2ec1fa1f0eb48e8e",
    "SRC-ANTI-SYC-001": "d6f85a03f7a71c19b419570c62583a0302192e6dbec8ae55a58b6239cdf5aa54",
    "SRC-PROMPT-ARCHITECTURE-001": "bb5392de90eb37b14453c3a455951d3fc2cbbc2ec104a5a3c49ae05c6be529b3",
    "SRC-SOURCE-AUDIT-001": "e9b2e6b570baec3898021c2709d9cda50e535b977113dbdb72588363bac61660",
    "SRC-DEVELOPMENT-STYLE-001": "f8e20e39b24826585234d666cf6b4946c97665ffffaa597eb2442a6b33c83530",
    "SRC-SCHEDULED-MAIN-INHERITANCE-001": "f3688bfde48893c6280f66bc01dd14222e171edf0492dd18cffd614108554697",
    "SRC-WHOOP-LIFE-001": "744738408767c16e3ab18ad96781be12224e8e411192a08a79a99d3dde8ccdbc",
    "SRC-TRANSCRIPT-INGESTION-001": "a1a62331f7ccaed6b2008fd7581581b4b0e2e4d109abeab9b67350af65b0a971",
    "SRC-ACTIVATION-RELEASE-001": "33e2f5059334637c21da017f0f5a4d2a9775ba71493e63f51cf9c397c978f830",
}
EXPECTED_CLASSIFICATION_POINTER_DIGESTS = {
    "SRC-PRODUCT-VISION-RESEARCH-001": "50315d5f4cbc73e88f56d30fa17d7e6eec0f7dce251fc4076e0fb70b5d7c2a0a",
    "SRC-COMPETITOR-RESEARCH-001": "89f3147dcdb1ba40ce05e4aab24253919a1a0dac8e61d31e6406e96c272c156b",
    "SRC-OPERATING-REVIEW-001": "1dac6f1aa576116aa7672dd99ac0e72576d6e7e5a133ea9057e948239c3463fb",
    "SRC-CODEX-CAPABILITY-QUESTION-001": "868d6b9a55e5d64321447eef5c72be9857005b5f0d2c91b09718e8d892024c4f",
    "SRC-MACHINE-NOTIFICATION-SUPPORT-001": "d353c63899eebeb445dfaac4952849a28dfc1e835781faef2f0e8c5ff73280df",
    "SRC-AUTOMATION-REPLAY-001": "ee367dede2b3091a6253d776474d5d73def832e4fef8ca2afabb0c66380ea5b6",
    "SRC-AGENT-DERIVED-LANES-001": "c528bb2c9ea5e6a93e567a1f405456ed0dc0d8379876f4bc695bb5600434dc14",
    "SRC-REMAINING-RECOVERABLE-001": "02a034be7c71ed386b9440b7bcc43c6a550b9dc7ac108b35b8d3421350eb6c74",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", _read(path))


def _canonical_overall_result(value: str) -> str | None:
    normalized = value.strip().lstrip("`*_~ ")
    for result in sorted(CANONICAL_OVERALL_RESULTS, key=len, reverse=True):
        if re.match(rf"^{re.escape(result)}(?=$|[\s—:;,.()\[\]`*_])", normalized):
            return result
    return None


def _markdown_table_cells(line: str) -> list[str]:
    """Split one pipe-table row without treating code-span or escaped pipes as columns."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        raise ValueError("Markdown table row must start with a pipe")

    cells: list[str] = []
    current: list[str] = []
    code_fence_width = 0
    index = 0
    while index < len(stripped):
        character = stripped[index]
        if character == "\\" and index + 1 < len(stripped):
            current.extend((character, stripped[index + 1]))
            index += 2
            continue
        if character == "`":
            run_end = index + 1
            while run_end < len(stripped) and stripped[run_end] == "`":
                run_end += 1
            run_width = run_end - index
            current.append(stripped[index:run_end])
            if code_fence_width == 0:
                code_fence_width = run_width
            elif code_fence_width == run_width:
                code_fence_width = 0
            index = run_end
            continue
        if character == "|" and code_fence_width == 0:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())

    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def test_markdown_table_cells_preserve_literal_pipes() -> None:
    assert _markdown_table_cells("| A | `generate|check` | PASS 2026-08-29 |") == [
        "A",
        "`generate|check`",
        "PASS 2026-08-29",
    ]
    assert _markdown_table_cells(r"| A | left\|right | NOT RUN — cataloged 2026-08-29 |") == [
        "A",
        r"left\|right",
        "NOT RUN — cataloged 2026-08-29",
    ]
    assert _markdown_table_cells("| A | ``one|two`` | PASS 2026-08-29 |") == [
        "A",
        "``one|two``",
        "PASS 2026-08-29",
    ]


def _effective_agent_text(paths: list[Path]) -> str:
    return " ".join(_normalized(path) for path in paths)


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


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        assert key not in mapping, (
            f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
        )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_release_test_owners() -> dict[str, dict[str, str]]:
    mapping_path = QA_ROOT / "release-test-owners.yaml"
    payload = yaml.load(_read(mapping_path), Loader=_UniqueKeyLoader)
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
    """Return true only when HEAD contains this exact repository path."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{_relative(path)}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _git_tracked_paths_under(path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", _relative(path)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _is_durable_repo_path(path: Path) -> bool:
    """Return true when current bytes survive HEAD checkout or a pinned component ref."""
    resolved = path.resolve()
    if resolved.is_file() and _is_git_tracked(resolved):
        result = subprocess.run(
            ["git", "show", f"HEAD:{_relative(resolved)}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        return result.returncode == 0 and result.stdout == resolved.read_bytes()
    if resolved.is_dir() and _git_tracked_paths_under(resolved):
        return True

    lock_path = ROOT / "components.lock.json"
    if not lock_path.exists():
        return False
    lock = json.loads(_read(lock_path))
    for component in lock.get("components", []):
        component_root = (ROOT / component["path"]).resolve()
        if not resolved.is_relative_to(component_root):
            continue
        relative = resolved.relative_to(component_root).as_posix()
        pinned_ref = str(component.get("ref") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", pinned_ref):
            return False
        object_name = pinned_ref if not relative else f"{pinned_ref}:{relative}"
        result = subprocess.run(
            ["git", "-C", str(component_root), "cat-file", "-e", object_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    return False


def _markdown_anchor_ids(text: str) -> set[str]:
    anchors = set(
        re.findall(r"<(?:a|span)\s+[^>]*(?:id|name)=[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    )
    counts: dict[str, int] = {}
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.MULTILINE):
        heading = re.sub(r"<[^>]+>", "", match.group(1))
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        heading = re.sub(r"[`*_~]", "", heading).lower().strip()
        slug = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE).replace(" ", "-")
        if not slug:
            continue
        duplicate = counts.get(slug, 0)
        counts[slug] = duplicate + 1
        anchors.add(slug if duplicate == 0 else f"{slug}-{duplicate}")
    return anchors


def _local_markdown_links(
    paths: list[Path],
) -> list[tuple[Path, int, str, Path, str]]:
    links: list[tuple[Path, int, str, Path, str]] = []
    for path in sorted(set(paths)):
        if _is_git_ignored(path):
            continue
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            references: list[str] = []
            markdown_line = re.sub(r"`[^`\n]*`", "", line)
            references.extend(
                match.group(1).strip().strip("<>")
                for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", markdown_line)
            )
            if "/reports/" not in _relative(path):
                references.extend(
                    match.group(1).strip()
                    for match in re.finditer(r"`(qa/[^`\n]+\.md)`", line)
                )
            for reference in references:
                if not reference or reference.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                if any(marker in reference for marker in ("<", ">", "*", "{", "}")):
                    continue
                parsed = urlsplit(reference)
                if parsed.scheme or parsed.netloc:
                    continue
                relative_target = unquote(parsed.path)
                target = (
                    ROOT / relative_target
                    if relative_target.startswith("qa/")
                    else path.parent / relative_target
                )
                links.append((path, line_number, reference, target.resolve(), unquote(parsed.fragment)))
    return links


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


def test_agent_instruction_architecture_is_lean_imported_and_reachable() -> None:
    root_agents = ROOT / "AGENTS.md"
    root_claude = ROOT / "CLAUDE.md"
    librechat_agents = ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md"
    librechat_claude = ROOT / "viventium_v0_4" / "LibreChat" / "CLAUDE.md"
    glasshive_agents = ROOT / "viventium_v0_4" / "GlassHive" / "AGENTS.md"
    glasshive_claude = ROOT / "viventium_v0_4" / "GlassHive" / "CLAUDE.md"

    assert len(_read(root_agents).splitlines()) < 200
    assert root_agents.stat().st_size < 16_384

    root_claude_text = _read(root_claude)
    root_agents_text = _read(root_agents)
    normalized_root_agents = _normalized(root_agents)
    assert root_claude_text.strip() == "@AGENTS.md"
    assert "LACONIC MODE: ON." not in root_agents_text
    assert "ASD-STE100" not in root_agents_text
    expected_outcome_metric = """**outcome = Quality (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast, Smooth, Reliable)**
are the core metric of the viventium project that we must always evaluate in tests, QA, development, design.
Never optimize Performance in isolation — a faster result that is less intelligent, relevant, useful, or
aligned is a regression. Where multiple paths can serve the same request (e.g. an in-process hand-off agent
vs a GlassHive worker), aim for **parity**: each path must meet this metric on its own AI. Do not hardcode a
routing rubric (\"which path for which request\"); let the Main Agent and worker decide intelligently, and make
every path truthful, complete, useful, and fast."""
    assert expected_outcome_metric in root_agents_text
    for contract_term in [
        "Viventium is AI-first: rely on model intelligence for semantic judgment.",
        "do not hardcode or overfit runtime behavior",
        "Prompt or model-behavior changes must use Prompt Workbench",
        "Prompt Workbench exact-model evals provide evidence for model behavior",
        "real-user QA proves the delivered experience",
    ]:
        assert contract_term in normalized_root_agents
    for duplicated_term in [
        "interface.webSearch",
        "feature -> requirement -> use case",
        "VIVENTIUM START",
        "A: current live user-level agent config",
        "complete task specification",
        "genuinely independent, sizeable",
    ]:
        assert duplicated_term not in root_claude_text

    assert _read(librechat_claude).strip() == "@AGENTS.md"
    assert _read(glasshive_claude).strip() == "@AGENTS.md"
    assert "../../AGENTS.md" in _read(librechat_agents)
    assert (librechat_agents.parent / "../../AGENTS.md").resolve() == root_agents
    assert "VIVENTIUM START" in _read(librechat_agents)
    assert "scripts/viventium-sync-agents.js compare --env=<env>" in _read(librechat_agents)
    assert "GlassHive Host Brokerage" in _read(librechat_agents)
    assert "../../AGENTS.md" in _read(glasshive_agents)
    assert (glasshive_agents.parent / "../../AGENTS.md").resolve() == root_agents
    assert "Worker Runtime Boundary" in _read(glasshive_agents)
    assert "host is a faithful courier" in _read(root_agents)

    for label, paths in EFFECTIVE_AGENT_DOCS.items():
        assert all(path.is_file() for path in paths), f"Broken effective instruction set: {label}"


def test_user_grade_qa_loop_disallows_backend_only_substitution() -> None:
    for label, paths in EFFECTIVE_AGENT_DOCS.items():
        assert REQUIRED_LOOP_PHRASE in _effective_agent_text(paths), (
            f"Missing substitution guard in effective instruction set: {label}"
        )

    canonical_paths = [
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
    ]
    for path in canonical_paths:
        assert REQUIRED_LOOP_PHRASE in _normalized(path), f"Missing substitution guard in {path}"

    qa_readme = _read(QA_ROOT / "README.md")
    assert "Playwright CLI or an equivalent real-browser harness" in qa_readme
    assert "Skipping the visible browser step is not acceptable" in qa_readme


def test_full_view_evidence_gate_is_explicit_in_agent_and_qa_docs() -> None:
    for label, paths in EFFECTIVE_AGENT_DOCS.items():
        text = _effective_agent_text(paths)
        for term in FULL_VIEW_EVIDENCE_TERMS:
            assert term in text, (
                f"Missing full-view evidence gate term {term!r} in effective set: {label}"
            )

    canonical_paths = [
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
    ]
    for path in canonical_paths:
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
    for label, paths in EFFECTIVE_AGENT_DOCS.items():
        text = _effective_agent_text(paths).lower()
        assert "natural user" in text, f"Missing natural-user QA gate in effective set: {label}"
        assert "checklist" in text or "feature inventory" in text, (
            f"Missing checklist/feature-inventory QA gate in effective set: {label}"
        )

    canonical_paths = [
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "cases.md",
        QA_ROOT / "_templates" / "feature-readme.md",
        QA_ROOT / "_templates" / "run-report.md",
        FEATURE_USE_CASE_CHECKLIST,
    ]
    for path in canonical_paths:
        text = _normalized(path).lower()
        assert "natural user" in text, f"Missing natural-user QA gate in {path}"
        assert "checklist" in text or "feature inventory" in text, (
            f"Missing checklist/feature-inventory QA gate in {path}"
        )

    combined_text = " ".join(
        [_normalized(ROOT / "AGENTS.md"), *(_normalized(path) for path in canonical_paths)]
    )
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


def test_cataloged_not_run_cases_have_fresh_digest_bound_triage() -> None:
    today = date.today()
    assert not _is_git_ignored(STALE_CASE_TRIAGE)
    triage = yaml.safe_load(_read(STALE_CASE_TRIAGE))
    assert triage["schema_version"] == 1
    max_age_days = triage["max_age_days"]
    assert max_age_days == 90
    assert triage["first_cataloged_on_source"] == (
        "inline_cataloged_date_or_machine_readable_catalogedOn"
    )
    assert triage["first_cataloged_on_immutable"] is True
    reviewed_on = triage["reviewed_on"]
    if isinstance(reviewed_on, str):
        reviewed_on = date.fromisoformat(reviewed_on)
    assert 0 <= (today - reviewed_on).days <= max_age_days
    assert triage["disposition"] == "review_before_expiry_or_during_next_owning_change"
    assert triage["deterministic_enforcement"] == [
        "first_cataloged_on_presence",
        "review_age",
        "marker_count",
        "marker_digest",
    ]
    assert triage["process_obligation"] == "next_owning_feature_change_review"
    assert "does not claim that the test can infer" in triage["reason"]
    assert len(triage["reason"]) >= 120

    pattern = re.compile(r"NOT RUN[^\n]*cataloged (\d{4})-(\d{2})-(\d{2})", re.IGNORECASE)
    missing_catalog_dates: list[str] = []
    stale_by_path: dict[str, list[str]] = {}
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        lines = _read(cases_path).splitlines()
        last_run_line_re = re.compile(
            r"^\s*-?\s*(?:\*\*)?Last run(?:(?:\*\*)?:|:(?:\*\*)?)\s*",
            re.IGNORECASE,
        )
        for line_number, line in enumerate(lines, start=1):
            if last_run_line_re.match(line):
                value = last_run_line_re.sub("", line)
                if _canonical_overall_result(value) == "NOT RUN" and not pattern.search(value):
                    missing_catalog_dates.append(
                        f"{_relative(cases_path)}:{line_number}: {value.strip()}"
                    )
        for index, line in enumerate(lines):
            if not line.lstrip().startswith("|") or "last run" not in line.lower():
                continue
            headings = _markdown_table_cells(line)
            lowered = [heading.lower() for heading in headings]
            if "last run" not in lowered:
                continue
            last_run_index = lowered.index("last run")
            for row_number in range(index + 2, len(lines)):
                row = lines[row_number]
                if not row.lstrip().startswith("|"):
                    break
                cells = _markdown_table_cells(row)
                if not cells or not cells[0] or re.fullmatch(r":?-+:?", cells[0]):
                    continue
                if len(cells) != len(headings):
                    continue
                value = cells[last_run_index]
                if _canonical_overall_result(value) == "NOT RUN" and not pattern.search(value):
                    missing_catalog_dates.append(
                        f"{_relative(cases_path)}:{row_number + 1}: {value}"
                    )

        stale_lines: list[str] = []
        for line in lines:
            match = pattern.search(line)
            if not match:
                continue
            cataloged = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if (today - cataloged).days > max_age_days:
                stale_lines.append(line.rstrip())
        if stale_lines:
            stale_by_path[_relative(cases_path)] = stale_lines

    continuity_contract = json.loads(
        _read(QA_ROOT / "main-continuity" / "contract.v1.json")
    )
    for case in continuity_contract["qaCases"]:
        if case["result"] != "NOT RUN":
            continue
        cataloged_on = str(case.get("catalogedOn") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cataloged_on):
            missing_catalog_dates.append(
                f"qa/main-continuity/contract.v1.json:{case['id']}: missing catalogedOn"
            )

    assert not missing_catalog_dates, (
        "Every NOT RUN overall result needs its immutable first catalog date:\n"
        + "\n".join(missing_catalog_dates)
    )

    entries = {entry["path"]: entry for entry in triage["entries"]}
    assert set(entries) == set(stale_by_path), (
        "Stale NOT RUN case files must exactly match qa/stale-case-triage.yaml"
    )
    for path, lines in stale_by_path.items():
        entry = entries[path]
        digest = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
        assert entry["marker_count"] == len(lines), f"Stale marker count changed for {path}"
        assert entry["marker_sha256"] == digest, f"Stale marker content changed for {path}"
    assert _is_durable_repo_path(STALE_CASE_TRIAGE), (
        "qa/stale-case-triage.yaml content is internally current but its bytes must also match HEAD"
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
            "FAIL (escaped 2026-05-18",
        ]:
            assert phrase in text, f"Missing escaped voice/web-search case phrase {phrase!r} in {owner}"


def test_evidence_retrieval_failures_have_classification_prereq_and_fallback_contract() -> None:
    required_terms = [
        "provider unavailable",
        "timeout",
        "rate limit",
        "auth/config missing",
        "request rejected",
        "Docker",
    ]
    for label, paths in EFFECTIVE_AGENT_DOCS.items():
        text = _effective_agent_text(paths)
        for term in required_terms:
            assert term in text, (
                f"Missing evidence-retrieval QA term {term!r} in effective set: {label}"
            )

    core_paths = [
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        ROOT / "docs" / "requirements_and_learnings" / "10_Open_Source_Web_Search.md",
        QA_ROOT / "README.md",
        QA_ROOT / "web-search" / "README.md",
        QA_ROOT / "web-search" / "cases.md",
    ]
    for path in core_paths:
        text = _normalized(path)
        for term in required_terms:
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

    exact_row_tokens = {
        "02_Background_Agents.md": ["737/737", "2026-07-15", "`DEGRADED`"],
        "06_Voice_Calls.md": ["MPV-UC-025", "`FAIL` 2026-08-25"],
        "39_Installer_and_Config_Compiler.md": [
            "qa/installer-resilience/cases.md",
            "INST-027",
            "INST-UC-019",
        ],
        "49_Prompt_Architecture_and_Token_Efficiency.md": [
            "qa/prompt-architecture/cases.md",
            "PROMPT-001",
            "PROMPT-003",
            "PROMPT-007",
            "PROMPT-UC-001",
            "PROMPT-UC-007",
        ],
        "54_Emotional_Cortex_And_Feeling_State.md": [
            "EMO-055",
            "EMO-UC-048",
        ],
    }
    matrix_rows = {
        doc_name: next(
            line for line in matrix_text.splitlines() if f"[`{doc_name}`]" in line
        )
        for doc_name in exact_row_tokens
    }
    for doc_name, tokens in exact_row_tokens.items():
        missing_tokens = [token for token in tokens if token not in matrix_rows[doc_name]]
        assert not missing_tokens, (
            f"{doc_name} Runtime Feature QA Map row misses exact joins/status: {missing_tokens}"
        )


def test_requirement_source_coverage_ledger_is_private_safe_and_resolves() -> None:
    data = yaml.safe_load(_read(REQUIREMENT_SOURCE_COVERAGE))
    assert data["schema_version"] == 2
    assert data["privacy_contract"]["raw_prompts"] == "private_only"
    assert data["privacy_contract"]["public_source_identifiers"] == "opaque_aliases_only"
    assert data["privacy_contract"]["pointer_digest_definition"] == (
        "sha256 of sorted private task pointers plus exact retained message pointer, content hash, "
        "provenance, and eligibility lines"
    )
    assert data["privacy_contract"]["pointer_digest_canonicalization"] == (
        "sorted_unique_typed_pointer_utf8_lines_with_trailing_newline"
    )
    assert data["privacy_contract"]["historical_retention"] == "partial_source_retention"
    assert "must never be read as proof" in data["privacy_contract"]["limitation"]

    private_receipt = data["private_companion_receipt"]
    assert private_receipt["receipt_id"] == "VSA-2026-08-30"
    assert private_receipt["storage_boundary"] == "separate_authorized_private_repository"
    assert private_receipt["durability"] == "working_tree_only_until_authorized_commit"
    assert private_receipt["access_procedure"] == (
        "Authorized maintainers locate receipt VSA-2026-08-30 in the project's private companion "
        "repository under curated private docs; request access from the repository owner."
    )
    assert private_receipt["payload_file_count"] == 1
    assert private_receipt["files_manifest_sha256"] == "0" * 64
    assert private_receipt["receipt_sha256"] == "0" * 64
    assert private_receipt["integrity_sha256"] == (
        "a36e4dab40f64792363799a2d50616c6b1cd485644f3062c83557b792714c91e"
    )
    private_receipt_payload = "\t".join(
        [
            private_receipt["receipt_id"],
            str(private_receipt["payload_file_count"]),
            private_receipt["files_manifest_sha256"],
            private_receipt["receipt_sha256"],
            data["atomic_traceability"]["message_group_trace_sha256"],
            data["atomic_traceability"]["semantic_atomic_trace_sha256"],
            data["atomic_traceability"]["derived_audit_requirement_ids_sha256"],
            data["atomic_traceability"]["crosswalk_join_sha256"],
            data["atomic_traceability"]["all_eligible_disposition_sha256"],
        ]
    ) + "\n"
    assert hashlib.sha256(private_receipt_payload.encode()).hexdigest() == private_receipt[
        "integrity_sha256"
    ]
    assert "one trailing LF" in private_receipt["canonicalization"]
    assert "not clean-checkout durable" in private_receipt["limitation"]

    atomic = data["atomic_traceability"]
    assert atomic["registry_status"] == "manual_partial_retention_audit_receipt"
    assert atomic["mapping_unit"] == (
        "semantic_requirement_or_disposition_alias_on_exact_retained_human_requirement_payload_span"
    )
    assert atomic["finite_reference_graph_messages"] == 617
    assert atomic["direct_human_messages"] == 597
    assert atomic["legacy_human_likely_messages"] == 20
    assert atomic["distinct_normalized_texts"] == 248
    assert atomic["source_context_qualified_groups"] == 254
    assert atomic["all_eligible_original_corpus_messages"] == 972
    assert atomic["all_eligible_supplemental_messages"] == 4
    assert atomic["all_eligible_message_dispositions"] == 976
    assert atomic["all_eligible_disposition_only_messages"] == 359
    assert atomic["disposition_only_clause_trace_messages"] == 42
    assert atomic["disposition_only_failure_evidence_messages"] == 1
    assert atomic["disposition_only_reviewed_messages"] == 316
    assert atomic["disposition_only_exact_clause_spans"] == 170
    assert atomic["disposition_only_message_to_requirement_joins"] == 306
    assert atomic["disposition_only_clause_span_to_requirement_joins"] == 506
    assert atomic["all_eligible_distinct_normalized_texts"] == 427
    assert atomic["all_eligible_disposition_sha256"] == (
        "e3f38d99ca26122b3e1bba3c32fe9e573d451c32f7669c08e923621dc7dc6113"
    )
    assert "message_pointer, thread_id, raw_text_chars" in atomic[
        "all_eligible_disposition_canonicalization"
    ]
    assert "exact_semantic_clause_spans_json" in atomic[
        "all_eligible_disposition_canonicalization"
    ]
    assert atomic["message_group_trace_sha256"] == (
        "c865faffc72c752538d7d023f933a2988207725a6eaad7ddd3e5c76dfa90845e"
    )
    assert atomic["message_group_trace_canonicalization"].startswith(
        "sha256 of sorted unique tab-separated context"
    )
    assert atomic["semantic_atomic_trace_rows"] == 1409
    assert atomic["semantic_atomic_requirement_rows"] == 1337
    assert atomic["semantic_atomic_no_requirement_rows"] == 72
    assert (
        atomic["semantic_atomic_requirement_rows"]
        + atomic["semantic_atomic_no_requirement_rows"]
        == atomic["semantic_atomic_trace_rows"]
    )
    assert atomic["semantic_atomic_trace_sha256"] == (
        "80cf8c33895137aeb9f610cf3154c72e70f6f1f022c934957283f1a278e5640d"
    )
    assert atomic["semantic_atomic_trace_canonicalization"].startswith(
        "SHA-256 of UTF-8 bytes for lexicographically sorted unique tab-separated rows"
    )
    assert "mutable QA/evidence join fields are excluded" in atomic[
        "semantic_atomic_trace_canonicalization"
    ]
    assert atomic["stable_requirement_ids"] == 360
    assert atomic["stable_requirement_ids_with_atomic_aliases"] == 304
    assert atomic["stable_requirement_ids_with_disposition_only_direct_mappings"] == 8
    assert atomic["stable_requirement_ids_with_any_direct_message_mapping"] == 312
    assert atomic["required_owner_declaration_rows"] == 288
    assert atomic["required_owner_declaration_sha256"] == (
        "2c389b9861e73de660bb84a2d65b5e56bc374264729d5f5da26fe246b9040671"
    )
    assert atomic["required_owner_declaration_canonicalization"].startswith(
        "sha256 of lexicographically sorted unique tab-separated requirement ID"
    )
    assert "QA files provide acceptance only" in atomic["required_owner_declaration_rule"]
    declaration_pattern = re.compile(r"^([A-Z]+-\d{3}): (\S.*)$")
    declaration_rows: list[str] = []
    declaration_ids: list[str] = []
    for path in sorted((ROOT / "docs/requirements_and_learnings").glob("*.md")):
        for line in _read(path).splitlines():
            match = declaration_pattern.fullmatch(line)
            if not match:
                continue
            declaration_ids.append(match.group(1))
            declaration_rows.append(
                "\t".join((match.group(1), _relative(path), match.group(2)))
            )
    assert len(declaration_ids) == len(set(declaration_ids)) == 288
    declaration_payload = "\n".join(sorted(set(declaration_rows))) + "\n"
    assert hashlib.sha256(declaration_payload.encode()).hexdigest() == atomic[
        "required_owner_declaration_sha256"
    ]
    assert atomic["derived_audit_requirement_ids_without_direct_alias"] == 48
    assert atomic["derived_audit_requirement_ids_sha256"] == (
        "72fd14720dd80735c97c4bae68626b9f10affdbeec1f08c6ff441083f1ad597d"
    )
    assert atomic["derived_audit_requirement_ids_canonicalization"].startswith(
        "sha256 of lexicographically sorted unique stable requirement ids"
    )
    assert "exact 48 stable audit IDs" in atomic["derived_definition"]
    assert "no direct retained eligible-message" in atomic["derived_definition"]
    assert "cannot be used to infer exact user wording" in atomic["inverse_attribution_limit"]
    assert atomic["derived_deterministic_scope"] == (
        "exact_direct_vs_derived_set_closure_and_digest_only"
    )
    assert atomic["derived_semantic_review"] == (
        "manual_word_level_review_against_private_provenance_and_crosswalk"
    )
    assert "cannot prove that a synthesis is semantically correct" in atomic[
        "derived_semantic_limitation"
    ]
    assert atomic["crosswalk_join_rows"] == 360
    assert atomic["required_acceptance_join_rows"] == 288
    assert atomic["required_acceptance_join_sha256"] == (
        "e34703a39b8eb136907237347c3dd4023516a7934968649b79b7ef840982c785"
    )
    assert atomic["required_acceptance_join_canonicalization"] == (
        "sha256_of_exact_tsv_file_bytes"
    )
    assert "unique exact stable-ID declaration" in atomic["required_acceptance_locator_rule"]
    assert "exact UTF-8 declaration line with SHA-256" in atomic[
        "required_acceptance_locator_rule"
    ]
    assert atomic["crosswalk_join_sha256"] == (
        "4eaed9a735e11bc636a8799d056b5779f2d8537d52ce3f0d93267f5637a5bb10"
    )
    assert atomic["crosswalk_join_canonicalization"].startswith(
        "SHA-256 of UTF-8 bytes for lexicographically sorted unique tab-separated rows"
    )
    assert "missing_join_record" in atomic["crosswalk_join_canonicalization"]
    assert atomic["span_granularity"] == (
        "exact_retained_human_requirement_payload_utf8_bytes_after_documented_envelope_exclusions"
    )
    assert atomic["direct_human_messages"] + atomic["legacy_human_likely_messages"] == 617
    assert "private verified annex" in atomic["public_rule"]
    assert "not the 360-row stable-ID inventory" in atomic["public_rule"]
    assert "288 REQUIRED IDs have canonical public owner" in atomic["public_rule"]
    assert "one semantic requirement or explicit no-requirement disposition" in atomic[
        "public_rule"
    ]
    assert "raw user-role payload has a separate verified hash" in atomic["public_rule"]
    assert "not an inferred subclause offset" in atomic["public_rule"]
    assert "not the generated product/service" in atomic["public_rule"]
    assert "ONB-011" in atomic["public_rule"]
    assert "976 retained eligible messages" in atomic["limitation"]
    assert "purged follow-ups" in atomic["limitation"]

    inventory = data["private_inventory_summary"]
    assert inventory == {
        "exact_root_sessions": 1845,
        "descendant_directory_sessions": 237,
        "original_corpus_human_eligible_messages": 972,
        "supplemental_human_eligible_messages": 4,
        "total_retained_human_eligible_messages": 976,
        "excluded_control_or_injected_records": 510,
        "tasks_with_full_followup_history": 83,
        "tasks_with_first_message_only": 317,
        "tasks_with_no_retained_prompt": 1,
        "exact_private_inventory": "task/message/attachment/image ledgers outside the public repository",
    }
    screenshot = data["screenshot_crosscheck"]
    assert screenshot["visible_rows"] == 48
    assert screenshot["distinct_visible_label_families"] == 41
    assert (
        screenshot["direct_or_likely_human_rows"]
        + screenshot["agent_derived_rows"]
        + screenshot["automation_replay_rows"]
        == screenshot["total_check"]
        == screenshot["visible_rows"]
    )
    assert "never promoted to fresh user requirements" in screenshot["rule"]

    vocabulary = data["disposition_vocabulary"]
    assert vocabulary["required_as_of_field"] == "disposition_as_of"
    allowed_dispositions = set(vocabulary["allowed"])
    assert allowed_dispositions == {
        "captured_acceptance_open",
        "captured_live_acceptance_failed",
        "captured_acceptance_partial",
        "captured_current_source_contract_failed",
        "reconciled_documentation_contract_partial_source_retention",
        "reconciled_current_instruction_contract",
        "captured_live_acceptance_passed",
        "captured_live_analysis_failed",
        "captured_release_acceptance_open",
        "not_current_runtime_truth",
        "not_automatically_adopted",
        "supports_existing_requirements",
        "excluded_from_viventium_product_truth",
        "qa_evidence_only",
        "trace_to_human_parent",
        "retained_private_not_promoted_without_specific_adoption",
    }

    join_inventory = data["crosswalk_join_inventory"]
    assert join_inventory["as_of"] == date(2026, 8, 30)
    assert join_inventory["total_stable_ids"] == 360
    assert join_inventory["requirements_with_any_missing_join"] == 72
    assert join_inventory["missing_exact_owner_path"] == 61
    assert join_inventory["missing_natural_use_case_excluding_superseded_history"] == 45
    assert join_inventory["missing_qa_case_excluding_superseded_history"] == 39
    assert join_inventory["qa_join_status_counts"] == {
        "EXACT_QA_CASE_AND_NATURAL_USE_CASE_DECLARATIONS": 293,
        "EXACT_QA_CASE_ONLY_MISSING_NATURAL_USE_CASE": 7,
        "EXACT_NATURAL_USE_CASE_ONLY_MISSING_QA_CASE": 1,
        "MISSING_EXACT_QA_CASE_AND_NATURAL_USE_CASE": 38,
        "NOT_APPLICABLE_SUPERSEDED_HISTORY": 21,
    }
    assert join_inventory["requirements_with_any_missing_join_by_prefix"] == {
        "CC": 2,
        "DATA": 1,
        "GAP": 21,
        "GOV": 4,
        "HARD": 6,
        "OPEN": 17,
        "SUP": 21,
    }
    assert join_inventory["required_disposition"] == {
        "total": 288,
        "with_any_missing_join": 0,
        "missing_exact_owner_path": 0,
        "missing_natural_use_case": 0,
        "missing_qa_case": 0,
        "fully_joined": 288,
        "alignment_verdict": "ALIGNED_FOR_RETAINED_REQUIRED_SOURCES",
    }
    assert "not an implicit product PASS claim" in join_inventory["rule"]
    assert "QA is acceptance only" in join_inventory["rule"]
    assert "Locator line digests" in join_inventory["rule"]

    stale_catalog = data["stale_case_catalog_audit"]
    assert stale_catalog == {
        "as_of": date(2026, 8, 30),
        "initial_audit_recent_marker_total": 86,
        "markers_in_current_files_absent_from_head": 75,
        "markers_in_untracked_current_files": 11,
        "existing_case_catalog_date_resets": 0,
        "current_recent_marker_total": 267,
        "post_initial_audit_recent_marker_delta": 181,
        "current_stale_triage_marker_total": 164,
        "current_total_stale_marker_delta_after_initial_audit": 0,
        "method": "read_only_current_marker_comparison_against_head",
        "durability": "working_tree_only_until_authorized_commit",
        "limitation": (
            "These markers preserve NOT RUN debt; they are not execution results. The separate "
            "stale-case triage manifest keeps its own 2026-08-29 review boundary and remains "
            "non-durable while untracked."
        ),
    }
    stale_triage = yaml.safe_load(_read(STALE_CASE_TRIAGE))
    assert stale_catalog["current_stale_triage_marker_total"] == sum(
        entry["marker_count"] for entry in stale_triage["entries"]
    )
    recent_marker_pattern = re.compile(r"cataloged 2026-08-(?:29|30)", re.IGNORECASE)
    assert stale_catalog["current_recent_marker_total"] == sum(
        len(recent_marker_pattern.findall(_read(path)))
        for path in QA_ROOT.rglob("*.md")
    )

    sources = data["sources"]
    aliases = [source["source_alias"] for source in sources]
    assert len(aliases) == len(set(aliases))
    assert set(aliases) == set(EXPECTED_SOURCE_POINTER_DIGESTS)

    for source in sources:
        assert re.fullmatch(r"SRC-[A-Z0-9-]+-\d{3}", source["source_alias"])
        assert source["pointer_set_sha256"] == EXPECTED_SOURCE_POINTER_DIGESTS[
            source["source_alias"]
        ]
        assert source["retention"] == "partial_source_retention"
        assert len(source["goal"]) >= 40
        assert len(source["remaining_gap"]) >= 40
        assert source["disposition"] in allowed_dispositions
        assert source["disposition_as_of"] == date(2026, 8, 30)
        stable_requirement_ids = source.get("stable_requirement_ids", [])
        assert len(stable_requirement_ids) == len(set(stable_requirement_ids)), source[
            "source_alias"
        ]
        for owner in source["requirements"]:
            owner_path = (REQUIREMENT_SOURCE_COVERAGE.parent / owner["owner"]).resolve()
            assert owner_path.exists(), owner["owner"]
            assert owner_path.is_relative_to(ROOT), owner["owner"]
            owner_text = _read(owner_path)
            anchors = owner.get("anchors", [])
            requirement_ids = owner.get("ids", [])
            assert bool(anchors) != bool(requirement_ids), owner
            assert len(anchors) == len(set(anchors)), owner
            assert len(requirement_ids) == len(set(requirement_ids)), owner
            for anchor in anchors:
                assert anchor in owner_text, (
                    f"Missing requirement anchor {anchor!r} in {_relative(owner_path)}"
                )
            for requirement_id in requirement_ids:
                assert requirement_id in owner_text, (
                    f"Missing requirement id {requirement_id!r} in {_relative(owner_path)}"
                )
        for owner in source["qa_refs"]:
            owner_path = ROOT / owner["owner"]
            assert owner_path.exists(), owner["owner"]
            owner_text = _read(owner_path)
            case_ids = owner.get("case_ids", [])
            use_case_ids = owner.get("use_case_ids", [])
            assert case_ids or use_case_ids, owner
            assert len(case_ids) == len(set(case_ids)), owner
            assert len(use_case_ids) == len(set(use_case_ids)), owner
            assert not any("-UC-" in case_id for case_id in case_ids), owner
            assert all("-UC-" in use_case_id for use_case_id in use_case_ids), owner
            if owner_path.suffix == ".json":
                payload = json.loads(owner_text)
                defined_case_ids = {
                    str(case.get("id") or "") for case in payload.get("qaCases", [])
                }
                assert set(case_ids).issubset(defined_case_ids), (
                    f"QA cases must be definitions in {_relative(owner_path)}: "
                    f"{sorted(set(case_ids) - defined_case_ids)}"
                )
                assert not use_case_ids, owner
            else:
                for case_id in case_ids:
                    assert re.search(
                        rf"^(?:##\s+`?{re.escape(case_id)}`?(?:\s|:|—|$)|"
                        rf"\|\s*`?{re.escape(case_id)}`?\s*\|)",
                        owner_text,
                        re.MULTILINE,
                    ), f"Missing exact QA case definition {case_id!r} in {_relative(owner_path)}"
                for use_case_id in use_case_ids:
                    assert re.search(
                        rf"^\|\s*`?{re.escape(use_case_id)}`?\s*\|",
                        owner_text,
                        re.MULTILINE,
                    ), (
                        f"Missing exact natural use-case definition {use_case_id!r} "
                        f"in {_relative(owner_path)}"
                    )

        owner_texts = [
            _read((REQUIREMENT_SOURCE_COVERAGE.parent / owner["owner"]).resolve())
            for owner in source["requirements"]
        ]
        qa_texts = [_read(ROOT / owner["owner"]) for owner in source["qa_refs"]]
        atomic_outcomes = source.get("atomic_outcomes", [])
        assert len({outcome["outcome"] for outcome in atomic_outcomes}) == len(atomic_outcomes)
        for outcome in atomic_outcomes:
            assert len(outcome["outcome"]) >= 40
            assert outcome["owner_refs"]
            assert outcome["qa_refs"]
            assert len(outcome["owner_refs"]) == len(set(outcome["owner_refs"])), outcome
            assert len(outcome["qa_refs"]) == len(set(outcome["qa_refs"])), outcome
            requirement_ids = outcome.get("requirement_ids", [])
            assert len(requirement_ids) == len(set(requirement_ids)), outcome
            for owner_ref in outcome["owner_refs"]:
                assert any(owner_ref in owner_text for owner_text in owner_texts), (
                    f"Missing atomic owner reference {owner_ref!r} for {source['source_alias']}"
                )
            for qa_ref in outcome["qa_refs"]:
                assert any(qa_ref in qa_text for qa_text in qa_texts), (
                    f"Missing atomic QA reference {qa_ref!r} for {source['source_alias']}"
                )

    atomic_sources = {
        source["source_alias"] for source in sources if source.get("atomic_outcomes")
    }
    assert atomic_sources == {
        "SRC-HOSTED-GLASSHIVE-001",
        "SRC-PROMPT-ARCHITECTURE-001",
    }

    prompt_source = next(
        source
        for source in sources
        if source["source_alias"] == "SRC-PROMPT-ARCHITECTURE-001"
    )
    expected_prompt_requirement_ids = {
        "GOV-001",
        "GOV-002",
        "GOV-003",
        "GOV-023",
        "GOV-024",
        "GOV-025",
        "GOV-026",
        "GOV-027",
        "OPEN-016",
        "OPEN-017",
        "OPEN-018",
    }
    assert set(prompt_source["stable_requirement_ids"]) == expected_prompt_requirement_ids
    prompt_owner_text = _read(
        ROOT
        / "docs"
        / "requirements_and_learnings"
        / "49_Prompt_Architecture_and_Token_Efficiency.md"
    )
    for requirement_id in expected_prompt_requirement_ids:
        assert prompt_owner_text.count(f"`{requirement_id}`") >= 1, (
            f"Prompt source requirement {requirement_id} is missing from its public owner"
        )
    outcome_requirement_ids = {
        requirement_id
        for outcome in prompt_source["atomic_outcomes"]
        for requirement_id in outcome["requirement_ids"]
    }
    open_decisions = {
        decision["requirement_id"]: decision["decision"]
        for decision in prompt_source["open_decisions"]
    }
    flattened_outcome_requirement_ids = [
        requirement_id
        for outcome in prompt_source["atomic_outcomes"]
        for requirement_id in outcome["requirement_ids"]
    ]
    assert len(flattened_outcome_requirement_ids) == len(
        set(flattened_outcome_requirement_ids)
    )
    open_decision_ids = [
        decision["requirement_id"] for decision in prompt_source["open_decisions"]
    ]
    assert len(open_decision_ids) == len(set(open_decision_ids))
    assert outcome_requirement_ids == {
        requirement_id
        for requirement_id in expected_prompt_requirement_ids
        if not requirement_id.startswith("OPEN-01") or requirement_id == "OPEN-018"
    }
    assert set(open_decisions) == {"OPEN-016", "OPEN-017", "OPEN-018"}
    assert all(len(decision) >= 60 for decision in open_decisions.values())

    source_audit = next(
        source for source in sources if source["source_alias"] == "SRC-SOURCE-AUDIT-001"
    )
    expected_source_audit_ids = {
        "GOV-004",
        "GOV-005",
        "GOV-006",
        "GOV-007",
        "GOV-008",
        "GOV-009",
        "GOV-010",
        "GOV-011",
        "GOV-012",
        "GOV-021",
        "GOV-022",
    }
    assert set(source_audit["stable_requirement_ids"]) == expected_source_audit_ids
    assert source_audit["qa_join_strength"] == "source_audit_specific"
    assert "DOCIMPL-007 remains FAIL" in source_audit["remaining_gap"]
    assert "QASYS-004 contract PASS is not current feature acceptance" in source_audit[
        "remaining_gap"
    ]
    source_audit_owner = _read(QA_ROOT / "README.md")
    for requirement_id in expected_source_audit_ids:
        assert source_audit_owner.count(f"`{requirement_id}`") == 1

    development_style = next(
        source for source in sources if source["source_alias"] == "SRC-DEVELOPMENT-STYLE-001"
    )
    assert development_style["qa_join_strength"] == (
        "shared_process_contract_not_feature_specific"
    )

    activation_source = next(
        source
        for source in sources
        if source["source_alias"] == "SRC-ACTIVATION-RELEASE-001"
    )
    assert set(activation_source["open_requirement_ids"]) == {
        "ONB-007",
        "ONB-008",
        "ONB-011",
        "ONB-012",
        "GAP-020",
        "GAP-021",
    }
    assert "generated product/service" in activation_source["remaining_gap"]

    classifications = data["source_classifications"]
    classification_aliases = [entry["source_alias"] for entry in classifications]
    assert len(classification_aliases) == len(set(classification_aliases))
    assert set(classification_aliases) == set(EXPECTED_CLASSIFICATION_POINTER_DIGESTS)
    for entry in classifications:
        assert entry["pointer_set_sha256"] == EXPECTED_CLASSIFICATION_POINTER_DIGESTS[
            entry["source_alias"]
        ]
        assert entry["classification"]
        assert entry["disposition"] in allowed_dispositions
        assert entry["disposition_as_of"] == date(2026, 8, 30)
        assert len(entry["rationale"]) >= 40

    raw = _read(REQUIREMENT_SOURCE_COVERAGE)
    assert "/Users/" not in raw
    assert not re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", raw)
    assert not re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        raw,
        re.IGNORECASE,
    )
    assert not re.search(r"\b(?:msg|thread|task)_[0-9a-f]{12,}\b", raw, re.IGNORECASE)


def test_requirement_source_coverage_ledger_and_owners_are_durable() -> None:
    data = yaml.safe_load(_read(REQUIREMENT_SOURCE_COVERAGE))
    paths = [REQUIREMENT_SOURCE_COVERAGE]
    for source in data["sources"]:
        paths.extend(
            (REQUIREMENT_SOURCE_COVERAGE.parent / owner["owner"]).resolve()
            for owner in source["requirements"]
        )
        paths.extend((ROOT / owner["owner"]).resolve() for owner in source["qa_refs"])

    violations: list[str] = []
    for path in sorted(set(paths)):
        if _is_git_ignored(path):
            violations.append(f"{_relative(path)} is ignored")
        if not _is_durable_repo_path(path):
            violations.append(f"{_relative(path)} current bytes do not match HEAD or a pinned ref")

    assert not violations, "Source-ledger owners must survive a clean checkout:\n" + "\n".join(violations)


def test_current_requirement_and_qa_local_markdown_evidence_links_resolve() -> None:
    paths = sorted((ROOT / "docs" / "requirements_and_learnings").glob("*.md"))
    paths += sorted((ROOT / "viventium_v0_4" / "docs").glob("*.md"))
    paths += sorted(QA_ROOT.rglob("*.md"))
    violations: list[str] = []

    for path, line_number, reference, resolved, fragment in _local_markdown_links(paths):
        location = f"{_relative(path)}:{line_number} -> {reference}"
        if not resolved.is_relative_to(ROOT):
            violations.append(f"{location} escapes the repository")
            continue
        if not resolved.exists():
            violations.append(f"{location} is missing")
            continue
        if fragment and resolved.is_file() and resolved.suffix.lower() == ".md":
            if fragment not in _markdown_anchor_ids(_read(resolved)):
                violations.append(f"{location} has no matching fragment")

    assert not violations, (
        "Current requirement/QA links must be contained, present, and fragment-valid:\n"
        + "\n".join(violations)
    )


def test_runtime_feature_qa_map_links_are_durable() -> None:
    paths = [
        ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md"
    ]
    violations: list[str] = []

    for path, line_number, reference, resolved, _fragment in _local_markdown_links(paths):
        if not resolved.is_relative_to(ROOT) or not resolved.exists():
            continue
        if not _is_durable_repo_path(resolved):
            violations.append(
                f"{_relative(path)}:{line_number} -> {reference} does not match HEAD or "
                "a pinned component ref"
            )

    assert not violations, (
        "The central runtime feature/QA map must survive a clean checkout:\n"
        + "\n".join(sorted(set(violations)))
    )


def test_current_alignment_regressions_stay_reconciled() -> None:
    map_text = _read(ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md")
    checklist = _read(FEATURE_USE_CASE_CHECKLIST)
    architecture = _read(ROOT / "viventium_v0_4" / "docs" / "ARCHITECTURE.md")
    runtime_doc = _read(
        ROOT
        / "docs"
        / "requirements_and_learnings"
        / "48_GlassHive_Workstation_Sandbox_Runtime.md"
    )
    installer_doc = _read(
        ROOT / "docs" / "requirements_and_learnings" / "39_Installer_and_Config_Compiler.md"
    )
    all_cases = "\n".join(_read(path) for path in sorted(QA_ROOT.glob("*/cases.md")))

    for term in [
        "57_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md",
        "58_Anti_Sycophancy_and_Truth_Seeking.md",
        "SCHED-023",
        "PW-050",
        "PERI-014",
    ]:
        assert term in map_text
    for term in ["qa/glasshive-user-control-plane/", "qa/anti-sycophancy/"]:
        assert term in checklist
    compiler_source = _read(CONFIG_COMPILER)
    def one_source_value(pattern: str) -> str:
        matches = re.findall(pattern, compiler_source)
        assert len(matches) == 1, f"Expected one compiler owner for {pattern!r}, got {matches}"
        return matches[0]

    voice_phase_a_ms = one_source_value(
        r'env\["VIVENTIUM_VOICE_PHASE_A_AWAIT_MS"\]\s*=\s*"(\d+)"'
    )
    text_phase_a_ms = one_source_value(
        r'env\["VIVENTIUM_TEXT_PHASE_A_AWAIT_MS"\]\s*=\s*"(\d+)"'
    )
    shared_detect_ms = one_source_value(
        r'env\["VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS"\]\s*=\s*"(\d+)"'
    )
    late_detect_ms = one_source_value(
        r'DEFAULT_CORTEX_LATE_DETECT_TIMEOUT_MS\s*=\s*"(\d+)"'
    )
    runtime_flow = _markdown_section(architecture, "## Runtime Flow (Server)")
    runtime_flow_normalized = re.sub(r"\s+", " ", runtime_flow)
    exact_detection_sentence = (
        "Phase A activation detection runs in the mode-specific fast window: "
        f"{text_phase_a_ms} ms for text and {voice_phase_a_ms} ms for voice by shipped default. "
        f"The shared {shared_detect_ms} ms value is only the fallback when a mode-specific value is unset."
    )
    assert runtime_flow_normalized.count(exact_detection_sentence) == 1
    assert f"non-blocking {late_detect_ms} ms late- recovery window" in runtime_flow_normalized
    assert "newer visible exchange" in architecture

    background_doc = _read(
        ROOT / "docs" / "requirements_and_learnings" / "02_Background_Agents.md"
    )
    assert re.search(
        rf"detection budget\s*\|[^\n]*\*\*{voice_phase_a_ms} ms\*\*[^\n]*"
        rf"\*\*{text_phase_a_ms} ms\*\*",
        background_doc,
    )
    assert background_doc.count(
        f"`VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS` (default {shared_detect_ms} ms)"
    ) == 1
    assert background_doc.count(
        f"`VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS` defaults to **{late_detect_ms} ms**"
    ) == 1

    host_requirements = _read(GLASSHIVE_RUNTIME_REQUIREMENTS)
    codex_min = re.search(
        r'"codex-cli":\s*\[.*?"min_version":\s*"([^"]+)"',
        host_requirements,
        re.DOTALL,
    )
    claude_min = re.search(
        r'"claude-code":\s*\[.*?"min_version":\s*"([^"]+)"',
        host_requirements,
        re.DOTALL,
    )
    sandbox_source = _read(GLASSHIVE_DOCKER_SANDBOX)
    codex_npm = re.search(r'WPR_SANDBOX_CODEX_NPM_SPEC",\s*"([^"]+)"', sandbox_source)
    claude_npm = re.search(r'WPR_SANDBOX_CLAUDE_CODE_NPM_SPEC",\s*"([^"]+)"', sandbox_source)
    assert codex_min and claude_min and codex_npm and claude_npm
    for term in [
        f">={codex_min.group(1)}",
        f">={claude_min.group(1)}",
        codex_npm.group(1),
        claude_npm.group(1),
    ]:
        assert term in runtime_doc
    assert "2.1.229" not in runtime_doc
    assert "signed `Viventium.app` contract" in installer_doc
    assert "all nine default Nature/half-life/enabled values" in installer_doc
    assert "NOT YET RUN" not in all_cases
    assert not re.search(r"\bPENDING\b", all_cases)


def test_scheduling_catalog_details_and_natural_use_cases_cover_every_current_case() -> None:
    text = _read(QA_ROOT / "scheduling-cortex" / "cases.md")
    summary_rows: dict[str, list[str]] = {}
    use_case_rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*`(SCHED-\d{3})`\s*\|", line)
        if match:
            summary_rows[match.group(1)] = _markdown_table_cells(line)
        use_case_match = re.match(r"^\|\s*`(SCHED-UC-\d{3})`\s*\|", line)
        if use_case_match:
            use_case_rows[use_case_match.group(1)] = _markdown_table_cells(line)

    stopwords = {
        "and", "after", "before", "from", "into", "must", "only", "that", "the", "this",
        "uses", "using", "with", "without", "until", "when", "where", "whose",
    }

    def objective_terms(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if len(token) >= 4 and token not in stopwords
        }

    for number in range(1, 27):
        case_id = f"SCHED-{number:03d}"
        use_case_id = f"SCHED-UC-{number:03d}"
        heading_match = re.search(
            rf"^## `{re.escape(case_id)}`\s*-\s*(.+)$", text, re.MULTILINE
        )
        assert heading_match, case_id
        assert text.count(f"`{use_case_id}`") == 1, use_case_id
        assert case_id in summary_rows, case_id
        assert use_case_id in use_case_rows, use_case_id
        assert len(summary_rows[case_id]) == 5, f"{case_id} summary row width"
        assert len(use_case_rows[use_case_id]) == 7, f"{use_case_id} row width"
        section = _markdown_section(text, f"## `{case_id}`")
        for field in [
            "Scenario:",
            "Requirement:",
            "Risk covered:",
            "Preconditions:",
            "Steps:",
            "Expected result:",
            "Forbidden result:",
            "Evidence to capture:",
            "Automation:",
            "Last run:",
        ]:
            assert field in section, f"{case_id} missing {field}"
        detail_match = re.search(r"^- Last run:\s*(.+)$", section, re.MULTILINE)
        assert detail_match, case_id
        summary_last_run = summary_rows[case_id][-1]
        use_case_last_run = use_case_rows[use_case_id][-1]
        summary_status = _canonical_overall_result(summary_last_run)
        detail_status = _canonical_overall_result(detail_match.group(1))
        use_case_status = _canonical_overall_result(use_case_last_run)
        assert summary_status, f"{case_id} summary lacks canonical overall status"
        assert detail_status, f"{case_id} detail lacks canonical overall status"
        assert use_case_status, f"{use_case_id} lacks canonical overall status"
        summary_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", summary_last_run)
        detail_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", detail_match.group(1))
        use_case_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", use_case_last_run)
        assert summary_date and detail_date and use_case_date, (
            f"{case_id} summary, detail, and use case need an evidence or catalog date"
        )
        assert (summary_status, summary_date.group(0) if summary_date else None) == (
            detail_status,
            detail_date.group(0) if detail_date else None,
        ), f"{case_id} summary/detail status or date drift"
        assert (summary_status, summary_date.group(0)) == (
            use_case_status,
            use_case_date.group(0),
        ), f"{case_id} summary/use-case status or date drift"
        assert case_id in use_case_rows[use_case_id][2], f"{use_case_id} does not map to {case_id}"

        summary_terms = objective_terms(summary_rows[case_id][1])
        heading_terms = objective_terms(heading_match.group(1))
        assert summary_terms & heading_terms, f"{case_id} summary/detail objective drift"
        assert len(use_case_rows[use_case_id][1]) >= 30, f"{use_case_id} action is underspecified"

    map_text = _read(ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md")
    assert "`SCHED-001`–`SCHED-026`" in map_text
    for case_id, result in {
        "SCHED-019": "PARTIAL",
        "SCHED-023": "FAIL",
        "SCHED-024": "NOT RUN",
        "SCHED-025": "PARTIAL",
    }.items():
        assert re.search(rf"`{case_id}` is `{result}`", map_text)

    requirement_text = _read(
        ROOT / "docs" / "requirements_and_learnings" / "11_Scheduling_Cortex.md"
    )
    assert "SCHEDULED_SELF_PROMPT_LINE" not in requirement_text
    assert "_default_scheduler_run_envelope" in requirement_text
    assert "render_scheduler_run_envelope" in requirement_text
    assert "unbounded integer `SCHEDULER_STREAM_TIMEOUT_S` override" in requirement_text


def test_glasshive_user_control_plane_summary_and_detail_status_dates_align() -> None:
    text = _read(QA_ROOT / "glasshive-user-control-plane" / "cases.md")
    summary_rows: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*`(GHUCP-\d{3})`\s*\|", line)
        if not match:
            continue
        cells = _markdown_table_cells(line)
        assert len(cells) == 6, f"{match.group(1)} summary row width"
        summary_rows[match.group(1)] = cells[-1]

    assert set(summary_rows) == {f"GHUCP-{number:03d}" for number in range(1, 36)}
    for case_id, summary_last_run in summary_rows.items():
        section = _markdown_section(text, f"## `{case_id}`")
        detail_match = re.search(r"^- Last run:\s*(.+)$", section, re.MULTILINE)
        assert detail_match, f"{case_id} missing detail Last run"
        detail_last_run = detail_match.group(1)
        summary_status = _canonical_overall_result(summary_last_run)
        detail_status = _canonical_overall_result(detail_last_run)
        summary_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", summary_last_run)
        detail_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", detail_last_run)
        assert summary_status and detail_status, f"{case_id} lacks canonical status"
        assert summary_date and detail_date, f"{case_id} lacks a Last Run date"
        assert (summary_status, summary_date.group(0)) == (
            detail_status,
            detail_date.group(0),
        ), f"{case_id} summary/detail status or date drift"

    natural_section = _markdown_section(text, "## Natural User Use Case Checklist")
    use_case_rows = re.findall(r"^\|\s*`(GHUCP-UC-\d{3})`\s*\|(.+)$", natural_section, re.MULTILINE)
    assert {use_case_id for use_case_id, _ in use_case_rows} == {
        f"GHUCP-UC-{number:03d}" for number in range(1, 14)
    }
    for use_case_id, remainder in use_case_rows:
        cells = _markdown_table_cells(f"| `{use_case_id}` |{remainder}")
        assert len(cells) == 7, f"{use_case_id} row width"
        assert _canonical_overall_result(cells[-1]), f"{use_case_id} lacks canonical status"
        assert re.search(r"\b\d{4}-\d{2}-\d{2}\b", cells[-1]), (
            f"{use_case_id} lacks a Last Run date"
        )


def test_case_catalog_overall_results_use_only_canonical_status_tokens() -> None:
    violations: list[str] = []
    for cases_path in sorted(QA_ROOT.glob("*/cases.md")):
        if cases_path.parent.name == "_templates":
            continue
        lines = _read(cases_path).splitlines()
        last_run_line_re = re.compile(
            r"^\s*-?\s*(?:\*\*)?Last run(?:(?:\*\*)?:|:(?:\*\*)?)\s*",
            re.IGNORECASE,
        )
        for line_number, line in enumerate(lines, start=1):
            if last_run_line_re.match(line):
                value = last_run_line_re.sub("", line)
                if not _canonical_overall_result(value):
                    violations.append(f"{_relative(cases_path)}:{line_number}: {value.strip()}")
                elif not re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
                    violations.append(
                        f"{_relative(cases_path)}:{line_number}: missing Last Run date: "
                        f"{value.strip()}"
                    )

        for index, line in enumerate(lines):
            if not line.lstrip().startswith("|") or "last run" not in line.lower():
                continue
            headings = _markdown_table_cells(line)
            last_run_index = [heading.lower() for heading in headings].index("last run")
            assert last_run_index == len(headings) - 1, (
                f"{_relative(cases_path)}:{index + 1} must keep Last Run as the final column"
            )
            for row_number in range(index + 2, len(lines)):
                row = lines[row_number]
                if not row.lstrip().startswith("|"):
                    break
                cells = _markdown_table_cells(row)
                if not cells or not cells[0] or re.fullmatch(r":?-+:?", cells[0]):
                    continue
                if len(cells) != len(headings):
                    violations.append(
                        f"{_relative(cases_path)}:{row_number + 1}: "
                        f"{len(cells)} cells under {len(headings)} headings"
                    )
                    continue
                value = cells[last_run_index]
                if not _canonical_overall_result(value):
                    violations.append(f"{_relative(cases_path)}:{row_number + 1}: {value}")
                elif not re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
                    violations.append(
                        f"{_relative(cases_path)}:{row_number + 1}: "
                        f"missing Last Run date: {value}"
                    )

    continuity_contract = json.loads(
        _read(QA_ROOT / "main-continuity" / "contract.v1.json")
    )
    for case in continuity_contract["qaCases"]:
        result = str(case.get("result") or "")
        if result not in CANONICAL_OVERALL_RESULTS:
            violations.append(
                f"qa/main-continuity/contract.v1.json:{case.get('id')}: {result or '<missing>'}"
            )
        supporting_result = str(case.get("supportingResult") or "")
        if supporting_result and supporting_result not in {"PASS-LIVE", "PASS-AUTOMATED"}:
            violations.append(
                "qa/main-continuity/contract.v1.json:"
                f"{case.get('id')}: invalid supporting result {supporting_result}"
            )

    assert not violations, (
        "QA catalogs must use a dated PASS, FAIL, PARTIAL, BLOCKED, or NOT RUN overall result; "
        "qualified layer labels belong in prose:\n" + "\n".join(violations)
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
            if "cataloged" in line and "NOT RUN" not in line:
                violations.append(f"{_relative(cases_path)}:{line_number}: {line.strip()}")

    assert not violations, "Cataloged-only cases must be marked NOT RUN:\n" + "\n".join(violations)


def test_telegram_runtime_case_ids_are_unique_and_cross_repo_contract_agrees() -> None:
    catalog = _read(QA_ROOT / "telegram-runtime" / "cases.md")
    case_ids = re.findall(r"^## Case (TR-\d{3}):", catalog, re.MULTILINE)
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    assert not duplicates, f"Duplicate Telegram runtime case IDs: {duplicates}"
    assert "## Case TR-014: Installed Telegram Is Source-Independent" in catalog
    assert "## Case TR-026: Rapid Segments Supersede One Unfinished Reply" in catalog
    assert "## Case TR-029: Delivery Dependency Failure" in catalog
    assert "## Case TR-030: Reply To A Scheduled Output" in catalog
    assert "## Case TR-014: Rapid Segments" not in catalog

    use_case_ids = re.findall(r"^\| `(TELEGRAM-UC-\d{3})` \|", catalog, re.MULTILINE)
    duplicate_use_cases = sorted(
        {use_case_id for use_case_id in use_case_ids if use_case_ids.count(use_case_id) > 1}
    )
    assert not duplicate_use_cases, f"Duplicate Telegram natural use-case IDs: {duplicate_use_cases}"

    nested_source = _read(
        ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "packages"
        / "api"
        / "src"
        / "glasshive"
        / "orchestrationMode.ts"
    )
    assert "['qa/telegram-runtime/cases.md', 'TR-026']" in nested_source
    assert "['qa/telegram-runtime/cases.md', 'TR-014']" not in nested_source


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
