from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "viventium"))

import select_release_tests as selection  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
         "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _lock(ref: str) -> str:
    return json.dumps({"components": [
        {"name": "Comp", "path": "viventium_v0_4/Comp", "ref": ref},
        {"name": "LibreChat", "path": "viventium_v0_4/LibreChat", "ref": "a" * 40},
    ]})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    files = {
        "components.lock.json": _lock("1" * 40),
        "scripts/viventium/alpha.py": (
            "from pathlib import Path\nimport beta\n"
            "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
            "TEMPLATE = REPO_ROOT / 'templates' / 'alpha.yaml'\n"
            "def load():\n    return TEMPLATE.read_text()\n"
        ),
        "scripts/viventium/beta.py": "VALUE = 1\n",
        # Production code that only locates a component is not a consumer of the component pin.
        "scripts/viventium/locator.py": "COMPONENT = 'viventium_v0_4/Comp'\n",
        "templates/alpha.yaml": "a: 1\n",
        "docs/guide.md": "# Guide\n",
        "config.example.yaml": "x: 1\n",
        "tests/release/test_alpha.py": (
            "import sys\nfrom pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parents[2]\n"
            "sys.path.insert(0, str(ROOT / 'scripts' / 'viventium'))\n"
            "import alpha\nimport locator\n"
            "def test_alpha():\n    assert alpha.load()\n"
        ),
        "tests/release/test_docs.py": (
            "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n"
            "def test_docs():\n    assert (ROOT / 'docs' / 'guide.md').read_text()\n"
        ),
        "tests/release/test_component.py": (
            "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n"
            "COMP = ROOT / 'viventium_v0_4' / 'Comp'\n"
            "def test_component():\n    assert (COMP / 'runtime' / 'main.py').exists() or True\n"
        ),
        "tests/release/test_dynamic_reader.py": (
            "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n"
            "COMP = ROOT / 'viventium_v0_4' / 'Comp'\n"
            "def _read(relative):\n    return (COMP / relative).read_text()\n"
            "def test_reads_component_files():\n    assert _read\n"
        ),
        "tests/release/test_configs.py": (
            "from pathlib import Path\nREPO_ROOT = Path(__file__).resolve().parents[2]\n"
            "def test_configs():\n    assert list(REPO_ROOT.glob('config*.yaml'))\n"
        ),
        "tests/release/test_artifacts.py": (
            "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n"
            "LIBRECHAT = ROOT / 'viventium_v0_4' / 'LibreChat'\n"
            "def test_built_client():\n    assert (LIBRECHAT / 'client' / 'dist' / 'index.html').name\n"
        ),
        "tests/release/test_shared_fixtures.py": "def build():\n    return 1\n\ndef test_build():\n    assert build()\n",
        "tests/release/test_fixture_consumer.py": (
            "import importlib.util\nfrom pathlib import Path\n"
            "FIXTURES = Path(__file__).with_name('test_shared_fixtures.py')\n"
            "def test_reuses_fixtures():\n"
            "    assert importlib.util.spec_from_file_location('fixtures', FIXTURES)\n"
        ),
        "tests/release/test_workflow_text.py": (
            "def test_workflow_text():\n"
            "    assert 'npm run build:client' and 'viventium_v0_4/LibreChat/client/dist/'\n"
        ),
    }
    for relative, text in files.items():
        _write(root, relative, text)
    _commit(root, "base")
    return root


def _select(repo: Path, base: str | None = None, *, changed: list[str] | None = None, scope: str = "blast-radius"):
    loaded = selection.Repository.load(repo)
    components: list[str] = []
    if changed is None and base is not None:
        changed, components = selection.changed_paths(repo, base, "HEAD")
    return selection.select(loaded, scope=scope, changed=changed, components=components)


def _names(result) -> set[str]:
    return {Path(test).stem for test in result.tests}


