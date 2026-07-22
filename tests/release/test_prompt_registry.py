from __future__ import annotations

import ast
import os
from pathlib import Path
import json
import re
import shutil
import subprocess

import pytest
import yaml

from scripts.viventium.prompt_registry import (
    KNOWN_RUNTIME_PLACEHOLDERS,
    PromptRegistryError,
    build_prompt_bundle,
    load_and_resolve_prompt_refs,
    load_prompt_registry,
    render_prompt,
)
from scripts.viventium.prompt_observability_dashboard import render_dashboard


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
AGENTS_SOURCE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.viventium-agents.yaml"
)
LIBRECHAT_SOURCE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.librechat.yaml"
)
SCHEDULING_CORTEX_SERVER = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "MCPs"
    / "scheduling-cortex"
    / "scheduling_cortex"
    / "server.py"
)
GLASSHIVE_MCP_SERVER = (
    REPO_ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "runtime_phase1"
    / "src"
    / "workers_projects_runtime"
    / "mcp_server.py"
)


def write_prompt(root: Path, rel: str, prompt_id: str, body: str, **metadata: object) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": prompt_id,
        "owner_layer": "test",
        "target": "test",
        "version": 1,
        "status": "active",
        "safety_class": "public_product",
        "required_context": [],
        "output_contract": "test",
        **metadata,
    }
    path.write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False).strip() + "\n---\n" + body.rstrip() + "\n",
        encoding="utf-8",
    )


def test_public_prompt_registry_validates_and_compiles() -> None:
    bundle = build_prompt_bundle(PROMPT_ROOT)

    assert bundle["prompt_root"] == "."
    assert bundle["prompt_count"] >= 50
    assert "main.conscious_agent" in bundle["prompts"]
    assert "surface.voice.provider.cartesia" in bundle["prompts"]
    assert "surface.voice.feeling_expression" in bundle["prompts"]
    assert "surface.telegram.audio_output" in bundle["prompts"]
    assert "surface.telegram.audio_provider.cartesia" in bundle["prompts"]
    assert "surface.telegram.audio_provider.chatterbox" in bundle["prompts"]
    assert "surface.telegram.audio_provider.plain_tts" in bundle["prompts"]
    assert "surface.telegram.audio_provider.xai" in bundle["prompts"]
    assert bundle["prompts"]["main.identity"]["content_hash"]
    assert all(
        not Path(prompt["path"]).is_absolute()
        and ".." not in Path(prompt["path"]).parts
        for prompt in bundle["prompts"].values()
    )


def test_prompt_bundle_paths_are_stable_outside_the_repository(tmp_path: Path) -> None:
    prompt_root = tmp_path / "detached-build" / "prompts"
    write_prompt(prompt_root, "nested/example.md", "test.detached", "Detached prompt")

    bundle = build_prompt_bundle(prompt_root)

    assert bundle["prompt_root"] == "."
    assert bundle["prompts"]["test.detached"]["path"] == "nested/example.md"
    assert str(tmp_path) not in json.dumps(bundle)


