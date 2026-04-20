from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SOURCE_OF_TRUTH_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "local.viventium-agents.yaml"
)
SOURCE_OF_TRUTH_LIBRECHAT_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "local.librechat.yaml"
)
CATALOG_PATH = ROOT / "qa" / "background_agents" / "01_catalog.md"
COVERAGE_MATRIX_PATH = ROOT / "qa" / "background_agents" / "05_coverage_matrix.md"
SIGNOFF_MANIFEST_PATH = ROOT / "qa" / "background_agents" / "06_agent_signoff_manifest.md"
PROMPT_BANK_PATH = ROOT / "qa" / "background_agents" / "03_eval_prompt_bank.md"
RUNTIME_MODELS_SCRIPT_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-agent-runtime-models.js"
)

APPROVED_EXECUTION_FAMILIES = {
    ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-opus-4-7"),
    ("openAI", "gpt-5.4"),
}
APPROVED_ACTIVATION_FAMILY = ("groq", "meta-llama/llama-4-scout-17b-16e-instruct")
APPROVED_MAIN_AGENT_FAMILY = ("anthropic", "claude-opus-4-7")


def _load_source_of_truth() -> dict:
    return yaml.safe_load(SOURCE_OF_TRUTH_PATH.read_text(encoding="utf-8"))


def _load_librechat_source_of_truth() -> dict:
    return yaml.safe_load(SOURCE_OF_TRUTH_LIBRECHAT_PATH.read_text(encoding="utf-8"))