def test_module_changes_select_importers_through_the_import_graph(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "scripts/viventium/beta.py", "VALUE = 2\n")
    _commit(repo, "beta")

    result = _select(repo, base)

    assert not result.full
    assert _names(result) == {"test_alpha"}
    assert result.unmapped == []


def test_files_a_module_reads_select_the_tests_that_use_that_module(repo: Path) -> None:
    result = _select(repo, changed=["templates/alpha.yaml"])

    assert _names(result) == {"test_alpha"}


def test_docs_changes_select_only_tests_that_read_them(repo: Path) -> None:
    result = _select(repo, changed=["docs/guide.md"])

    assert _names(result) == {"test_docs"}


def test_tests_that_load_sibling_test_files_are_selected_with_them(repo: Path) -> None:
    result = _select(repo, changed=["tests/release/test_shared_fixtures.py"])

    assert _names(result) == {"test_shared_fixtures", "test_fixture_consumer"}


def test_component_pin_selects_direct_readers_not_modules_that_locate_it(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "components.lock.json", _lock("2" * 40))
    _commit(repo, "pin")

    result = _select(repo, base)

    assert result.components == ["viventium_v0_4/Comp"]
    assert _names(result) == {"test_component", "test_dynamic_reader"}
    assert not any(result.lanes.values())
    assert result.prerequisites == ["Comp"]


def test_constant_globs_match_only_the_files_they_can_list(repo: Path) -> None:
    assert _names(_select(repo, changed=["config.local.yaml"])) == {"test_configs"}
    assert _names(_select(repo, changed=["configs/nested.yaml"])) == set()


def test_lanes_follow_real_artifact_paths_not_assertion_text(repo: Path) -> None:
    result = _select(repo, changed=["tests/release/test_workflow_text.py"])
    assert _names(result) == {"test_workflow_text"}
    assert result.lanes["librechat_client"] is False

    result = _select(repo, changed=["tests/release/test_artifacts.py"])
    assert _names(result) == {"test_artifacts"}
    assert result.lanes["librechat_client"] is True


def test_shared_inputs_and_missing_diff_never_authorize_full_scope(repo: Path) -> None:
    shared = _select(repo, changed=[".github/workflows/config-compile.yml", "docs/guide.md"])
    assert not shared.full
    assert _names(shared) == {"test_docs"}
    assert shared.unmapped == [".github/workflows/config-compile.yml"]
    unknown = _select(repo, changed=None)
    assert not unknown.full and unknown.tests == []
    assert unknown.status == "INCOMPLETE"
    assert not any(unknown.lanes.values()) and unknown.prerequisites == []
    requested = _select(repo, changed=["docs/guide.md"], scope="full")
    assert requested.full
    assert _names(requested) == {path.stem for path in (repo / "tests" / "release").glob("test_*.py")}
    assert requested.lanes["librechat_client"]
    assert not requested.lanes["audio_tools"]  # full does not invent prerequisites


def test_deleted_modules_still_select_their_importers(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "scripts" / "viventium" / "beta.py").unlink()
    _commit(repo, "remove beta")

    assert _names(_select(repo, base)) == {"test_alpha"}


def test_unparsable_tests_are_always_selected_and_unmapped_changes_are_reported(repo: Path) -> None:
    _write(repo, "tests/release/test_broken.py", "def test_broken(:\n")
    _commit(repo, "broken")

    result = _select(repo, changed=["notes/unrelated.txt"])

    assert _names(result) == {"test_broken"}
    assert result.unmapped == ["notes/unrelated.txt"]
    assert result.unparsed == ["tests/release/test_broken.py"]
    assert result.status == "INCOMPLETE"


