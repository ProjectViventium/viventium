from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
GPT_56_MODELS = {"gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}
CONNECTED_ACCOUNT_GPT_56_MODELS = {"gpt-5.6-sol", "gpt-5.6-terra"}


def _shell_csv_constant(source: str, name: str) -> list[str]:
    match = re.search(rf'^{re.escape(name)}="([^"]*)"$', source, flags=re.MULTILINE)
    assert match is not None, f"Missing shell constant: {name}"
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def test_direct_openai_model_inventories_expose_the_full_gpt_56_family() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    for name in (
        "DEFAULT_VIVENTIUM_OPENAI_MODELS",
        "DEFAULT_VIVENTIUM_ASSISTANTS_MODELS",
    ):
        assert GPT_56_MODELS <= set(_shell_csv_constant(source, name))


def test_connected_account_inventory_exposes_only_verified_gpt_56_models() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    for name in (
        "CONNECTED_ACCOUNT_VIVENTIUM_OPENAI_MODELS",
        "CONNECTED_ACCOUNT_VIVENTIUM_ASSISTANTS_MODELS",
    ):
        models = _shell_csv_constant(source, name)
        assert models[0] == "gpt-5.6-sol"
        assert set(models) & GPT_56_MODELS == CONNECTED_ACCOUNT_GPT_56_MODELS


def test_gpt_56_pro_is_not_invented_as_a_model_slug() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    for name in (
        "DEFAULT_VIVENTIUM_OPENAI_MODELS",
        "DEFAULT_VIVENTIUM_ASSISTANTS_MODELS",
        "CONNECTED_ACCOUNT_VIVENTIUM_OPENAI_MODELS",
        "CONNECTED_ACCOUNT_VIVENTIUM_ASSISTANTS_MODELS",
    ):
        assert "gpt-5.6-pro" not in set(_shell_csv_constant(source, name))
