#!/usr/bin/env python3
"""Resolve explicit QA modes and a candidate static release-test selection.

CLI: --scope skip|critical-path|blast-radius|full. Critical path requires repeatable
--test file[::node] and --reason. GitHub uses the same fields in workflow_dispatch
inputs or one fenced ``viventium-qa`` JSON object in the PR body. Explicit PR
retries read the current handoff only when head/base SHAs still match. On push, the merged
PR handoff is recovered through GitHub's read-only commit/pulls endpoint; direct
pushes may include the same fence in the head commit message. Invalid or unavailable
handoffs fail closed. No shared path or failed diff can authorize a full run.

Static references identify candidates, not complete semantic consumers. The receipt
names unmapped paths and parse failures. Selection is never execution evidence.
See qa/README.md, "Verification Scope And Handoff".
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

TEST_DIR = "tests/release"
LOCK_FILE = "components.lock.json"

MODES = ("skip", "critical-path", "blast-radius", "full")
# Disjoint PR/push ownership; a manual Config Compile run uses "all".
PARTITIONS = {
    "policy": frozenset({
        "tests/release/test_public_bootstrap_manifests.py",
        "tests/release/test_private_repo_resolution_contract.py",
        "tests/release/test_qa_operating_contract.py",
        "tests/release/test_qa_storage_guard.py",
    }),
    "activation": frozenset({
        "tests/release/test_ci_release_workflows.py",
        "tests/release/test_no_runtime_nlu.py",
    }),
}
LIBRECHAT = "viventium_v0_4/LibreChat"
PLAYGROUND = "viventium_v0_4/agent-starter-react"
LANES = ("node", "librechat_deps", "librechat_packages", "librechat_client", "playground_deps", "audio_tools")
# These nodes digest the repository's own runtime artifact manifest, which lists LibreChat and
# xPerfect runtime sources and LibreChat's package and client build outputs. The manifest is
# data, so the path trace cannot see these reads.
RUNTIME_MANIFEST_DIGEST_CONSUMERS = frozenset({
    "tests/release/test_parallel_work_release_gate.py::test_runtime_service_manifest_binds_tracked_nonempty_runtime_inputs",
    "tests/release/test_glasshive_qa_parent_control.py::test_cleanup_remains_available_after_the_exact_session_expires",
    "tests/release/test_glasshive_qa_parent_control.py::test_cleanup_rejects_same_size_parent_state_mutation_before_fixture_delete",
})
# These nodes find the Health checkout through its lock entry, not an anchored path.
HEALTH_CHECKOUT_READERS = frozenset({
    "tests/release/test_viventium_health_runtime.py::test_health_component_pin_matches_the_reviewed_component_head",
    "tests/release/test_viventium_health_runtime.py::test_health_runtime_install_is_private_self_contained_and_reads_empty_archive",
    "tests/release/test_viventium_health_runtime.py::test_health_runtime_reinstall_preserves_archive_and_replaces_runtime",
    "tests/release/test_viventium_health_runtime.py::test_health_runtime_install_reuses_matching_artifact_without_rebuild",
    "tests/release/test_viventium_health_runtime.py::test_health_runtime_install_rebuilds_a_tampered_installed_package",
    "tests/release/test_viventium_health_runtime.py::test_public_cli_materializes_and_runs_the_health_component",
    "tests/release/test_viventium_health_runtime.py::test_installed_health_runtime_serves_only_bounded_read_tools",
})
# Real audio execution was traced in the audit. Mentioning ffmpeg in a mocked
# subprocess or a source assertion must not install it. Add consumers with evidence.
LANE_CONSUMERS = {
    # This shell fixture delegates only the report parser to the real Node binary.
    "node": frozenset({
        "tests/release/test_ci_release_workflows.py::test_live_activation_eval_shell_preserves_pass_failure_and_outage_semantics",
        "tests/release/test_parallel_work_installed_journey_qa.py",
    }),
    "librechat_client": RUNTIME_MANIFEST_DIGEST_CONSUMERS,
    # Importing agent-sync loads the API and data-provider workspace packages.
    "librechat_packages": frozenset({
        "tests/release/test_agent_sync_review_contract.py::test_agent_sync_compare_reviews_user_visible_sequential_output_policy",
    }),
    "audio_tools": frozenset({
        "tests/release/test_mpv_061_installed_scenario_preparation.py::test_local_say_and_ffmpeg_create_two_distinct_private_audible_wavs",
        "tests/release/test_voice_playground_dispatch_contract.py::test_synthetic_audio_qa_captures_actual_remote_audio_as_private_audible_wav",
    }),
}

# Data-driven reads can fall outside the Python path trace. Keep confirmed
# source-only checkouts attached to their consumer, not every test in its file.
CHECKOUT_CONSUMERS = {
    "tests/release/test_qa_operating_contract.py::test_current_requirement_and_qa_local_markdown_evidence_links_resolve": (
        LIBRECHAT, "viventium_v0_4/xPerfect", "viventium_v0_4/Viventium-Health",
    ),
    # The node joins ROOT to paths from a set and checks each file exists.
    # Telegram is parent-tracked. Its adjacent shape-only node needs no checkout.
    "tests/release/test_parallel_work_release_gate.py::test_runtime_service_manifest_binds_runtime_controls_and_kernel_process_reader": (
        LIBRECHAT, "viventium_v0_4/xPerfect",
    ),
    **{node: (LIBRECHAT, "viventium_v0_4/xPerfect") for node in RUNTIME_MANIFEST_DIGEST_CONSUMERS},
    **{node: ("viventium_v0_4/Viventium-Health",) for node in HEALTH_CHECKOUT_READERS},
}

ROOT_NAMES = frozenset({"ROOT", "REPO_ROOT", "REPO", "REPOSITORY_ROOT", "PROJECT_ROOT"})
# Receivers of these operations are anchors inside a longer path, not dependencies themselves.
ANCHOR_ATTRIBUTES = frozenset(
    {"parent", "parents", "joinpath", "resolve", "absolute", "expanduser", "with_name", "with_suffix"}
)
# Walking the repository root from a test or module means any change can matter to it. A constant
# glob pattern is recorded as `glob:<pattern>` so it matches only the files it can list.
REPO_SCAN_ATTRIBUTES = frozenset({"iterdir", "walk"})
GLOB_ATTRIBUTES = frozenset({"glob", "rglob"})
ANY_CHANGE = "*"
PATH_TOKEN = re.compile(
    r"[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)+|[A-Za-z0-9_-]+\.(?:py|sh|cjs|mjs|js|json|ya?ml)"
)
FOLLOWED_SUFFIXES = (".py", ".sh", ".cjs", ".mjs", ".js")
ESCAPED = "\0"
# Marks a path found in free text (shell, JavaScript, or a sibling-relative Python string). Such a
# path counts only when it names a file: idioms like `$SCRIPT_DIR/../..` must not become a
# dependency on a whole directory.
SIBLING = "\1"


class SelectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Repository:
    root: Path
    files: frozenset[str]
    dirs: frozenset[str]
    components: dict[str, str]  # component path -> canonical pin entry at the selected head

    @classmethod
    def load(cls, root: Path) -> "Repository":
        files = frozenset(p for p in _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0") if p)
        dirs = set()
        for path in files:
            parent = PurePosixPath(path).parent
            while str(parent) != ".":
                dirs.add(str(parent))
                parent = parent.parent
        return cls(root, files, frozenset(dirs), _components(_read_text(root / LOCK_FILE)))

    def component_of(self, path: str) -> str | None:
        return next((c for c in self.components if path == c or path.startswith(c + "/")), None)


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SelectionError(f"git {' '.join(args[:2])} failed") from exc
    return result.stdout


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _components(lock_text: str) -> dict[str, str]:
    try:
        entries = json.loads(lock_text).get("components", [])
    except (ValueError, AttributeError):
        return {}
    return {
        str(entry["path"]).strip("/"): json.dumps(entry, sort_keys=True)
        for entry in entries
        if isinstance(entry, dict) and entry.get("path")
    }


def _normalize(path: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(path.replace("\\", "/")).parts:
        if part in ("", ".", "/"):
            continue
        if part == "..":
            if not parts:
                return ESCAPED
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


class _PythonScan:
    """Statically resolve the repository paths and modules one Python file uses."""

    def __init__(self, relative_file: str, tree: ast.AST) -> None:
        self.file = relative_file
        self.tree = tree
        self.values: dict[str, str] = {}
        self.parents: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parents[id(child)] = node
        for node in ast.walk(tree):  # names bound to paths, e.g. ROOT = Path(__file__).parents[2]
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) and node.value else []
            for target in targets:
                if isinstance(target, ast.Name):
                    value = self.path(node.value)  # type: ignore[union-attr]
                    if value is not None:
                        self.values[target.id] = value

    def path(self, node: ast.AST | None) -> str | None:
        """Return the repository-relative path `node` evaluates to, or None when unknown."""
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return self.file
            return self.values.get(node.id, "" if node.id in ROOT_NAMES else None)
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            base = self.path(node.value)
            return None if base is None else _normalize(base + "/..")
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
            base, index = self.path(node.value.value), getattr(node.slice, "value", None)
            return None if base is None or not isinstance(index, int) else _normalize(base + "/.." * (index + 1))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            base, part = self.path(node.left), _literal(node.right)
            return None if base is None or part is None else _normalize(f"{base}/{part}")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"Path", "PurePath", "PosixPath", "str"} and len(node.args) == 1:
                return self.path(node.args[0])
            if isinstance(func, ast.Attribute) and func.attr in {"resolve", "absolute", "expanduser"}:
                return self.path(func.value)
            if isinstance(func, ast.Attribute) and func.attr in {"with_name", "with_suffix"} and len(node.args) == 1:
                base, part = self.path(func.value), _literal(node.args[0])
                if base is None or part is None:
                    return None
                if func.attr == "with_name":
                    return _normalize(f"{base}/../{part}")
                return str(PurePosixPath(base).with_suffix(part)) if PurePosixPath(base).suffix else None
            if isinstance(func, ast.Attribute) and func.attr == "joinpath":
                base, parts = self.path(func.value), [_literal(a) for a in node.args]
                if base is not None and parts and all(p is not None for p in parts):
                    return _normalize("/".join([base, *parts]))  # type: ignore[list-item]
        return None

    def _is_anchor_use(self, node: ast.AST) -> bool:
        parent = self.parents.get(id(node))
        if isinstance(parent, ast.BinOp) and parent.left is node:
            return True
        if isinstance(parent, ast.Attribute) and parent.attr in ANCHOR_ATTRIBUTES:
            return True
        if isinstance(parent, (ast.Assign, ast.AnnAssign)):
            return True  # recorded where the bound name is used
        if isinstance(parent, ast.Call) and self.path(parent) is not None:
            return True  # Path(x) / str(x) wrappers: the call is the maximal expression
        return False

    def _in_sys_path_call(self, node: ast.AST) -> bool:
        current = self.parents.get(id(node))
        while current is not None:
            func = getattr(current, "func", None)
            if isinstance(func, ast.Attribute) and func.attr in {"insert", "append"}:
                receiver = func.value
                if isinstance(receiver, ast.Attribute) and receiver.attr == "path":
                    return True
            current = self.parents.get(id(current))
        return False

    def _glob_dependency(self, node: ast.AST, value: str) -> str | None:
        parent = self.parents.get(id(node))
        call = self.parents.get(id(parent)) if parent is not None else None
        if not (isinstance(parent, ast.Attribute) and parent.attr in GLOB_ATTRIBUTES and isinstance(call, ast.Call)):
            return None
        pattern = _literal(call.args[0]) if call.args else None
        if pattern is None:
            return ANY_CHANGE if value == "" else value
        if parent.attr == "rglob":
            pattern = "**/" + pattern
        return "glob:" + (f"{value}/{pattern}" if value else pattern)

    def dependencies(self) -> tuple[set[str], set[str], set[str], set[tuple[str, ...]]]:
        """Return (paths used, paths built from repository anchors, import roots, module names)."""
        anchors = {""}
        ancestor = PurePosixPath(self.file).parent
        while str(ancestor) != ".":
            anchors.add(str(ancestor))
            ancestor = ancestor.parent
        used: set[str] = set()
        rooted: set[str] = set()
        roots: set[str] = set()
        imports: set[tuple[str, ...]] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imports.update(tuple(alias.name.split(".")) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = tuple(node.module.split(".")) if node.module else ()
                if node.level:
                    base = PurePosixPath(self.file).parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    prefix = "/".join((str(base), *module)) if module else str(base)
                    used.add(prefix + ".py")
                    used.update(f"{prefix}/{alias.name}.py" for alias in node.names)
                elif module:
                    imports.add(module)
                    imports.update((*module, alias.name) for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 400:
                here = str(PurePosixPath(self.file).parent)
                for token in PATH_TOKEN.findall(node.value):
                    used.add(_normalize(token))
                    used.add(SIBLING + _normalize(f"{here}/{token}"))
            elif isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.BinOp, ast.Call)):
                value = self.path(node)
                if value is None and isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                    # `KNOWN_DIR / runtime_value` reads something inside that directory.
                    inside = self.path(node.left)
                    if inside is not None and inside not in anchors and not self._in_sys_path_call(node):
                        used.add(inside)
                        rooted.add(inside)
                    continue
                if value is None or value == ESCAPED:
                    continue
                parent = self.parents.get(id(node))
                glob = self._glob_dependency(node, value)
                walked = isinstance(parent, ast.Attribute) and parent.attr in REPO_SCAN_ATTRIBUTES
                walked = walked or (isinstance(parent, ast.Call) and getattr(parent.func, "attr", None) == "walk")
                if self._in_sys_path_call(node):
                    roots.add(value)
                elif glob is not None:
                    used.add(glob)
                    rooted.add(glob)
                elif value == "" and walked:
                    used.add(ANY_CHANGE)
                elif not self._is_anchor_use(node) and value not in anchors:
                    used.add(value)
                    rooted.add(value)
        return used, rooted, roots, imports


class DependencyTrace:
    """Transitive repository dependencies of release test files, computed once per run."""

    def __init__(self, repo: Repository, extra_known: set[str] | None = None) -> None:
        self.repo = repo
        self.extra_known = extra_known or set()
        self._direct: dict[str, set[str] | None] = {}
        self.rooted: dict[str, set[str]] = {}
        self.unparsed: set[str] = set()

    def known(self, path: str) -> bool:
        return (
            path == ANY_CHANGE
            or path.startswith("glob:")
            or path in self.repo.files
            or path in self.repo.dirs
            or path in self.extra_known
            or self.repo.component_of(path) is not None
        )

    def direct(self, path: str) -> set[str] | None:
        """Dependencies named by one file; None when a Python file cannot be parsed."""
        if path not in self._direct:
            self._direct[path] = self._scan(path)
        return self._direct[path]

    def _scan(self, path: str) -> set[str] | None:
        text = _read_text(self.repo.root / path)
        here = str(PurePosixPath(path).parent)
        candidates: set[str] = set()
        if path.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                self.unparsed.add(path)
                return None
            used, rooted, roots, imports = _PythonScan(path, tree).dependencies()
            candidates |= used
            self.rooted[path] = {c for c in rooted if self.known(c)}
            for module in imports:
                for root in {TEST_DIR, "scripts/viventium", "scripts", "", here, *roots}:
                    base = "/".join(p for p in (root, *module) if p)
                    candidates.update({base + ".py", base + "/__init__.py"})
        else:
            for token in PATH_TOKEN.findall(text):
                candidates.update({SIBLING + _normalize(token), SIBLING + _normalize(f"{here}/{token}")})
        resolved = set()
        for candidate in candidates:
            if candidate.startswith(SIBLING):
                candidate = candidate[len(SIBLING):]
                if candidate not in self.repo.files and candidate not in self.extra_known and self.repo.component_of(candidate) is None:
                    continue
            if candidate not in ("", ESCAPED) and candidate != path and self.known(candidate):
                resolved.add(candidate)
        return resolved

    def _followable(self, path: str) -> bool:
        if path not in self.repo.files:
            return False
        if path.endswith(FOLLOWED_SUFFIXES):
            return True
        return PurePosixPath(path).suffix == "" and _read_text(self.repo.root / path).startswith("#!")

    def closure(self, test_file: str) -> set[str] | None:
        """Everything `test_file` depends on, transitively; None when it cannot be traced."""
        seen = {test_file}
        pending = [test_file]
        while pending:
            dependencies = self.direct(pending.pop())
            if dependencies is None:
                if len(seen) == 1:
                    return None  # the test itself is unparsable: always select it
                continue
            for dependency in dependencies - seen:
                seen.add(dependency)
                if self._followable(dependency):
                    pending.append(dependency)
        return seen


def _glob_matches(pattern: str, path: str) -> bool:
    if "**" in pattern:
        prefix = pattern.split("**", 1)[0]
        return path.startswith(prefix) and fnmatch.fnmatchcase(path, pattern.replace("**/", "*"))
    parts, pattern_parts = path.split("/"), pattern.split("/")
    return len(parts) == len(pattern_parts) and all(map(fnmatch.fnmatchcase, parts, pattern_parts))


def _depends(dependencies: set[str], changed: str) -> bool:
    for d in dependencies:
        if d == ANY_CHANGE:
            return True
        if d.startswith("glob:"):
            if _glob_matches(d[5:], changed):
                return True
        elif changed == d or changed.startswith(d + "/") or d.startswith(changed + "/"):
            return True
    return False


@dataclass
class Selection:
    scope: str
    full: bool
    reason: str
    tests: list[str]
    lanes: dict[str, bool]
    changed: list[str]
    components: list[str]
    unmapped: list[str]
    prerequisites: list[str] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    status: str = "candidate"
    partition: str = "all"
    elsewhere: list[str] = field(default_factory=list)
    live_refs: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**vars(self), "count": len(self.tests)}


def changed_paths(root: Path, base: str, head: str) -> tuple[list[str], list[str]]:
    """Return paths changed since the merge base, and component paths whose pins changed."""
    merge_base = _git(root, "merge-base", base, head).strip()
    changed = sorted({p for p in _git(root, "diff", "--name-only", "--no-renames", merge_base, head).splitlines() if p})
    components: list[str] = []
    if LOCK_FILE in changed:
        before = _components(_git_show(root, merge_base, LOCK_FILE))
        after = _components(_git_show(root, head, LOCK_FILE))
        components = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    return changed, components


def _git_show(root: Path, revision: str, path: str) -> str:
    try:
        return _git(root, "show", f"{revision}:{path}")
    except SelectionError:
        return ""


def _definition_tree(repo: Repository, selector: str) -> ast.Module:
    """Validate a file/node without importing it or collecting/executing tests."""
    if not isinstance(selector, str) or any(ord(c) < 32 or ord(c) == 127 for c in selector):
        raise SelectionError("test selectors must be strings without control characters")
    path, *nodes = selector.split("::")
    if (path != _normalize(path) or not path.startswith(TEST_DIR + "/test_")
            or not path.endswith(".py") or path not in repo.files
            or not (repo.root / path).is_file()
            or not (repo.root / path).resolve().is_relative_to(repo.root.resolve())):
        raise SelectionError("test selector must name an existing repository release test file")
    try:
        tree = ast.parse((repo.root / path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise SelectionError(f"cannot validate test definitions in {path}") from exc
    body = tree.body
    for index, node_id in enumerate(nodes):
        # Parameter IDs remain literal pytest argv. Their existence is checked by pytest;
        # source validation proves the owning definition, without executing decorators.
        name = node_id.split("[", 1)[0]
        if (not name.isidentifier() or ("[" in node_id and
                (index != len(nodes) - 1 or not node_id.endswith("]")))):
            raise SelectionError(f"invalid test node in {path}")
        definition = next((n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                           and n.name == name), None)
        if definition is None or (isinstance(definition, ast.ClassDef) and not name.startswith("Test")):
            raise SelectionError(f"test node does not exist in {path}: {name}")
        if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)) and not name.startswith("test_"):
            raise SelectionError(f"selector does not name a test in {path}")
        body = definition.body
    return tree


def _selected_tree(tree: ast.Module, selector: str) -> ast.Module:
    """Bound prerequisite scanning to selected definitions and referenced local helpers.

    This is static evidence. Dynamic fixtures/imports can still require more setup.
    Referenced module bindings and eager file reads remain in the scan.
    """
    parts = selector.split("::")
    if len(parts) == 1:
        return tree
    wanted = {parts[1].split("[", 1)[0]}
    definitions = {n.name: n for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    # Autouse fixtures run even when not named in a test signature.
    wanted.update(n.name for n in definitions.values()
                  if any(isinstance(d, ast.Call) and any(k.arg == "autouse" and
                         isinstance(k.value, ast.Constant) and k.value.value is True for k in d.keywords)
                         for d in getattr(n, "decorator_list", [])))
    pending = list(wanted)
    while pending:
        current = definitions.get(pending.pop())
        if current is None:
            continue
        used = {n.id for n in ast.walk(current) if isinstance(n, ast.Name)}
        used.update(n.arg for n in ast.walk(current) if isinstance(n, ast.arg))
        extra = (used & definitions.keys()) - wanted
        wanted.update(extra)
        pending.extend(extra)
    chosen = [n for n in definitions.values() if n.name in wanted]
    used = {n.id for definition in chosen for n in ast.walk(definition) if isinstance(n, ast.Name)}
    assignments = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    included: set[int] = set()
    changed = True
    while changed:
        changed = False
        for statement in assignments:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            names = {n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)}
            # Eager file reads also happen during module import for a node selection.
            eager = any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") in
                        {"read_text", "read_bytes", "open"} for n in ast.walk(statement))
            if id(statement) not in included and (names & used or eager):
                included.add(id(statement))
                used.update(n.id for n in ast.walk(statement) if isinstance(n, ast.Name))
                changed = True
    return ast.Module(body=[n for n in tree.body if
        (n.name in wanted if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else
         id(n) in included if isinstance(n, (ast.Assign, ast.AnnAssign)) else True)], type_ignores=[])


def _executes_node(tree: ast.Module) -> bool:
    """Find Node in an actual subprocess executable slot, not a string assertion.

    Resolve the common `node = shutil.which("node")` binding only when that
    binding is passed as the executable. A standalone availability probe is not
    installation authority. Indirect harness consumers are declared above.
    """
    values = {target.id: n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
              for target in n.targets if isinstance(target, ast.Name)}
    def node_executable(value: ast.AST, seen: frozenset[str] = frozenset()) -> bool:
        if isinstance(value, ast.Constant):
            return value.value in ("node", "nodejs")
        if isinstance(value, ast.Name) and value.id in values and value.id not in seen:
            return node_executable(values[value.id], seen | {value.id})
        return (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name) and value.func.value.id == "shutil"
                and value.func.attr == "which" and bool(value.args)
                and isinstance(value.args[0], ast.Constant) and value.args[0].value in ("node", "nodejs"))
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "subprocess"
                and call.func.attr in {"run", "Popen", "check_call", "check_output", "call"}):
            continue
        argv = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "args"), None)
        if isinstance(argv, ast.Name):
            argv = values.get(argv.id)
        if isinstance(argv, (ast.List, ast.Tuple)) and argv.elts and node_executable(argv.elts[0]):
            return True
    return False


def _executed_python_paths(repo: Repository, path: str, tree: ast.Module) -> set[str]:
    """Resolve Python entrypoints in subprocess argv without running test code.

    Script arguments can be rooted Paths, str(Path) wrappers, literal paths,
    bound argv lists, or -m module names. Reading a script with cat, mentioning
    its path, or passing it as data after -c is not execution evidence.
    """
    scan = _PythonScan(path, tree)
    values = {target.id: n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
              for target in n.targets if isinstance(target, ast.Name)}
    def resolve(node: ast.AST | None, seen: frozenset[str] = frozenset()) -> ast.AST | None:
        if isinstance(node, ast.Name) and node.id in values and node.id not in seen:
            return resolve(values[node.id], seen | {node.id})
        return node

    def script_path(node: ast.AST, *, relative_allowed: bool) -> str | None:
        result = scan.path(node)
        if result is None:
            value = _literal(resolve(node))
            if value and relative_allowed and not PurePosixPath(value).is_absolute():
                result = _normalize(value)
        return result if result in repo.files and result.endswith(".py") else None

    paths: set[str] = set()
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "subprocess"
                and call.func.attr in {"run", "Popen", "check_call", "check_output", "call"}):
            continue
        if any(k.arg == "shell" and not (isinstance(k.value, ast.Constant) and k.value.value is False)
               for k in call.keywords):
            continue  # shell argument semantics are not the direct argv contract
        argv = resolve(call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "args"), None))
        if not isinstance(argv, (ast.List, ast.Tuple)) or not argv.elts:
            continue
        cwd = next((k.value for k in call.keywords if k.arg == "cwd"), None)
        relative_allowed = cwd is None or scan.path(cwd) == ""
        executable = resolve(argv.elts[0])
        direct = script_path(argv.elts[0], relative_allowed=relative_allowed)
        if direct:
            paths.add(direct)
            continue
        python = (isinstance(executable, ast.Attribute) and executable.attr == "executable"
                  and isinstance(executable.value, ast.Name) and executable.value.id == "sys")
        literal = _literal(executable)
        python |= bool(literal and re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", PurePosixPath(literal).name))
        if not python:
            continue
        arguments = iter(argv.elts[1:])
        for argument in arguments:
            option = _literal(resolve(argument))
            if option in {"-c", "-", "--help", "--version", "-V"}:
                break
            if option == "-m":
                module = _literal(resolve(next(arguments, None)))
                module_path = module.replace(".", "/") + ".py" if module else ""
                if relative_allowed and module_path in repo.files:
                    paths.add(module_path)
                break
            if option in {"-W", "-X"}:
                next(arguments, None)
                continue
            if option and option.startswith("-") and option != "--":
                continue
            if option == "--":
                argument = next(arguments, None)
                if argument is None:
                    break
            entrypoint = script_path(argument, relative_allowed=relative_allowed)
            if entrypoint:
                paths.add(entrypoint)
            break
    return paths


def _executed_source_components(repo: Repository, path: str, tree: ast.Module,
                                cache: dict[str, tuple[set[str], set[str]]]) -> set[str]:
    """Follow executed Python entrypoints for source checkouts, never build lanes.

    The compiler's anchored source reads are the same regardless of the invoking
    test's name. Recursively follow explicit Python subprocesses while bounding
    cycles. Dynamic subprocesses and shell programs remain outside this trace.
    """
    required: set[str] = set()
    pending = list(_executed_python_paths(repo, path, tree))
    seen: set[str] = set()
    while pending:
        entrypoint = pending.pop()
        if entrypoint in seen:
            continue
        seen.add(entrypoint)
        if entrypoint not in cache:
            try:
                source_tree = ast.parse((repo.root / entrypoint).read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeError):
                continue
            _, rooted, _, _ = _PythonScan(entrypoint, source_tree).dependencies()
            components = {component for p in rooted if (component := repo.component_of(p))}
            cache[entrypoint] = components, _executed_python_paths(repo, entrypoint, source_tree)
        components, children = cache[entrypoint]
        required.update(components)
        pending.extend(children - seen)
    return required


def _prerequisites(repo: Repository, tests: list[str]) -> tuple[dict[str, bool], list[str]]:
    lanes = dict.fromkeys(LANES, False)
    required: set[str] = set()
    executed_cache: dict[str, tuple[set[str], set[str]]] = {}
    for selector in tests:
        path = selector.split("::", 1)[0]
        try:
            tree = _selected_tree(_definition_tree(repo, selector), selector)
        except SelectionError:
            continue  # parse failure is reported; do not invent heavyweight prerequisites
        source = ast.unparse(tree)
        used, rooted, _, _ = _PythonScan(path, tree).dependencies()
        required.update(_executed_source_components(repo, path, tree, executed_cache))
        # Only anchored paths prove a checkout dependency. Free-text fixture/assertion
        # paths are candidate test-selection evidence, not an instruction to clone.
        for dependency in rooted:
            component = repo.component_of(dependency)
            if component:
                required.add(component)
        for consumer, checkouts in CHECKOUT_CONSUMERS.items():
            if (consumer == selector.split("[", 1)[0]
                    or consumer.startswith(selector + "::")):
                required.update(checkouts)
        node = _executes_node(tree)
        lanes["node"] |= node
        client = any(p.startswith(LIBRECHAT + "/client/dist") for p in rooted)
        packages = any(p.startswith(LIBRECHAT + "/packages/") and "/dist" in p for p in rooted)
        # These Node harnesses require the hardener's compiled workspace packages.
        packages |= node and ("viventium-memory-hardening.js" in source or
                              "seedCallSession" in source)
        dependencies = any(p.startswith(LIBRECHAT + "/node_modules/") for p in rooted)
        lanes["librechat_client"] |= client
        lanes["librechat_packages"] |= packages or client
        lanes["librechat_deps"] |= dependencies or packages or client
        # The playground's env-selectable root is intentionally dynamic. Its TypeScript
        # harness is the confirmed dependency that cannot be resolved by the path scan.
        playground_deps = node and ("TYPESCRIPT" in source or "typescript/lib/typescript.js" in source)
        lanes["playground_deps"] |= playground_deps
        if playground_deps:
            required.add(PLAYGROUND)
        for lane, consumers in LANE_CONSUMERS.items():
            lanes[lane] |= any(c == selector.split("[", 1)[0] or c.startswith(selector + "::")
                               or ("::" not in c and selector.startswith(c + "::")) for c in consumers)
    # A declared build consumer needs the same build chain as a traced one.
    lanes["librechat_packages"] |= lanes["librechat_client"]
    lanes["librechat_deps"] |= lanes["librechat_packages"]
    if lanes["librechat_deps"]:
        required.add(LIBRECHAT)
    lanes["node"] |= lanes["librechat_deps"] or lanes["playground_deps"]
    # Use exact lock names, with no implicit default LibreChat/Health selection.
    names = {json.loads(repo.components[p])["name"] for p in required if p in repo.components}
    return lanes, sorted(names)


def select(repo: Repository, *, scope: str, changed: list[str] | None, components: list[str],
           explicit: list[str] | None = None, reason: str = "", partition: str = "all", live_refs: bool = False) -> Selection:
    if scope not in MODES or partition not in ("all", "core", *PARTITIONS):
        raise SelectionError("unknown QA mode or partition")
    if not isinstance(live_refs, bool):
        raise SelectionError("live_refs must be a boolean")
    explicit = explicit or []
    if scope == "critical-path" and (not explicit or not reason.strip()):
        raise SelectionError("critical-path requires explicit --test selectors and --reason")
    if explicit and scope != "critical-path":
        raise SelectionError("explicit test selectors require critical-path mode")
    if scope == "skip":
        return Selection(scope, False, reason or "QA skipped by explicit request", [],
                         dict.fromkeys(LANES, False), [], [], [], status="NOT RUN", partition=partition)
    tests = sorted(p for p in repo.files if p.startswith(TEST_DIR + "/test_") and p.endswith(".py"))
    unparsed: list[str] = []
    unmapped: list[str] = []
    if scope == "critical-path":
        for selector in explicit:
            _definition_tree(repo, selector)
        selected = list(dict.fromkeys(explicit))
        # Whole-file selections subsume nodes from that same file.
        selected = [s for s in selected if "::" not in s or s.split("::", 1)[0] not in selected]
        status = "explicit selection; NOT RUN by selector"
    elif scope == "full":
        selected = tests
        reason = reason or "full release bank explicitly requested"
        status = "full selection; NOT RUN by selector"
    elif changed is None:
        selected = []
        reason = "diff unavailable; no tests or prerequisites authorized by a guessed blast radius"
        status = "INCOMPLETE"
    else:
        trace = DependencyTrace(repo, extra_known=set(changed))
        selected = []
        mapped: set[str] = set()
        for test in tests:
            dependencies = trace.closure(test)
            if dependencies is None:
                selected.append(test)  # expose the parse error, without claiming coverage
                continue
            own = trace.direct(test) or set()
            hits = [c for c in changed if _depends(dependencies, c)]
            hits += [c for c in components if _depends(own, c)]
            if hits:
                selected.append(test)
                mapped.update(hits)
        unparsed = sorted(trace.unparsed)
        unmapped = sorted(p for p in set(changed) | set(components) if p not in mapped)
        reason = f"{len(selected)} of {len(tests)} release files are static candidates; semantic consumers are not proven"
        status = "INCOMPLETE" if unmapped or unparsed else "candidate selection; NOT RUN by selector"
    other = set().union(*PARTITIONS.values())
    def owned(selector: str) -> bool:
        path = selector.split("::", 1)[0]
        return partition == "all" or (path not in other if partition == "core" else path in PARTITIONS[partition])
    elsewhere = [s for s in selected if not owned(s)]
    selected = [s for s in selected if owned(s)]
    lanes, prerequisites = _prerequisites(repo, selected)
    # The existing public-main pin check stays in the policy job. It is not a
    # prerequisite for unrelated tests, and skip must not execute it.
    live_refs = partition in ("all", "policy") and (live_refs or (bool(selected) and (
        scope == "full" or (scope == "blast-radius" and LOCK_FILE in (changed or [])))))
    return Selection(scope, scope == "full", reason, selected, lanes, changed or [], components,
                     unmapped, prerequisites, unparsed, status, partition, elsewhere, live_refs)


def _fenced_handoff(body: str) -> dict | None:
    blocks = re.findall(r"^```viventium-qa[ \t]*\r?\n(.*?)^```[ \t]*$", body or "", re.M | re.S)
    if len(blocks) > 1:
        raise SelectionError("use exactly one viventium-qa JSON fence")
    if not blocks:
        if re.search(r"^```viventium-qa\b", body or "", re.M):
            raise SelectionError("malformed viventium-qa fence")
        return None
    try:
        result = json.loads(blocks[0])
    except ValueError as exc:
        raise SelectionError("invalid JSON in viventium-qa fence") from exc
    if not isinstance(result, dict) or "mode" not in result or set(result) - {"mode", "tests", "reason", "live_refs"}:
        raise SelectionError("QA handoff accepts only mode, tests, reason, live_refs")
    return result


def _merged_handoff(event: dict) -> dict | None:
    """Recover the merged PR mode rather than broadening skip/critical on push."""
    repository = event.get("repository", {}).get("full_name", "")
    sha = event.get("after", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SelectionError("push handoff requires repository identity and a full commit SHA")
    try:
        result = subprocess.run(["gh", "api", "--paginate", "--slurp",
            f"repos/{repository}/commits/{sha}/pulls?per_page=100"],
            check=True, capture_output=True, text=True, timeout=60)
        pages = json.loads(result.stdout)
        prs = [p for page in pages for p in page if p.get("merged_at") and
               p.get("base", {}).get("ref") == event.get("ref", "").removeprefix("refs/heads/")]
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as exc:
        raise SelectionError("merged PR QA handoff unavailable; no test scope was inferred") from exc
    handoffs = [_fenced_handoff(p.get("body") or "") for p in prs]
    handoffs = [h for h in handoffs if h is not None]
    if len({json.dumps(h, sort_keys=True) for h in handoffs}) > 1:
        raise SelectionError("associated merged PRs have conflicting QA handoffs")
    return handoffs[0] if handoffs else None


def _current_pr_body(event: dict) -> str:
    """On an explicit retry, read current QA metadata for the same source identity.

    GitHub replays the original event payload. A handoff-only edit can therefore
    take effect on Re-run jobs only through this bounded read, not by assuming the
    stored body changed. Reject a moved head or base rather than testing old code
    with a new PR's requested scope.
    """
    repository = event.get("repository", {}).get("full_name", "")
    original = event.get("pull_request", {})
    number = original.get("number", event.get("number"))
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not isinstance(number, int) or isinstance(number, bool) or number <= 0):
        raise SelectionError("PR retry handoff requires repository and PR identity")
    try:
        result = subprocess.run(["gh", "api", f"repos/{repository}/pulls/{number}"],
                                check=True, capture_output=True, text=True, timeout=30)
        current = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SelectionError("current PR QA handoff unavailable; retry did not infer a scope") from exc
    if not isinstance(current, dict):
        raise SelectionError("current PR QA handoff has an invalid response")
    for side in ("head", "base"):
        expected = original.get(side, {}).get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}", expected) or current.get(side, {}).get("sha") != expected:
            raise SelectionError("PR source identity changed; retry requires a new source-event run")
    return current.get("body") or ""


def event_handoff(event: dict, event_name: str, *, refresh_pr: bool = False) -> tuple[dict, bool]:
    """Return the typed handoff and whether an edited event changed that handoff."""
    if event_name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        tests = inputs.get("tests", "")
        try:
            tests = json.loads(tests) if isinstance(tests, str) and tests.strip() else tests or []
        except ValueError as exc:
            raise SelectionError("dispatch tests must be a JSON array of file/node selectors") from exc
        handoff = {"mode": inputs.get("mode", "blast-radius"), "tests": tests,
                   "reason": inputs.get("reason", "")}
        if "live_refs" in inputs:
            value = inputs["live_refs"]
            if value in ("true", "false"):
                value = value == "true"
            if not isinstance(value, bool):
                raise SelectionError("dispatch live_refs must be a boolean")
            handoff["live_refs"] = value
        return handoff, True
    if event_name == "pull_request":
        body = _current_pr_body(event) if refresh_pr else event.get("pull_request", {}).get("body") or ""
        current = _fenced_handoff(body)
        if event.get("action") == "edited":
            raise SelectionError("PR body edits do not replace source-event evidence; use workflow_dispatch with explicit inputs")
        return current or {}, True
    if event_name == "push":
        return (_fenced_handoff(event.get("head_commit", {}).get("message") or "")
                or _merged_handoff(event) or {}), True
    raise SelectionError("unsupported GitHub event for QA selection")


def _write_github_output(path: Path, selection: Selection) -> None:
    lines = [f"scope={selection.scope}", f"full={str(selection.full).lower()}",
             f"count={len(selection.tests)}", f"tests_json={json.dumps(selection.tests)}",
             f"components_json={json.dumps(selection.prerequisites)}",
             f"components_count={len(selection.prerequisites)}",
             f"live_refs={str(selection.live_refs).lower()}",
             *(f"{lane}={str(enabled).lower()}" for lane, enabled in selection.lanes.items())]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _write_summary(path: Path, selection: Selection) -> None:
    lanes = ", ".join(lane for lane, enabled in selection.lanes.items() if enabled) or "none"
    lines = ["### Release test selection", "", f"- Mode `{selection.scope}`: {selection.reason}.",
             f"- Status: {selection.status}. Selected file/node arguments: {len(selection.tests)}.",
             f"- Partition: {selection.partition}. Prerequisites: {lanes}.",
             "- Static selection does not prove semantic coverage or any test result."]
    if selection.elsewhere:
        lines.append(f"- Routed to other pytest workflows: {len(selection.elsewhere)} file/node arguments.")
    for label, values in (("Unmapped (coverage UNKNOWN)", selection.unmapped),
                          ("Unparsed (trace incomplete)", selection.unparsed),
                          ("Selected", selection.tests), ("Component checkouts", selection.prerequisites)):
        if values:
            lines.extend([f"- {label}:", *[f"  - `{value}`" for value in values]])
    if not selection.tests:
        lines.append("- NOT RUN: no pytest invocation and no test prerequisites.")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scope", "--mode", choices=MODES)
    parser.add_argument("--test", action="append", default=[], help="explicit release file or pytest node")
    parser.add_argument("--reason", default="")
    parser.add_argument("--live-refs", action="store_true", default=None,
                        help="explicitly verify public main pins in the policy partition; skip still runs none")
    parser.add_argument("--partition", choices=("all", "core", *PARTITIONS), default="all")
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--base", help="base revision; diff starts at its merge base with --head")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--changed", nargs="*", help="explicit changed paths instead of a git diff")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--pytest-args", action="store_true", help="print JSON argv (never shell words)")
    args = parser.parse_args(argv)
    try:
        handoff: dict = {}
        relevant = True
        event: dict = {}
        if args.event_file:
            event = json.loads(args.event_file.read_text(encoding="utf-8"))
            attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
            handoff, relevant = event_handoff(event, args.event_name,
                refresh_pr=args.event_name == "pull_request" and attempt.isdigit() and int(attempt) > 1)
        scope = args.scope or handoff.get("mode", "blast-radius")
        explicit = args.test or handoff.get("tests", [])
        reason = args.reason or handoff.get("reason", "")
        live_refs = args.live_refs if args.live_refs is not None else handoff.get("live_refs", False)
        if (scope not in MODES or not isinstance(explicit, list) or
                not all(isinstance(t, str) for t in explicit) or not isinstance(reason, str)):
            raise SelectionError("QA handoff requires a valid mode, tests array and reason string")
        # Skip does not even inspect the repository or compute the diff.
        repo = (Repository(args.repo_root.resolve(), frozenset(), frozenset(), {}) if scope == "skip"
                or not relevant else Repository.load(args.repo_root.resolve()))
        changed: list[str] | None = None
        components: list[str] = []
        if scope == "blast-radius" and relevant:
            base = args.base
            if not base and args.event_name == "workflow_dispatch":
                base = event.get("inputs", {}).get("base")
            if not base and args.event_name == "pull_request":
                base = event.get("pull_request", {}).get("base", {}).get("sha")
            if not base and args.event_name == "push":
                base = event.get("before")
            if args.changed is not None:
                changed = sorted({_normalize(p) for p in args.changed} - {ESCAPED, ""})
                if LOCK_FILE in changed:
                    components = sorted(repo.components)  # unknown pin diff is reported conservatively
            elif base:
                try:
                    changed, components = changed_paths(repo.root, base, args.head)
                except SelectionError:
                    pass  # explicit INCOMPLETE, never full
        if not relevant:
            selection = Selection(scope, False, "PR edit did not change the typed QA handoff", [],
                                  dict.fromkeys(LANES, False), [], [], [], status="NOT RUN", partition=args.partition)
        else:
            selection = select(repo, scope=scope, changed=changed, components=components,
                               explicit=explicit, reason=reason, partition=args.partition, live_refs=live_refs)
    except (SelectionError, OSError, ValueError) as exc:
        print(f"QA selection failed: {exc}", file=sys.stderr)
        return 2
    if args.github_output:
        _write_github_output(args.github_output, selection)
        if selection.status == "INCOMPLETE":
            print("::warning title=Incomplete QA selection::Coverage is unknown. Selection success is not a test pass; see the job summary.")
    if args.summary:
        _write_summary(args.summary, selection)
    print(json.dumps(selection.tests) if args.pytest_args else json.dumps(selection.as_dict(), indent=2))
    # A successful selector process is not verification. In CI, an unknown trace
    # must not replace a required check with a green zero-test result.
    return 1 if args.event_file and selection.status == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
