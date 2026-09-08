from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from test_native_payload_assembler import REPO_ROOT, fixture_inputs, run_assembler


def test_native_assembly_loads_managed_worker_prompts_and_requires_the_loader(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    prompts = {key: {"body": "Compiled " + key, "metadata": {}} for key in (
        "worker.safety_checkpoint", "worker.completion_contract", "worker.native_capability_inventory")}
    (inputs["compiled"] / "prompt-bundle.json").write_text(json.dumps({"prompts": prompts}))
    result = run_assembler(tmp_path, inputs, tmp_path / "candidate")
    assert result.returncode == 0, result.stderr
    root = tmp_path / "candidate/payload"
    # Use the actual worker bootstrap in its installed layout, with its ordinary
    # dependencies. Its ancestor discovery must not reach the source checkout.
    source = REPO_ROOT / "viventium_v0_4/GlassHive/runtime_phase1/src"
    installed_source = root / "runtime/glasshive/src"
    shutil.copytree(source, installed_source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    environment = {"PATH": os.defpath, "HOME": str(tmp_path), "PYTHONPATH": str(installed_source),
        "VIVENTIUM_INSTALL_MODE": "native",
        "VIVENTIUM_PROMPT_BUNDLE_PATH": str(root / "runtime/defaults/prompt-bundle.json")}
    check = subprocess.run([sys.executable, "-B", "-c", "from workers_projects_runtime import bootstrap as b; import json; print(json.dumps([b.GLASSHIVE_SAFETY_CHECKPOINT_RULE, b.GLASSHIVE_WORKER_COMPLETION_CONTRACT, b.GLASSHIVE_NATIVE_CAPABILITY_INVENTORY]))"],
        cwd=tmp_path, env=environment, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert [item.rstrip() for item in json.loads(check.stdout)] == ["Compiled " + key for key in prompts]
    shared = root / "runtime/shared/compiled_prompt_contract.py"
    assert shared.read_bytes() == (REPO_ROOT / "viventium_v0_4/shared/compiled_prompt_contract.py").read_bytes()
    spec = importlib.util.spec_from_file_location("native_closure_runtime", root / "runtime/scripts/native_runtime.py")
    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
    runtime.packaged_health(root)
    shared.unlink()
    try:
        runtime.packaged_health(root)
    except runtime.RuntimeError_ as error:
        assert "runtime/shared/compiled_prompt_contract.py" in str(error)
    else:
        raise AssertionError("missing shared loader passed packaged health")