def test_source_yaml_prompt_refs_resolve_to_runtime_strings() -> None:
    agents = load_and_resolve_prompt_refs(yaml.safe_load(AGENTS_SOURCE.read_text(encoding="utf-8")))
    librechat = load_and_resolve_prompt_refs(
        yaml.safe_load(LIBRECHAT_SOURCE.read_text(encoding="utf-8"))
    )

    assert isinstance(agents["mainAgent"]["instructions"], str)
    assert "# Identity" in agents["mainAgent"]["instructions"]
    assert "{{current_user}}" in agents["mainAgent"]["instructions"]
    assert "For important actions, If unsure which service the user means, ask." in agents["mainAgent"]["instructions"]
    assert "configured/available connected email providers" in agents["mainAgent"]["instructions"]
    assert "Connected Accounts handoff for immediate checks and quick updates" in agents["mainAgent"]["instructions"]
    assert "immediate checks and quick updates" in agents["mainAgent"]["instructions"]
    assert "Do not use GlassHive when a simple read-only Connected Accounts handoff is the direct, sufficient path" in (
        agents["mainAgent"]["instructions"]
    )
    assert "For immediate connected-account checks or quick updates" in (
        agents["mainAgent"]["instructions"]
    )
    assert "first get explicit user confirmation" in agents["mainAgent"]["instructions"]
    assert "write-capable connected-account path" in agents["mainAgent"]["instructions"]
    assert "GlassHive host-signed broker path" in agents["mainAgent"]["instructions"]
    assert "If no write-capable path is available" in agents["mainAgent"]["instructions"]
    assert "creating/updating calendar events" in agents["mainAgent"]["instructions"]
    assert "deleting calendar events" in agents["mainAgent"]["instructions"]
    assert "Use GlassHive for document generation, reports, deep research" in (
        agents["mainAgent"]["instructions"]
    )
    assert "pass broker/MCP/tool availability as context" in agents["mainAgent"]["instructions"]
    assert "Do not make tool choice, provider lists" in agents["mainAgent"]["instructions"]
    assert "memory-derived priorities" in agents["mainAgent"]["instructions"]
    assert "For vague user adjectives like urgent or important, pass the adjective through" in agents["mainAgent"]["instructions"]
    assert isinstance(librechat["memory"]["agent"]["instructions"], str)
    assert isinstance(librechat["mcpServers"]["ms-365"]["serverInstructions"], str)
    assert "Microsoft 365 owns" in librechat["mcpServers"]["ms-365"]["serverInstructions"]


def test_main_and_background_agent_execution_prompts_are_registry_owned() -> None:
    source = yaml.safe_load(AGENTS_SOURCE.read_text(encoding="utf-8"))
    registry = load_prompt_registry(PROMPT_ROOT)

    assert source["mainAgent"]["instructions"] == {"promptRef": "main.conscious_agent"}

    for agent in source["backgroundAgents"]:
        instructions = agent.get("instructions")
        assert isinstance(instructions, dict), (
            f"{agent['name']} duplicates its execution prompt inline instead of using Prompt Workbench"
        )
        prompt_id = instructions.get("promptRef")
        assert prompt_id in registry, f"{agent['name']} has no registered execution prompt"
        assert registry[prompt_id].metadata["target"] == (
            f"backgroundAgents.{agent['id']}.instructions"
        )


def test_emotional_resonance_is_an_eq_observer_not_a_fixed_demeanor() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    prompt = render_prompt("cortex.emotional_resonance.execution", registry)

    assert "high-EQ" in prompt
    assert "word choice" in prompt
    assert "uncertainty" in prompt
    assert "warm not clinical" not in prompt
    assert "One gentle opening" not in prompt


def test_main_memory_policy_uses_product_neutral_user_references() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    prompt = render_prompt("main.memory_policy", registry)

    assert "What the user said" in prompt
    assert "Who the user is" in prompt
    assert "What he said" not in prompt
    assert "Who he is" not in prompt
    assert "help him" not in prompt
    assert "about him" not in prompt


def test_main_agent_keeps_glasshive_gateway_eager_and_defers_bulk_operations() -> None:
    agents = yaml.safe_load(AGENTS_SOURCE.read_text(encoding="utf-8"))
    main_agent = agents["mainAgent"]
    options = main_agent.get("tool_options") or {}
    glasshive_operations = {
        tool
        for tool in main_agent.get("tools", [])
        if tool.endswith("_mcp_glasshive-workers-projects")
        and not tool.startswith("sys__server__")
    }

    eager_gateway = {
        "workspace_launch_mcp_glasshive-workers-projects",
        "workspace_status_mcp_glasshive-workers-projects",
        "workspace_wait_mcp_glasshive-workers-projects",
    }
    deferred_operations = glasshive_operations - eager_gateway

    assert eager_gateway <= glasshive_operations
    assert deferred_operations
    assert all(options.get(tool, {}).get("defer_loading") is not True for tool in eager_gateway)
    assert all(
        options.get(tool, {}).get("defer_loading") is True for tool in deferred_operations
    )
    assert options.get("file_search", {}).get("defer_loading") is not True
    assert options.get("sys__server__sys_mcp_glasshive-workers-projects", {}).get(
        "defer_loading"
    ) is not True


