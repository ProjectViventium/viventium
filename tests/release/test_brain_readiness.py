from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BRAIN_READINESS_PATH = REPO_ROOT / "scripts" / "viventium" / "brain_readiness.py"


def load_brain_readiness_module():
    spec = importlib.util.spec_from_file_location("viventium_brain_readiness", BRAIN_READINESS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_registry_covers_express_brain_surfaces_and_public_safety() -> None:
    registry = load_brain_readiness_module()

    expected = {
        "core_app",
        "scheduler",
        "glasshive",
        "prompt_workbench",
        "nightly_reflection",
        "memory_hardening",
        "transcript_ingest",
        "conversation_recall",
        "web_search",
        "primary_ai",
        "secondary_ai",
        "voice",
        "telegram",
        "telegram_codex",
        "google_workspace",
        "ms365",
        "whatsapp",
        "code_interpreter",
        "skyvern",
        "openclaw",
        "remote_access",
    }

    assert expected <= set(registry.FEATURE_BY_KEY)
    for key in expected:
        feature = registry.FEATURE_BY_KEY[key]
        assert feature.qa_owner.startswith("qa/")
        assert feature.public_safety_rule
        assert feature.health_probe


def test_registry_keeps_unshipped_features_out_of_easy_install_default() -> None:
    registry = load_brain_readiness_module()

    assert {"code_interpreter", "skyvern", "remote_access"} <= set(
        registry.ADVANCED_OFF_KEYS
    )
    assert {"whatsapp", "openclaw"} <= set(registry.UNAVAILABLE_KEYS)
    assert registry.CORE_EXPRESS_KEYS == ("core_app",)
    assert registry.GUIDED_EXPRESS_KEYS == ("primary_ai", "secondary_ai")
    assert {
        "scheduler",
        "glasshive",
        "prompt_workbench",
        "nightly_reflection",
        "memory_hardening",
    } <= set(registry.CUSTOM_SETTINGS_ONLY_KEYS)
    assert not set(registry.CORE_EXPRESS_KEYS) & set(registry.CUSTOM_SETTINGS_ONLY_KEYS)