def test_github_outputs_and_summary_state_what_was_not_run(repo: Path, tmp_path: Path) -> None:
    outputs = tmp_path / "outputs.txt"
    summary = tmp_path / "summary.md"

    selection.main([
        "--repo-root", str(repo), "--changed", "docs/guide.md", "notes/unrelated.txt",
        "--github-output", str(outputs), "--summary", str(summary),
    ])

    values = dict(line.split("=", 1) for line in outputs.read_text().splitlines())
    assert values["scope"] == "blast-radius"
    assert values["full"] == "false"
    assert values["count"] == "1"
    assert json.loads(values["tests_json"]) == ["tests/release/test_docs.py"]
    assert values["librechat_client"] == "false"
    assert "Unmapped (coverage UNKNOWN)" in summary.read_text()
    assert "notes/unrelated.txt" in summary.read_text()
    assert "scheduled" not in summary.read_text()


def test_repository_bank_traces_without_errors_and_stays_narrow_for_a_docs_change() -> None:
    loaded = selection.Repository.load(ROOT)
    result = selection.select(loaded, scope="blast-radius", changed=["docs/README.md"], components=[])

    assert not result.full
    assert 0 < len(result.tests) < len([p for p in loaded.files if p.startswith("tests/release/test_")])
    assert "tests/release/test_qa_operating_contract.py" in result.tests


def test_declared_lane_consumers_are_existing_release_tests() -> None:
    for lane, consumers in selection.LANE_CONSUMERS.items():
        assert lane in selection.LANES
        for test in consumers:
            assert (ROOT / test.split("::", 1)[0]).is_file(), f"{lane}: {test} does not exist"


def test_runtime_prerequisites_follow_declared_consumers_on_the_real_bank() -> None:
    loaded = selection.Repository.load(ROOT)
    result = selection.select(
        loaded,
        scope="blast-radius",
        changed=["tests/release/test_voice_playground_dispatch_contract.py"],
        components=[],
    )

    assert "tests/release/test_voice_playground_dispatch_contract.py" in result.tests
    assert not result.lanes["librechat_client"]
    assert "LibreChat" in result.prerequisites
    for lane in ("librechat_packages", "playground_deps", "audio_tools"):
        assert result.lanes[lane], lane


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "scripts/viventium/select_release_tests.py"),
                           "--repo-root", str(repo), *args], capture_output=True, text=True, check=False)


def test_skip_does_no_repository_diff_or_prerequisite_work(tmp_path: Path) -> None:
    result = _cli(tmp_path / "not-a-repository", "--scope", "skip")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["tests"] == receipt["prerequisites"] == []
    assert receipt["status"] == "NOT RUN"
    assert not any(receipt["lanes"].values())


def test_critical_path_keeps_exact_node_and_reason_without_diff(repo: Path) -> None:
    node = "tests/release/test_docs.py::test_docs"
    result = _cli(repo, "--scope", "critical-path", "--test", node, "--reason", "Changed doc reader")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["tests"] == [node]
    assert receipt["reason"] == "Changed doc reader"
    assert not receipt["full"] and not any(receipt["lanes"].values())


@pytest.mark.parametrize("args", [
    ["--scope", "critical-path"],
    ["--scope", "critical-path", "--test", "tests/release/test_docs.py"],
    ["--scope", "critical-path", "--reason", "No selection"],
    ["--scope", "full", "--test", "tests/release/test_docs.py"],
])
def test_invalid_mode_selection_combinations_fail_before_outputs(repo: Path, tmp_path: Path, args: list[str]) -> None:
    output = tmp_path / "outputs"
    result = _cli(repo, *args, "--github-output", str(output))
    assert result.returncode == 2
    assert not output.exists()


@pytest.mark.parametrize("selector", [
    "tests/release/test_docs.py::test_missing", "tests/release/test_docs.py::test_docs::nested",
    "tests/release/test_missing.py", "tests/release/../../scripts/viventium/alpha.py",
    "/tests/release/test_docs.py", "./tests/release/test_docs.py", "--help",
    "tests/release/test_docs.py\n--collect-only", "tests/release/test_docs.py::test_docs[broken",
])
def test_critical_path_rejects_missing_or_unsafe_selectors(repo: Path, selector: str) -> None:
    result = _cli(repo, "--scope", "critical-path", "--test=" + selector, "--reason", "Contract")
    assert result.returncode == 2, result.stdout