def test_js_sync_resolves_full_source_agent_yaml_prompt_refs(tmp_path: Path) -> None:
    output_path = tmp_path / "resolved-agents.json"
    script = """
const fs = require('fs');
const yaml = require('js-yaml');
const { resolvePromptRefs } = require('./scripts/viventium-sync-agents.js');
const source = yaml.load(fs.readFileSync('./viventium/source_of_truth/local.viventium-agents.yaml', 'utf8'));
const resolved = resolvePromptRefs(source);
fs.writeFileSync(process.argv[1], JSON.stringify(resolved));
process.exit(0);
"""
    result = subprocess.run(
        ["node", "-e", script, str(output_path)],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat",
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert result.stderr == ""
    resolved = json.loads(output_path.read_text(encoding="utf-8"))

    def assert_no_prompt_ref_keys(value: object) -> None:
        if isinstance(value, dict):
            assert "promptRef" not in value
            assert "promptRefs" not in value
            for nested in value.values():
                assert_no_prompt_ref_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_no_prompt_ref_keys(nested)

    assert_no_prompt_ref_keys(resolved)
    assert "# Identity" in resolved["mainAgent"]["instructions"]
    assert "{{current_user}}" in resolved["mainAgent"]["instructions"]
    assert "Runtime-Owned Background Cards" in resolved["mainAgent"]["instructions"]


def test_prompt_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    write_prompt(tmp_path, "one.md", "dup.prompt", "One")
    write_prompt(tmp_path, "nested/two.md", "dup.prompt", "Two")

    with pytest.raises(PromptRegistryError, match="Duplicate prompt id"):
        load_prompt_registry(tmp_path)


def test_prompt_registry_rejects_include_cycles(tmp_path: Path) -> None:
    write_prompt(tmp_path, "a.md", "a", "A", includes=["b"])
    write_prompt(tmp_path, "b.md", "b", "B", includes=["a"])
    registry = load_prompt_registry(tmp_path)

    with pytest.raises(PromptRegistryError, match="include cycle"):
        render_prompt("a", registry)


def test_prompt_registry_rejects_unfilled_strict_variables(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "needs-var.md",
        "needs.var",
        "Hello {{name}}",
        strict_variables=True,
    )
    registry = load_prompt_registry(tmp_path)

    with pytest.raises(PromptRegistryError, match="Missing prompt variable"):
        render_prompt("needs.var", registry)

    assert render_prompt("needs.var", registry, variables={"name": "Viv"}).strip() == "Hello Viv"


def test_prompt_registry_keeps_runtime_placeholders_for_non_strict_prompts(tmp_path: Path) -> None:
    write_prompt(tmp_path, "runtime.md", "runtime.placeholder", "Hello {{current_user}}")
    registry = load_prompt_registry(tmp_path)

    assert render_prompt("runtime.placeholder", registry).strip() == "Hello {{current_user}}"


def test_prompt_registry_rejects_unknown_runtime_placeholder_typos(tmp_path: Path) -> None:
    write_prompt(tmp_path, "runtime.md", "runtime.placeholder", "Hello {{currnet_user}}")
    registry = load_prompt_registry(tmp_path)

    with pytest.raises(PromptRegistryError, match="Unknown unfilled prompt variable"):
        render_prompt("runtime.placeholder", registry)


def test_phase_b_follow_up_prompts_render_with_declared_variables() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    ordinary = render_prompt(
        "cortex.follow_up_phase_b.user_message",
        registry,
        variables={
            "surface_rules": "WEB TEXT MODE:",
            "recent_response_context": "Here is the response you JUST sent to the user:",
            "continuation_context": "",
            "background_insights": "- worker: The task finished.",
            "background_limitations": "",
        },
    )
    system = render_prompt(
        "cortex.follow_up_phase_b.system",
        registry,
        variables={
            "continuation_contract": "",
            "no_response_instructions": "",
        },
    )
    primary = render_prompt(
        "cortex.follow_up_phase_b.primary_user_message",
        registry,
        variables={
            "surface_rules": "WEB TEXT MODE:",
            "user_request": "Summarize the finished task.",
            "recent_response": "I am checking.",
            "background_insights": "- worker: The task finished.",
            "background_limitations": "",
        },
    )

    assert "WEB TEXT MODE:" in ordinary
    assert "output exactly {NTA}" in ordinary
    assert "surface genuinely new information" in system
    assert "primary user-visible answer" in primary


def test_prompt_registry_rejects_private_patterns_in_public_prompt_tree(tmp_path: Path) -> None:
    unsafe_path = "/" + "Users" + "/example/private.txt"
    write_prompt(tmp_path, "private.md", "private.prompt", f"Read {unsafe_path}")

    with pytest.raises(PromptRegistryError, match="Private pattern"):
        load_prompt_registry(tmp_path)


def test_prompt_dashboard_public_safe_mode_hides_prompt_text(tmp_path: Path) -> None:
    out = tmp_path / "dashboard.html"
    render_dashboard(output=out, logs_root=tmp_path / "logs", include_private_text=False)

    text = out.read_text(encoding="utf-8")
    assert "Viventium Prompt Observatory" in text
    assert "main.conscious_agent" in text
    assert "hidden in public-safe mode" in text
    assert "You're Viventium" not in text


def test_prompt_dashboard_refuses_private_frames_in_public_repo_without_override(tmp_path: Path) -> None:
    logs_root = tmp_path / "logs"
    day_dir = logs_root / "2026-05-09"
    day_dir.mkdir(parents=True)
    (day_dir / "frames.jsonl").write_text(
        json.dumps({"event": "viventium.prompt_frame", "surface": "web"}) + "\n",
        encoding="utf-8",
    )
    public_output = REPO_ROOT / "qa" / "prompt-architecture" / "reports" / "tmp-dashboard-test.html"

    with pytest.raises(ValueError, match="Refusing to write private frame-log summaries"):
        render_dashboard(output=public_output, logs_root=logs_root, include_private_text=False)

    assert not public_output.exists()


def test_prompt_dashboard_public_frame_summary_whitelists_decision_state(tmp_path: Path) -> None:
    logs_root = tmp_path / "logs"
    day_dir = logs_root / "2026-05-09"
    day_dir.mkdir(parents=True)
    (day_dir / "frames.jsonl").write_text(
        json.dumps(
            {
                "event": "viventium.prompt_frame",
                "surface": "web",
                "prompt_family": "main",
                "provider": "openAI",
                "model": "gpt-5.4",
                "layer_hashes": {"main_instructions": "abc123"},
                "layer_token_estimates": {"main_instructions": 123},
                "decision_state": {
                    "status": "complete",
                    "confidence": 0.8,
                    "reason": "private user phrasing can land here",
                    "reason_code": "provider_done",
                    "private_prompt_text": "do not publish",
                    "raw_user_text": "do not publish",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    public_output = tmp_path / "public-dashboard.html"

    render_dashboard(
        output=public_output,
        logs_root=logs_root,
        include_private_text=False,
        allow_public_output=True,
    )

    text = public_output.read_text(encoding="utf-8")
    assert "complete" in text
    assert "0.8" in text
    assert "provider_done" in text
    assert "private user phrasing" not in text
    assert "private_prompt_text" not in text
    assert "raw_user_text" not in text
    assert "do not publish" not in text


def test_prompt_dashboard_refuses_private_prompt_text_in_public_repo_even_without_frames(
    tmp_path: Path,
) -> None:
    public_output = REPO_ROOT / "qa" / "prompt-architecture" / "reports" / "tmp-private-dashboard-test.html"

    with pytest.raises(ValueError, match="Refusing to write private prompt-text dashboard"):
        render_dashboard(output=public_output, logs_root=tmp_path / "logs", include_private_text=True)

    assert not public_output.exists()


def test_prompt_dashboard_refuses_private_prompt_text_in_public_repo_even_with_override(
    tmp_path: Path,
) -> None:
    public_output = REPO_ROOT / "qa" / "prompt-architecture" / "reports" / "tmp-private-dashboard-override-test.html"

    with pytest.raises(ValueError, match="Refusing to write private prompt-text dashboard"):
        render_dashboard(
            output=public_output,
            logs_root=tmp_path / "logs",
            include_private_text=True,
            allow_public_output=True,
        )

    assert not public_output.exists()


def test_scheduling_cortex_fastmcp_instructions_match_registry_prompt() -> None:
    server_text = SCHEDULING_CORTEX_SERVER.read_text(encoding="utf-8")
    match = re.search(
        r"SCHEDULING_CORTEX_INSTRUCTIONS\s*=\s*(?P<string>\"\"\".*?\"\"\")\.strip\(\)",
        server_text,
        re.S,
    )
    assert match, "SCHEDULING_CORTEX_INSTRUCTIONS literal not found"
    server_instructions = ast.literal_eval(match.group("string")).strip()
    registry = load_prompt_registry(PROMPT_ROOT)
    registry_instructions = render_prompt("mcp.scheduling_cortex.server", registry).strip()

    assert registry_instructions == server_instructions


def _load_glasshive_instruction_namespace():
    tree = ast.parse(GLASSHIVE_MCP_SERVER.read_text(encoding="utf-8"))
    selected_names = {
        "_allowed_worker_profiles",
        "_configured_default_worker_profile",
        "_default_execution_mode",
        "_host_profile_available",
        "_host_profile_binary",
        "_host_workers_enabled",
        "_host_worker_mentions",
        "_worker_surface_summary",
        "_worker_surface_routing_guidance",
        "_worker_capability_summary",
        "_worker_execution_instruction",
        "glasshive_workers_server_instructions",
    }
    selected_nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in selected_names)
        or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                in {"HOST_SIDE_ORCHESTRATION_GUIDANCE", "HIGH_EFFORT_SELECTION_GUIDANCE"}
                for target in node.targets
            )
        )
    ]
    namespace: dict[str, object] = {"os": os, "shutil": shutil}
    exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), str(GLASSHIVE_MCP_SERVER), "exec"), namespace)
    return namespace


