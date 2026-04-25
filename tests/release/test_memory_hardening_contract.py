from __future__ import annotations

import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_COMPILER_SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler",
    ROOT / "scripts/viventium/config_compiler.py",
)
assert CONFIG_COMPILER_SPEC and CONFIG_COMPILER_SPEC.loader
config_compiler = importlib.util.module_from_spec(CONFIG_COMPILER_SPEC)
CONFIG_COMPILER_SPEC.loader.exec_module(config_compiler)


def test_memory_hardening_defaults_are_launch_ready_and_opt_in() -> None:
    settings = config_compiler.resolve_memory_hardening_settings({})

    assert settings["enabled"] is False
    assert settings["schedule"] == "0 5 * * *"
    assert settings["lookback_days"] == 7
    assert settings["min_user_idle_minutes"] == 60
    assert settings["max_changes_per_user"] == 3
    assert settings["max_input_chars"] == 500000
    assert settings["require_full_lookback"] is True
    assert settings["provider_profile"] == "launch_ready_only"
    assert settings["anthropic_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["anthropic"]
    assert settings["openai_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["openai"]


def test_memory_hardening_public_audit_contract_has_no_raw_path_field() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    text = script.read_text(encoding="utf-8")

    assert "raw_proposal_path" not in text
    assert "private_proposal_file" in text
    assert re.search(r"proposal\.private\.json", text)
    assert re.search(r"rollback\.private\.json", text)


def test_memory_hardening_docs_keep_private_artifacts_out_of_public_qa() -> None:
    boundary_doc = ROOT / "docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md"
    qa_readme = ROOT / "qa/memory-hardening/README.md"

    boundary_text = boundary_doc.read_text(encoding="utf-8")
    qa_text = qa_readme.read_text(encoding="utf-8")

    assert "proposal.private.json" in boundary_text
    assert "rollback.private.json" in boundary_text
    assert "Raw proposals and rollback snapshots stay under local App Support state" in qa_text