def test_parameter_ids_stay_literal_json_arguments(repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    node = "tests/release/test_docs.py::test_docs[with spaces;$(not-a-command)]"
    result = _cli(repo, "--scope", "critical-path", "--test", node, "--reason", "Parameter",
                  "--github-output", str(output))
    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert json.loads(values["tests_json"]) == [node]
    # Parameter existence remains pytest's gate; source validation never executes a decorator.


def test_cli_missing_diff_stays_empty_incomplete(repo: Path) -> None:
    result = _cli(repo, "--base", "missing-revision")
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "INCOMPLETE" and receipt["count"] == 0
    assert not receipt["full"]


def test_partitions_are_disjoint_and_preserve_the_total_selection(repo: Path) -> None:
    for files in selection.PARTITIONS.values():
        for path in files:
            _write(repo, path, "def test_owned():\n    assert True\n")
    _commit(repo, "owned suites")
    loaded = selection.Repository.load(repo)
    all_tests = set(selection.select(loaded, scope="full", changed=None, components=[]).tests)
    groups = [selection.select(loaded, scope="full", changed=None, components=[], partition=p)
              for p in ("core", "policy", "activation")]
    assert set().union(*(set(g.tests) for g in groups)) == all_tests
    assert sum(len(g.tests) for g in groups) == len(all_tests)
    node = "tests/release/test_qa_storage_guard.py::test_owned"
    for partition in ("core", "policy", "activation"):
        chosen = selection.select(loaded, scope="critical-path", changed=None, components=[],
            explicit=[node], reason="Storage guard", partition=partition)
        assert chosen.tests == ([node] if partition == "policy" else [])
        if partition != "policy":
            assert chosen.prerequisites == [] and not any(chosen.lanes.values())


def test_component_pin_does_not_request_client_or_package_build(repo: Path) -> None:
    _write(repo, "tests/release/test_lc_source.py", "from pathlib import Path\nROOT=Path(__file__).parents[2]\ndef test_source():\n    assert (ROOT / 'viventium_v0_4/LibreChat/source.js').exists()\n")
    _commit(repo, "source consumer")
    result = selection.select(selection.Repository.load(repo), scope="blast-radius", changed=[], components=[selection.LIBRECHAT])
    # This repo also has a client-dist consumer, which legitimately needs the build.
    assert "tests/release/test_lc_source.py" in result.tests
    bounded = selection.select(selection.Repository.load(repo), scope="critical-path", changed=None,
        components=[selection.LIBRECHAT], explicit=["tests/release/test_lc_source.py"], reason="Source contract")
    assert bounded.prerequisites == ["LibreChat"]
    assert not bounded.lanes["librechat_packages"] and not bounded.lanes["librechat_client"]


def test_mock_audio_mentions_do_not_install_real_ffmpeg(repo: Path) -> None:
    _write(repo, "tests/release/test_mock_audio.py", "def test_audio():\n    command = ['ffmpeg', 'ffprobe']\n    assert command\n")
    _commit(repo, "mock")
    result = _select(repo, changed=["tests/release/test_mock_audio.py"])
    assert not result.lanes["audio_tools"]
    assert "telegram_suite" not in result.lanes


def test_critical_node_does_not_inherit_sibling_audio_prerequisites() -> None:
    repo = selection.Repository.load(ROOT)
    node = "tests/release/test_voice_playground_dispatch_contract.py::test_shared_voice_capability_contracts_match_librechat_mirrors"
    result = selection.select(repo, scope="critical-path", changed=None, components=[], explicit=[node], reason="Source parity")
    assert result.prerequisites == ["LibreChat"]
    assert not any(result.lanes.values())
    audio = next(c for c in selection.LANE_CONSUMERS["audio_tools"] if "remote_audio" in c)
    result = selection.select(repo, scope="critical-path", changed=None, components=[], explicit=[audio], reason="Audio conversion")
    assert result.lanes["audio_tools"] and result.lanes["node"]
    assert not result.lanes["librechat_client"]


def _fence(mode: str, tests: list[str] | None = None, reason: str = "") -> str:
    return "```viventium-qa\n" + json.dumps({"mode": mode, "tests": tests or [], "reason": reason}) + "\n```"


@pytest.mark.parametrize("mode", selection.MODES)
def test_pr_and_dispatch_use_the_same_typed_mode(mode: str) -> None:
    tests = ["tests/release/test_docs.py::test_docs"] if mode == "critical-path" else []
    expected = {"mode": mode, "tests": tests, "reason": "Bounded change"}
    pr, relevant = selection.event_handoff({"pull_request": {"body": _fence(mode, tests, expected["reason"])}}, "pull_request")
    dispatch, _ = selection.event_handoff({"inputs": {**expected, "tests": json.dumps(tests)}}, "workflow_dispatch")
    assert pr == dispatch == expected and relevant


def test_pr_body_edits_cannot_emit_replacement_success() -> None:
    event = {"action": "edited", "pull_request": {"body": _fence("skip")}}
    with pytest.raises(selection.SelectionError, match="do not replace source-event evidence"):
        selection.event_handoff(event, "pull_request")


@pytest.mark.parametrize("body", ["```viventium-qa\n{broken}\n```", "```viventium-qa\n{}",
                                    _fence("skip") + "\n" + _fence("full")])
def test_invalid_fences_fail_closed(body: str) -> None:
    with pytest.raises(selection.SelectionError):
        selection.event_handoff({"pull_request": {"body": body}}, "pull_request")


def test_push_recovers_merged_pr_critical_handoff_without_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {"mode": "critical-path", "tests": ["tests/release/test_docs.py"], "reason": "Contract"}
    calls = []
    def gh(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps([[{"merged_at": "synthetic", "base": {"ref": "main"},
            "body": _fence(**expected)}]]), "")
    monkeypatch.setattr(selection.subprocess, "run", gh)
    event = {"repository": {"full_name": "example/repo"}, "after": "a" * 40, "ref": "refs/heads/main"}
    actual, relevant = selection.event_handoff(event, "push")
    assert actual == expected and relevant
    assert calls[0][0][:4] == ["gh", "api", "--paginate", "--slurp"]
    assert not calls[0][1].get("shell") and calls[0][1]["timeout"] <= 60
    event["head_commit"] = {"message": _fence("skip")}
    assert selection.event_handoff(event, "push")[0]["mode"] == "skip"
    assert len(calls) == 1


def test_push_handoff_lookup_failure_does_not_default_to_blast(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args, **kwargs):
        raise OSError("No API")
    monkeypatch.setattr(selection.subprocess, "run", unavailable)
    event = {"repository": {"full_name": "example/repo"}, "after": "a" * 40, "ref": "refs/heads/main"}
    with pytest.raises(selection.SelectionError, match="no test scope was inferred"):
        selection.event_handoff(event, "push")


def test_critical_source_node_does_not_authorize_all_remote_component_probes() -> None:
    repo = selection.Repository.load(ROOT)
    node = "tests/release/test_public_bootstrap_manifests.py::test_public_component_manifest_uses_projectviventium_origins"
    critical = selection.select(repo, scope="critical-path", explicit=[node], reason="Source manifest",
                                changed=None, components=[], partition="policy")
    assert not critical.live_refs
    assert not critical.prerequisites
    full = selection.select(repo, scope="full", changed=None, components=[], partition="policy")
    assert full.live_refs
    blast = selection.select(repo, scope="blast-radius", changed=["components.lock.json"],
                             components=[], partition="policy")
    assert blast.live_refs


def test_compiler_wizard_node_gets_only_confirmed_source_prerequisites() -> None:
    node = "tests/release/test_config_compiler.py::test_public_minimal_example_compiles_without_preexisting_keychain_state"
    repo = selection.Repository.load(ROOT)
    result = selection.select(repo, scope="critical-path", changed=None, components=[],
                              explicit=[node], reason="Wizard compiler replay")
    assert result.prerequisites == ["LibreChat", "xPerfect"]
    assert not any(result.lanes.values())


def test_manual_blast_uses_explicit_base(repo: Path, tmp_path: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "docs/guide.md", "Changed guide")
    _commit(repo, "guide")
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"mode": "blast-radius", "base": base}}))
    result = _cli(repo, "--event-file", str(event), "--event-name", "workflow_dispatch")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["tests"] == ["tests/release/test_docs.py"]
    assert receipt["full"] is False