def _load_glasshive_instruction_builder():
    namespace = _load_glasshive_instruction_namespace()
    return namespace["glasshive_workers_server_instructions"]


def test_glasshive_fastmcp_default_instructions_match_registry_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLASSHIVE_HOST_WORKERS_ENABLED", "true")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")
    monkeypatch.setenv("WPR_HOST_MENTION_CODEX", "@codex")
    monkeypatch.setenv("WPR_HOST_MENTION_CLAUDE", "@claude")
    monkeypatch.setenv("WPR_HOST_MENTION_OPENCLAW", "@openclaw")

    namespace = _load_glasshive_instruction_namespace()
    server_instructions = namespace["glasshive_workers_server_instructions"]().strip()
    registry = load_prompt_registry(PROMPT_ROOT)
    registry_instructions = render_prompt(
        "mcp.glasshive_workers.server",
        registry,
        variables={
            "glasshive_worker_capability_summary": namespace["_worker_capability_summary"](),
            "glasshive_worker_execution_instruction": namespace["_worker_execution_instruction"](),
        },
    ).strip()

    assert registry_instructions == server_instructions
    assert "tool_search" in server_instructions
    assert "query=<needed capability>" in server_instructions
    assert "mcp_server=glasshive-workers-projects" in server_instructions
    assert "same invocation" in server_instructions
    assert "needed GlassHive capability is not currently available" in server_instructions