def _extract_table_first_column(markdown_path: Path, heading: str, header_label: str) -> list[str]:
    text = markdown_path.read_text(encoding="utf-8")
    section_match = re.search(
        rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert section_match, f"Could not find heading {heading!r} in {markdown_path}"
    section = section_match.group("body")
    lines = [line.strip() for line in section.splitlines() if line.strip()]

    table_start = None
    for index, line in enumerate(lines):
        if line.startswith("|") and f"| {header_label} |" in line:
            table_start = index
            break

    assert table_start is not None, f"Could not find table header {header_label!r} in {markdown_path}"

    names: list[str] = []
    for line in lines[table_start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0]:
            names.append(cells[0])
    return names


def _extract_manifest_names(markdown_path: Path) -> list[str]:
    text = markdown_path.read_text(encoding="utf-8")
    return re.findall(r"^###\s+\d+\.\s+(.+)$", text, flags=re.MULTILINE)


def _extract_scenario_ids(markdown_path: Path) -> set[str]:
    text = markdown_path.read_text(encoding="utf-8")
    return set(re.findall(r"^###\s+([A-Z]{2,3}-\d{2})\b", text, flags=re.MULTILINE))


def _load_runtime_models_contract() -> dict:
    result = subprocess.run(
        [
            "node",
            "-e",
            (
                "const runtime = require(process.argv[1]);"
                "console.log(JSON.stringify({"
                "runtimeFamilies: Array.from(runtime.APPROVED_BACKGROUND_RUNTIME_FAMILIES),"
                "activationFamilies: Array.from(runtime.APPROVED_BACKGROUND_ACTIVATION_FAMILIES),"
                "builtInAgentIds: Array.from(runtime.BUILT_IN_BACKGROUND_AGENT_IDS),"
                "runtimeEnvAgentIds: Object.keys(runtime.AGENT_RUNTIME_ENV_BY_ID)"
                "}));"
            ),
            str(RUNTIME_MODELS_SCRIPT_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return yaml.safe_load(result.stdout)


def test_background_agent_docs_stay_in_sync_with_source_of_truth() -> None:
    bundle = _load_source_of_truth()
    source_names = [agent["name"] for agent in bundle.get("backgroundAgents", [])]

    catalog_names = _extract_table_first_column(CATALOG_PATH, "Quick Matrix", "Agent")
    coverage_names = _extract_table_first_column(COVERAGE_MATRIX_PATH, "Current Matrix", "Agent")
    manifest_names = _extract_manifest_names(SIGNOFF_MANIFEST_PATH)

    assert catalog_names == source_names
    assert coverage_names == source_names
    assert manifest_names == source_names


def test_signoff_manifest_references_prompt_bank_scenarios_that_exist() -> None:
    prompt_bank_ids = _extract_scenario_ids(PROMPT_BANK_PATH)
    manifest_text = SIGNOFF_MANIFEST_PATH.read_text(encoding="utf-8")
    referenced_ids = set(re.findall(r"\b[A-Z]{2,3}-\d{2}\b", manifest_text))

    assert referenced_ids, "Expected signoff manifest to reference scenario ids"
    assert referenced_ids <= prompt_bank_ids


def test_background_agent_execution_models_stay_in_launch_ready_families() -> None:
    bundle = _load_source_of_truth()
    background_agents = bundle.get("backgroundAgents", [])
    assert background_agents, "Expected shipped background agents in source of truth"

    for agent in background_agents:
        assert agent.get("model_parameters", {}).get("model") == agent.get("model"), (
            f"{agent.get('name')} should keep top-level model and model_parameters.model aligned"
        )
        execution_family = (
            agent.get("provider"),
            agent.get("model_parameters", {}).get("model") or agent.get("model"),
        )
        assert execution_family in APPROVED_EXECUTION_FAMILIES, (
            f"{agent.get('name')} drifted to non-approved execution family {execution_family}"
        )


def test_local_source_of_truth_main_agent_stays_on_claude_opus_46() -> None:
    bundle = _load_source_of_truth()
    main_agent = bundle.get("mainAgent", {})

    assert (
        main_agent.get("provider"),
        main_agent.get("model_parameters", {}).get("model") or main_agent.get("model"),
    ) == APPROVED_MAIN_AGENT_FAMILY


def test_local_source_of_truth_main_agent_voice_route_defaults_to_fast_anthropic_without_thinking() -> None:
    bundle = _load_source_of_truth()
    main_agent = bundle.get("mainAgent", {})

    assert main_agent.get("voice_llm_provider") == "anthropic"
    assert main_agent.get("voice_llm_model") == "claude-haiku-4-5"
    assert main_agent.get("voice_llm_model_parameters", {}).get("thinking") is False


def test_runtime_models_script_exports_match_release_contract() -> None:
    runtime_contract = _load_runtime_models_contract()

    assert set(runtime_contract["runtimeFamilies"]) == {
        f"{provider}::{model}" for provider, model in APPROVED_EXECUTION_FAMILIES
    }
    assert set(runtime_contract["activationFamilies"]) == {
        f"{APPROVED_ACTIVATION_FAMILY[0]}::{APPROVED_ACTIVATION_FAMILY[1]}"
    }


def test_runtime_models_script_covers_all_shipped_background_agents() -> None:
    bundle = _load_source_of_truth()
    source_agent_ids = {agent["id"] for agent in bundle.get("backgroundAgents", [])}
    runtime_contract = _load_runtime_models_contract()

    runtime_env_agent_ids = set(runtime_contract["runtimeEnvAgentIds"]) - {"agent_viventium_main_95aeb3"}
    assert runtime_env_agent_ids == source_agent_ids
    assert set(runtime_contract["builtInAgentIds"]) == source_agent_ids


def test_background_cortex_activation_models_stay_on_llama_4_scout() -> None:
    bundle = _load_source_of_truth()
    cortices_by_agent_id = {
        cortex.get("agent_id"): cortex
        for cortex in bundle.get("mainAgent", {}).get("background_cortices", [])
        if cortex.get("agent_id")
    }

    for agent in bundle.get("backgroundAgents", []):
        cortex = cortices_by_agent_id.get(agent.get("id"))
        assert cortex is not None, f"Missing background cortex config for {agent.get('name')}"
        activation = cortex.get("activation") or {}
        activation_family = (activation.get("provider"), activation.get("model"))
        assert activation_family == APPROVED_ACTIVATION_FAMILY, (
            f"{agent.get('name')} activation drifted to {activation_family}"
        )


def test_librechat_source_of_truth_stays_on_current_anthropic_inventory() -> None:
    source = _load_librechat_source_of_truth()
    model_specs = source.get("modelSpecs", {}).get("list", [])
    anthropic_names = [
        spec.get("name")
        for spec in model_specs
        if spec.get("preset", {}).get("endpoint") == "anthropic"
    ]

    assert anthropic_names == ["claude-sonnet-4-6", "claude-opus-4-7"]
    assert source.get("endpoints", {}).get("anthropic", {}).get("summaryModel") == "claude-sonnet-4-6"
    assert source.get("balance", {}).get("enabled") is False
