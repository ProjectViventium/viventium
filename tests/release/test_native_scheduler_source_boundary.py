"""Only committed scheduler support sources can enter a publisher payload."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def write(path, text="synthetic source\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), "-c", "user.name=Synthetic Builder",
         "-c", "user.email=builder@example.invalid", "-c", "commit.gpgsign=false",
         "-c", "core.hooksPath=/dev/null", *args], text=True,
    ).strip()


@pytest.fixture
def staging(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "scheduler_assembler", ROOT / "scripts/viventium/assemble_native_payload.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "repo"
    component = repo / "viventium_v0_4/LibreChat"
    component.mkdir(parents=True)
    git(component, "init", "-q")
    write(component / ".gitignore", "**/ignored-*\n**/__pycache__/\n**/.venv/\n")
    for relative in (
        "LICENSE", "viventium/source_of_truth/scheduled_failure_contract.v1.json",
        "viventium/source_of_truth/local.viventium-agents.yaml",
        "viventium/source_of_truth/local.librechat.yaml",
        "viventium/source_of_truth/prompts/approved.md",
        "viventium/MCPs/scheduling-cortex/uv.lock",
        "viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py",
        "viventium/MCPs/scheduling-cortex/scheduling_cortex/tests/helper.py",
    ):
        write(component / relative)
    write(component / "viventium/MCPs/scheduling-cortex/pyproject.toml",
          '[project]\nname="synthetic-scheduler"\nversion="0.1.0"\n')
    git(component, "add", ".")
    git(component, "commit", "-qm", "Synthetic fixture")
    pin = git(component, "rev-parse", "HEAD")
    git(repo, "init", "-q")
    write(repo / ".gitignore", "viventium_v0_4/LibreChat/\n**/ignored-*\n**/__pycache__/\n")
    for relative in (
        "LICENSE", "scripts/viventium/prompt_registry.py",
        "viventium_v0_4/shared/compiled_prompt_contract.py",
        "viventium_v0_4/prompt-workbench/backend/prompt_workbench/__init__.py",
    ):
        write(repo / relative)
    write(repo / "components.lock.json", json.dumps({"components": [{"name": "LibreChat", "ref": pin}]}))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Synthetic fixture")

    def dependency_build(args, **kwargs):
        if "--output-file" in args:
            write(Path(args[args.index("--output-file") + 1]), "")
        if "--target" in args:
            Path(args[args.index("--target") + 1]).mkdir()

    monkeypatch.setattr(module, "run_glasshive_build", dependency_build)

    def stage(local=False):
        output = tmp_path / ("local" if local else "publisher")
        result = module.stage_scheduling(repo, Path("python"), Path("uv"), output,
                                         source_date_epoch=1, local_qa_worktree=local)
        return output, result

    return module, repo, component, stage


def test_clean_selected_scheduler_support_is_staged(staging):
    _, _, _, stage = staging
    output, manifest = stage()
    assert manifest["source_kind"] == "component-pin"
    assert (output / "shared/compiled_prompt_contract.py").read_text() == "synthetic source\n"
    assert (output / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/approved.md").is_file()


@pytest.mark.parametrize("scope,relative", [
    ("component", "viventium/MCPs/scheduling-cortex/scheduling_cortex/tests/helper.py"),
    ("component", "viventium/source_of_truth/prompts/approved.md"),
    ("component", "viventium/source_of_truth/prompts/new.md"),
    ("component", "viventium/source_of_truth/prompts/ignored-local.yaml"),
    ("component", "viventium/source_of_truth/local.viventium-agents.yaml"),
    ("component", "viventium/source_of_truth/local.librechat.yaml"),
    ("parent", "scripts/viventium/prompt_registry.py"),
    ("parent", "viventium_v0_4/shared/new.py"),
    ("parent", "viventium_v0_4/shared/ignored-local.py"),
    ("parent", "viventium_v0_4/prompt-workbench/backend/prompt_workbench/__init__.py"),
])
def test_publisher_rejects_changed_or_untracked_support(staging, scope, relative):
    module, repo, component, stage = staging
    write((component if scope == "component" else repo) / relative, "local fixture\n")
    with pytest.raises(module.AssemblyError, match="Scheduling.*source differs"):
        stage()
    assert not (repo.parent / "publisher").exists()
    _, manifest = stage(local=True)
    assert manifest["source_kind"] == "local-qa-worktree"


def test_unpackaged_caches_and_support_tests_do_not_block(staging):
    _, repo, component, stage = staging
    write(repo / "viventium_v0_4/shared/tests/local_test.py")
    write(component / "viventium/source_of_truth/prompts/tests/local.md")
    write(repo / "viventium_v0_4/shared/__pycache__/local.pyc")
    write(component / "viventium/MCPs/scheduling-cortex/scheduling_cortex/__pycache__/local.pyc")
    write(component / "viventium/MCPs/scheduling-cortex/.venv/lib/python/site-packages/local.py")
    output, _ = stage()
    assert not (output / "shared/tests").exists()


@pytest.mark.parametrize("scope,relative", [
    ("parent", "viventium_v0_4/shared/compiled_prompt_contract.py"),
    ("component", "viventium/source_of_truth/prompts/approved.md"),
])
def test_publisher_rejects_staged_support_deletions(staging, scope, relative):
    module, repo, component, stage = staging
    git(component if scope == "component" else repo, "rm", "--", relative)
    with pytest.raises(module.AssemblyError, match="Scheduling.*source differs"):
        stage()
    assert not (repo.parent / "publisher").exists()