def test_glasshive_prompt_reflects_disabled_host_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLASSHIVE_HOST_WORKERS_ENABLED", "false")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")

    namespace = _load_glasshive_instruction_namespace()
    registry = load_prompt_registry(PROMPT_ROOT)
    rendered = render_prompt(
        "mcp.glasshive_workers.server",
        registry,
        variables={
            "glasshive_worker_capability_summary": namespace["_worker_capability_summary"](),
            "glasshive_worker_execution_instruction": namespace["_worker_execution_instruction"](),
        },
    )

    assert "Host-native workers are disabled by GlassHive config" in rendered
    assert "configured default 'docker'" in rendered
    assert "do not request execution_mode='host'" in rendered
    assert "Default to host-native execution" not in rendered


def test_live_data_prompt_uses_non_important_best_judgment_for_connected_inbox() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    rendered = render_prompt("main.truth_live_data", registry)

    assert (
        "- For important actions, If unsure which service the user means, ask. "
        "Otherwise, use your best judgement or get what you can."
    ) in rendered
    assert "configured/available connected email providers" in rendered
    assert "do not defer the check to background cortices" in rendered
    assert "read-only Connected Accounts handoff for immediate checks and quick updates" in rendered
    assert "pass broker/MCP/tool availability as context" in rendered
    assert "memory-derived priorities" in rendered
    assert "For vague user adjectives like urgent or important, pass the adjective through" in rendered
    assert "trust the GlassHive worker to choose the best path" in rendered
    assert "Do not use GlassHive when a simple read-only Connected Accounts handoff" in rendered