def test_ci_incomplete_diff_writes_receipt_and_cannot_pass(repo: Path, tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"mode": "blast-radius", "base": "missing-ref"}}))
    summary, output = tmp_path / "summary.md", tmp_path / "outputs.txt"
    result = _cli(repo, "--event-file", str(event), "--event-name", "workflow_dispatch",
                  "--github-output", str(output), "--summary", str(summary))
    assert result.returncode == 1
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert values["count"] == "0" and values["components_count"] == "0"
    assert "INCOMPLETE" in summary.read_text() and "NOT RUN" in summary.read_text()
    assert "not a test pass" in result.stdout


def test_selector_suite_needs_no_node_despite_its_node_assertions() -> None:
    result = selection.select(selection.Repository.load(ROOT), scope="critical-path", changed=None,
        components=[], explicit=["tests/release/test_release_test_selection.py"], reason="Selector regression")
    assert not any(result.lanes.values()) and result.prerequisites == []


@pytest.mark.parametrize(("source", "expected"), [
    ("def test_text():\n    assert 'node'\n", False),
    ("import shutil\ndef test_probe():\n    assert shutil.which('node')\n", False),
    ("import subprocess\ndef test_run():\n    subprocess.run(['node', '-e', '1'])\n", True),
    ("import subprocess, shutil\ndef test_run():\n    node = shutil.which('node')\n    subprocess.run([node, '-e', '1'])\n", True),
])
def test_node_setup_requires_executable_evidence(repo: Path, source: str, expected: bool) -> None:
    _write(repo, "tests/release/test_node_evidence.py", source)
    result = _select(repo, changed=["tests/release/test_node_evidence.py"])
    assert result.lanes["node"] is expected