def test_glasshive_worker_prompt_prefers_broker_tools_over_browser_for_connected_accounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLASSHIVE_HOST_WORKERS_ENABLED", "true")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")

    namespace = _load_glasshive_instruction_namespace()
    registry = load_prompt_registry(PROMPT_ROOT)
    rendered = render_prompt(
        "mcp.glasshive_workers.server",
        registry,
        variables={
            "glasshive_worker_capability_summary": namespace["_worker_capability_summary"](),
            "glasshive_worker_execution_instruction": namespace["_worker_execution_instruction"](),
        },
    )

    assert "MCP/tools are preferred when they can satisfy the task" in rendered
    assert "Do not make tool choice a workspace success criterion" in rendered
    assert "Do not invent project goals, success criteria" in rendered
    assert "memory-derived priorities" in rendered
    assert "For vague user adjectives like urgent or important, pass the adjective through" in rendered
    assert "trust the GlassHive worker to find the best path" in rendered
    assert "Satisfy the user's request as stated, preserving explicit constraints" in rendered
    assert "Connected-account read authorization comes from the host-signed broker grant" in rendered
    assert "when reviewed host policy projects content-read scope" in rendered
    assert "connected_account_content_intent is only a compatibility hint" in rendered
    assert "not a required authorization switch" in rendered
    assert "success_criteria as broker/tool evidence gates" not in rendered
    assert "Browser or computer use remains available" in rendered
    assert "preferred scoped option" in rendered
    assert "non-broker host connectors are fallback after" in rendered
    assert "set connected_account_content_intent=true" not in rendered


def test_three_way_prompt_ref_resolution_matches_python_js_sync_and_runtime(
    tmp_path: Path,
) -> None:
    fixture = {
        "voice": {
            "promptRef": "surface.voice.provider.cartesia",
            "promptVars": {
                "cartesia": {
                    "model_id": "sonic-3",
                    "nonverbal_markers": ["[laughter]"],
                    "emotions": ["calm", "excited"],
                    "primary_emotions": ["calm"],
                    "speed": {"min": "0.5", "max": "2.0"},
                    "volume": {"min": "0.5", "max": "2.0"},
                    "syntax": {
                        "emotion_state_change": '<emotion value="EMOTION"/>',
                        "emotion_scoped": '<emotion value="EMOTION">TEXT</emotion>',
                        "speed": '<speed ratio="RATIO"/>',
                        "volume": '<volume ratio="RATIO"/>',
                        "break": '<break time="DURATION"/>',
                        "spell": "<spell>TEXT</spell>",
                    },
                }
            },
        },
        "runtime": {"promptRef": "main.identity"},
    }
    python_resolved = load_and_resolve_prompt_refs(fixture)
    bundle_path = tmp_path / "prompt-bundle.json"
    bundle_path.write_text(
        json.dumps(build_prompt_bundle(PROMPT_ROOT), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    script = """
const { resolvePromptRefs } = require('./scripts/viventium-sync-agents.js');
const chunks = [];
  process.stdin.on('data', (chunk) => chunks.push(chunk));
  process.stdin.on('end', () => {
    const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    process.stdout.write('__PROMPT_REF_JSON__' + JSON.stringify(resolvePromptRefs(input)));
    process.exit(0);
  });
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat",
        input=json.dumps(fixture),
        text=True,
        capture_output=True,
        check=True,
    )
    marker = "__PROMPT_REF_JSON__"
    assert marker in result.stdout
    js_resolved = json.loads(result.stdout.rsplit(marker, 1)[1])

    assert js_resolved == python_resolved
    assert "{{current_user}}" in js_resolved["runtime"]
    assert "sonic-3" in js_resolved["voice"]

    runtime_script = """
const { PROMPT_BUNDLE_ENV, getPromptText, resetPromptRegistryForTests } = require('./server/services/viventium/promptRegistry');
const payload = JSON.parse(process.argv[2]);
process.env[PROMPT_BUNDLE_ENV] = process.argv[1];
resetPromptRegistryForTests();
process.stdout.write(JSON.stringify({
  voice: getPromptText('surface.voice.provider.cartesia', 'fallback', payload.voice.promptVars),
  runtime: getPromptText('main.identity', 'fallback'),
}));
"""
    runtime = subprocess.run(
        ["node", "-e", runtime_script, str(bundle_path), json.dumps(fixture)],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api",
        text=True,
        capture_output=True,
        check=True,
    )
    runtime_resolved = json.loads(runtime.stdout)

    assert runtime_resolved == python_resolved


def test_runtime_placeholder_allowlist_matches_python_js_sync_and_runtime() -> None:
    sync_script = """
const { KNOWN_RUNTIME_PLACEHOLDERS } = require('./scripts/viventium-sync-agents.js');
process.stdout.write(JSON.stringify([...KNOWN_RUNTIME_PLACEHOLDERS].sort()));
process.exit(0);
"""
    runtime_script = """
const { KNOWN_RUNTIME_PLACEHOLDERS } = require('./server/services/viventium/promptRegistry');
process.stdout.write(JSON.stringify([...KNOWN_RUNTIME_PLACEHOLDERS].sort()));
process.exit(0);
"""

    sync = subprocess.run(
        ["node", "-e", sync_script],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat",
        text=True,
        capture_output=True,
        check=True,
    )
    runtime = subprocess.run(
        ["node", "-e", runtime_script],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api",
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(sync.stdout) == sorted(KNOWN_RUNTIME_PLACEHOLDERS)
    assert json.loads(runtime.stdout) == sorted(KNOWN_RUNTIME_PLACEHOLDERS)


def test_js_sync_prompt_parser_enforces_frontmatter_and_public_safety(tmp_path: Path) -> None:
    unsafe_prompt = tmp_path / "unsafe.md"
    unsafe_prompt.write_text(
        "---\n"
        "id: unsafe.prompt\n"
        "owner_layer: test\n"
        "target: test\n"
        "version: 1\n"
        "status: active\n"
        "safety_class: public_product\n"
        "output_contract: test\n"
        "---\n"
        "Read /" + "Users" + "/example/private.txt\n",
        encoding="utf-8",
    )
    missing_field_prompt = tmp_path / "missing.md"
    missing_field_prompt.write_text(
        "---\n"
        "id: missing.prompt\n"
        "version: 1\n"
        "status: active\n"
        "safety_class: public_product\n"
        "---\n"
        "Body\n",
        encoding="utf-8",
    )
    script = """
const { parsePromptMarkdown } = require('./scripts/viventium-sync-agents.js');
const results = {};
for (const filePath of process.argv.slice(1)) {
  try {
    parsePromptMarkdown(filePath);
    results[filePath] = 'ok';
  } catch (error) {
    results[filePath] = error.message;
  }
}
process.stdout.write(JSON.stringify(results));
process.exit(0);
"""
    result = subprocess.run(
        ["node", "-e", script, str(unsafe_prompt), str(missing_field_prompt)],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat",
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert "Private pattern local_absolute_path" in payload[str(unsafe_prompt)]
    assert "Prompt frontmatter missing" in payload[str(missing_field_prompt)]


def test_runtime_surface_prompt_fallbacks_match_registry_rendering(tmp_path: Path) -> None:
    bundle_path = tmp_path / "prompt-bundle.json"
    bundle_path.write_text(
        json.dumps(build_prompt_bundle(PROMPT_ROOT), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    script = r"""
const {
  buildVoiceModeInstructions,
  buildTelegramAudioOutputInstructions,
  buildTelegramTextInstructions,
  buildWebTextInstructions,
  buildPlaygroundTextInstructions,
  buildVoiceNoteInputInstructions,
  buildVoiceCallInputInstructions,
  buildWingModeInstructions,
  buildCortexOutputInstructions,
  buildTimeContextInstructions,
} = require('./server/services/viventium/surfacePrompts');
const {
  PROMPT_BUNDLE_ENV,
  resetPromptRegistryForTests,
} = require('./server/services/viventium/promptRegistry');

const bundlePath = process.argv[1];
for (const key of [
  'VIVENTIUM_VOICE_MODE_PROMPT',
  'VIVENTIUM_TELEGRAM_TEXT_MODE_PROMPT',
  'VIVENTIUM_PLAYGROUND_TEXT_MODE_PROMPT',
  'VIVENTIUM_TELEGRAM_VOICE_NOTE_PROMPT',
  'VIVENTIUM_VOICE_CALL_INPUT_PROMPT',
  'VIVENTIUM_WING_MODE_PROMPT',
  'VIVENTIUM_SHADOW_MODE_PROMPT',
  'VIVENTIUM_CORTEX_OUTPUT_RULES',
  'VIVENTIUM_TIME_CONTEXT_PROMPT',
]) {
  delete process.env[key];
}

function timeReq() {
  return {
    body: {
      clientTimestamp: '2026-05-09T08:30:00',
      clientTimezone: 'America/Toronto',
    },
  };
}

function snapshot(useBundle) {
  if (useBundle) {
    process.env[PROMPT_BUNDLE_ENV] = bundlePath;
  } else {
    delete process.env[PROMPT_BUNDLE_ENV];
  }
  resetPromptRegistryForTests();
  return {
    voice_cartesia: buildVoiceModeInstructions('cartesia'),
    voice_xai: buildVoiceModeInstructions('x_ai'),
    voice_chatterbox: buildVoiceModeInstructions('chatterbox'),
    voice_plain: buildVoiceModeInstructions('openai'),
    voice_unknown: buildVoiceModeInstructions(''),
    telegram_audio_cartesia: buildTelegramAudioOutputInstructions('cartesia'),
    telegram_audio_xai: buildTelegramAudioOutputInstructions('xai'),
    telegram_audio_chatterbox: buildTelegramAudioOutputInstructions('chatterbox'),
    telegram_audio_plain: buildTelegramAudioOutputInstructions('openai'),
    telegram_audio_unknown: buildTelegramAudioOutputInstructions(''),
    telegram: buildTelegramTextInstructions(),
    web: buildWebTextInstructions(),
    playground: buildPlaygroundTextInstructions(),
    voice_note: buildVoiceNoteInputInstructions(),
    voice_call_input: buildVoiceCallInputInstructions(),
    wing: buildWingModeInstructions(),
    cortex_voice: buildCortexOutputInstructions({ voiceMode: true, surface: 'voice' }),
    cortex_telegram: buildCortexOutputInstructions({ surface: 'telegram' }),
    cortex_playground: buildCortexOutputInstructions({ surface: 'playground' }),
    cortex_web: buildCortexOutputInstructions({ surface: 'web' }),
    time_context: buildTimeContextInstructions(timeReq()),
  };
}

process.stdout.write(JSON.stringify({
  registry: snapshot(true),
  fallback: snapshot(false),
}));
"""
    result = subprocess.run(
        ["node", "-e", script, str(bundle_path)],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api",
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    assert {
        key: normalize(value)
        for key, value in payload["registry"].items()
    } == {
        key: normalize(value)
        for key, value in payload["fallback"].items()
    }