def test_librechat_typescript_dependency_does_not_build_packages_or_client(repo: Path) -> None:
    _write(repo, "tests/release/test_typescript.py", "from pathlib import Path\nROOT=Path(__file__).parents[2]\ndef test_ts():\n    assert (ROOT / 'viventium_v0_4/LibreChat/node_modules/typescript/lib/typescript.js').exists()\n")
    result = _select(repo, changed=["tests/release/test_typescript.py"])
    assert result.prerequisites == ["LibreChat"]
    assert result.lanes["librechat_deps"] and result.lanes["node"]
    assert not result.lanes["librechat_packages"] and not result.lanes["librechat_client"]


@pytest.mark.parametrize("moved", [None, "head", "base"])
def test_explicit_pr_retry_reads_current_handoff_only_for_same_source(monkeypatch: pytest.MonkeyPatch, moved: str | None) -> None:
    original = {"number": 42, "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40}, "body": _fence("blast-radius")}
    current = {**original, "body": _fence("critical-path", ["tests/release/test_docs.py"], "Reader repair")}
    if moved:
        current[moved] = {"sha": "c" * 40}
    calls = []
    def gh(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps(current), "")
    monkeypatch.setattr(selection.subprocess, "run", gh)
    event = {"repository": {"full_name": "example/repo"}, "pull_request": original, "action": "synchronize"}
    # Normal source events consume their original payload without an API request.
    assert selection.event_handoff(event, "pull_request")[0]["mode"] == "blast-radius"
    assert not calls
    if moved:
        with pytest.raises(selection.SelectionError, match="source identity changed"):
            selection.event_handoff(event, "pull_request", refresh_pr=True)
    else:
        handoff, _ = selection.event_handoff(event, "pull_request", refresh_pr=True)
        assert handoff["mode"] == "critical-path" and handoff["reason"] == "Reader repair"
    assert calls[0][0] == ["gh", "api", "repos/example/repo/pulls/42"]
    assert calls[0][1]["timeout"] == 30 and not calls[0][1].get("shell")


def test_pr_retry_handoff_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def outage(*args, **kwargs):
        raise OSError("No API")
    monkeypatch.setattr(selection.subprocess, "run", outage)
    event = {"repository": {"full_name": "example/repo"}, "number": 42, "pull_request": {}}
    with pytest.raises(selection.SelectionError, match="retry did not infer a scope"):
        selection.event_handoff(event, "pull_request", refresh_pr=True)


@pytest.mark.parametrize("invocation", [
    "subprocess.run([sys.executable, str(ROOT / 'scripts/viventium/runner.py')])",
    "subprocess.run([sys.executable, ROOT / 'scripts' / 'viventium' / 'runner.py'])",
    "script = ROOT / 'scripts/viventium/runner.py'; argv = [sys.executable, str(script)]; subprocess.run(args=argv)",
    "subprocess.run([sys.executable, '-B', str(ROOT.joinpath('scripts', 'viventium', 'runner.py'))])",
    "subprocess.run(['python3', 'scripts/viventium/runner.py'], cwd=ROOT)",
    "subprocess.run([sys.executable, '-m', 'scripts.viventium.runner'])",
    "subprocess.run([str(ROOT / 'scripts/viventium/runner.py')])",
])
def test_executed_python_script_traces_component_sources_without_test_name_rules(repo: Path, invocation: str) -> None:
    _write(repo, "scripts/viventium/runner.py", "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\nassert (ROOT / 'viventium_v0_4/LibreChat/source.yaml').read_text()\nassert (ROOT / 'viventium_v0_4/Comp/source.yaml').read_text()\n")
    _write(repo, "tests/release/test_entrypoint.py", "import subprocess, sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\ndef test_arbitrary_name():\n    " + invocation + "\n")
    result = selection.select(selection.Repository.load(repo), scope="critical-path", changed=None,
        components=[], explicit=["tests/release/test_entrypoint.py::test_arbitrary_name"], reason="Executable source consumer")
    assert result.prerequisites == ["Comp", "LibreChat"]
    assert not any(result.lanes.values())


@pytest.mark.parametrize("invocation", [
    "assert str(ROOT / 'scripts/viventium/runner.py')",
    "subprocess.run(['cat', str(ROOT / 'scripts/viventium/runner.py')])",
    "subprocess.run([sys.executable, '-c', 'pass', str(ROOT / 'scripts/viventium/runner.py')])",
])
def test_reading_or_mentioning_a_script_does_not_inherit_its_execution_prerequisites(repo: Path, invocation: str) -> None:
    _write(repo, "scripts/viventium/runner.py", "from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\nassert (ROOT / 'viventium_v0_4/LibreChat/source.yaml').read_text()\n")
    _write(repo, "tests/release/test_entrypoint.py", "import subprocess, sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\ndef test_source():\n    " + invocation + "\ndef test_unselected_execution():\n    subprocess.run([sys.executable, str(ROOT / 'scripts/viventium/runner.py')])\n")
    result = selection.select(selection.Repository.load(repo), scope="critical-path", changed=None,
        components=[], explicit=["tests/release/test_entrypoint.py::test_source"], reason="Source inspection only")
    assert result.prerequisites == []
    assert not any(result.lanes.values())


def test_repaired_keychain_compiler_node_selects_its_runtime_source_checkouts() -> None:
    node = "tests/release/test_config_compiler.py::test_config_compiler_easy_install_defaults_to_browser_api_key_not_direct_subscription_oauth"
    result = selection.select(selection.Repository.load(ROOT), scope="critical-path", changed=None,
        components=[], explicit=[node], reason="Compiler credential regression")
    assert result.prerequisites == ["LibreChat", "xPerfect"]
    assert not any(result.lanes.values())


def test_instruction_architecture_remains_in_policy_with_its_two_source_checkouts() -> None:
    node = "tests/release/test_qa_operating_contract.py::test_agent_instruction_architecture_is_lean_imported_and_reachable"
    repo = selection.Repository.load(ROOT)
    for partition in ("core", "policy", "activation"):
        result = selection.select(repo, scope="critical-path", changed=None, components=[],
                                  explicit=[node], reason="Instruction sources", partition=partition)
        assert result.tests == ([node] if partition == "policy" else [])
        assert result.prerequisites == (["LibreChat", "xPerfect"] if partition == "policy" else [])
        assert not any(result.lanes.values())


@pytest.mark.parametrize("selector", [
    "tests/release/test_qa_operating_contract.py",
    "tests/release/test_qa_operating_contract.py::test_current_requirement_and_qa_local_markdown_evidence_links_resolve",
])
def test_markdown_link_consumer_gets_only_source_checkouts(selector: str) -> None:
    result = selection.select(selection.Repository.load(ROOT), scope="critical-path",
                              changed=None, components=[], explicit=[selector], reason="Resolve current doc links")
    assert result.prerequisites == ["LibreChat", "Viventium-Health", "xPerfect"]
    assert not any(result.lanes.values())


def test_other_qa_node_does_not_inherit_markdown_checkout_dependency() -> None:
    node = "tests/release/test_qa_operating_contract.py::test_agent_instruction_architecture_is_lean_imported_and_reachable"
    result = selection.select(selection.Repository.load(ROOT), scope="critical-path",
                              changed=None, components=[], explicit=[node], reason="Instruction import contract")
    assert "Viventium-Health" not in result.prerequisites


@pytest.mark.parametrize("partition,expected", [("all", True), ("policy", True), ("core", False), ("activation", False)])
def test_explicit_public_pin_check_does_not_widen_critical_scope(partition: str, expected: bool) -> None:
    node = "tests/release/test_public_bootstrap_manifests.py::test_components_lock_uses_full_commit_shas_for_public_components"
    result = selection.select(selection.Repository.load(ROOT), scope="critical-path", changed=None,
                              components=[], explicit=[node], reason="Publish a component pin",
                              partition=partition, live_refs=True)
    assert result.live_refs is expected
    assert result.tests == ([node] if expected else [])
    assert not result.prerequisites and not any(result.lanes.values())


def test_skip_still_waives_explicit_public_pin_check(repo: Path) -> None:
    result = _cli(repo, "--scope", "skip", "--live-refs")
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "NOT RUN" and not receipt["live_refs"]
    assert not receipt["tests"] and not receipt["prerequisites"]


@pytest.mark.parametrize("value", ["true", 1, None, []])
def test_public_pin_handoff_rejects_nonboolean(value) -> None:
    with pytest.raises(selection.SelectionError, match="live_refs must be a boolean"):
        selection.select(selection.Repository.load(ROOT), scope="skip", changed=None,
                         components=[], live_refs=value)


def test_public_pin_request_survives_pr_and_dispatch_handoffs(repo: Path, tmp_path: Path) -> None:
    handoff = {"mode": "critical-path", "tests": ["tests/release/test_docs.py::test_docs"],
               "reason": "Component publication", "live_refs": True}
    body = "```viventium-qa\n" + json.dumps(handoff) + "\n```"
    event = {"pull_request": {"body": body}}
    parsed, _ = selection.event_handoff(event, "pull_request")
    dispatch, _ = selection.event_handoff({"inputs": {**handoff, "tests": json.dumps(handoff["tests"]),
                                                    "live_refs": "true"}}, "workflow_dispatch")
    assert parsed == dispatch == handoff
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    run = _cli(repo, "--event-file", str(event_path), "--event-name", "pull_request")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["live_refs"] and result["tests"] == handoff["tests"]
