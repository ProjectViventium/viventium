"""The optional Chrome connection uses existing compiler and per-user MCP owners."""

import copy

import pytest
import yaml

from test_config_compiler import (
    REPO_ROOT,
    config_compiler,
    load_source_of_truth_agents_bundle,
    minimal_compile_config,
)


def compiled(config):
    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)
    settings = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))
    agents = config_compiler.render_native_agents_bundle(config, assignments, set(settings["mcpServers"]))
    return env, settings, agents


def ownership(settings):
    return settings["viventium"]["background_cortices"]["activation_policy"]["direct_action_mcp_servers"]


@pytest.mark.parametrize("setting", [None, {"enabled": False}])
def test_optional_chrome_is_absent_from_default_server_and_agent_views(setting):
    config = minimal_compile_config()
    if setting is not None:
        config["integrations"]["chrome_devtools"] = setting
    env, settings, agents = compiled(config)
    assert "chrome-devtools" not in settings["mcpServers"]
    assert "MCP_PERSISTENT_CONNECTION_SERVERS" not in env
    assert all(item["server"] != "chrome-devtools" for item in ownership(settings))
    assert "list_pages_mcp_chrome-devtools" not in agents["mainAgent"]["tools"]
    assert "list_pages_mcp_chrome-devtools" not in agents["mainAgent"]["tool_options"]


def test_enabled_chrome_uses_the_pinned_official_server_and_reviewed_local_owner_policy():
    config = minimal_compile_config()
    config["integrations"]["chrome_devtools"] = {"enabled": True}
    env, settings, agents = compiled(config)
    server = settings["mcpServers"]["chrome-devtools"]
    assert server["command"] == "npx"
    assert server["args"] == [
        "-y", "chrome-devtools-mcp@1.12.0", "--autoConnect",
        "--no-usage-statistics", "--no-performance-crux",
    ]
    assert server["startup"] is False
    assert server["viventiumAccess"] == {"audience": "local_owner"}
    assert server["viventiumGlassHive"] == {
        "version": 1, "permitsAutonomousWorker": True,
        "hostAllowed": True, "sandboxAllowed": False,
        "defaultToolAccess": "content_read", "contentReadPolicy": "require_broker_grant",
        "writePolicy": "allow", "riskClass": "local_browser_control",
        "reexportNativeTools": True, "nativeServerIds": ["chrome-devtools"],
    }
    assert "toolPolicies" not in server["viventiumGlassHive"]
    assert env["MCP_PERSISTENT_CONNECTION_SERVERS"] == "scheduling-cortex,chrome-devtools"
    source = load_source_of_truth_agents_bundle()
    anchor = next(item for item in ownership(settings) if item["server"] == "chrome-devtools")
    assert anchor == next(item for item in ownership(source["config"]) if item["server"] == "chrome-devtools")
    assert anchor["tool_names"] == ["list_pages_mcp_chrome-devtools"]
    assert agents["mainAgent"]["tools"].count("list_pages_mcp_chrome-devtools") == 1
    assert agents["mainAgent"]["tool_options"]["list_pages_mcp_chrome-devtools"] == {"defer_loading": True}


@pytest.mark.parametrize("existing,expected", [
    ("another-service", "another-service,chrome-devtools"),
    ("scheduling-cortex, another-service,chrome-devtools,another-service", "scheduling-cortex,another-service,chrome-devtools"),
])
def test_enabled_chrome_preserves_other_persistent_connections_across_all_env_outputs(tmp_path, existing, expected):
    config = minimal_compile_config()
    config["integrations"]["chrome_devtools"] = {"enabled": True}
    config["runtime"]["extra_env"] = {"MCP_PERSISTENT_CONNECTION_SERVERS": existing}
    env, _, _ = compiled(config)
    assert env["MCP_PERSISTENT_CONNECTION_SERVERS"] == expected
    native = config_compiler.render_native_runtime_env(config, env)
    assert native["MCP_PERSISTENT_CONNECTION_SERVERS"] == expected
    config_compiler.render_service_envs(tmp_path, env)
    service = config_compiler.parse_env_file(tmp_path / "service-env" / "librechat.env")
    assert service["MCP_PERSISTENT_CONNECTION_SERVERS"] == expected
    config["integrations"]["chrome_devtools"]["enabled"] = False
    off, settings, _ = compiled(config)
    assert off["MCP_PERSISTENT_CONNECTION_SERVERS"] == existing
    assert "chrome-devtools" not in settings["mcpServers"]


def test_chrome_availability_changes_no_agent_models_personality_or_worker_settings():
    config = minimal_compile_config()
    _, _, before = compiled(config)
    config["integrations"]["chrome_devtools"] = {"enabled": True}
    _, _, after = compiled(config)
    expected = copy.deepcopy(after["mainAgent"])
    expected["tools"].remove("list_pages_mcp_chrome-devtools")
    expected["tool_options"].pop("list_pages_mcp_chrome-devtools")
    assert expected == before["mainAgent"]
    assert after.get("handoffAgents") == before.get("handoffAgents")


def test_compiled_activation_ownership_has_one_source_and_preserves_other_template_fields(monkeypatch):
    source = load_source_of_truth_agents_bundle()
    source_owners = ownership(source["config"])
    template = config_compiler.load_source_of_truth_librechat_yaml()
    template_policy = template["viventium"]["background_cortices"]["activation_policy"]
    template_policy["enabled"] = False
    template_policy["direct_action_mcp_servers"] = [{"server": "stale-duplicate", "tool_names": []}]
    monkeypatch.setattr(config_compiler, "load_source_of_truth_librechat_yaml", lambda: copy.deepcopy(template))
    config = minimal_compile_config()
    config["integrations"]["health"] = {"enabled": True}
    config["integrations"]["chrome_devtools"] = {"enabled": True}
    _, settings, _ = compiled(config)
    policy = settings["viventium"]["background_cortices"]["activation_policy"]
    assert policy["enabled"] is False
    assert policy["prompt"] == template_policy["prompt"]
    assert ownership(settings) == [item for item in source_owners if item["server"] in settings["mcpServers"]]
    assert {item["server"] for item in ownership(settings)} >= {"viventium-health", "chrome-devtools"}


def test_public_config_schema_and_examples_keep_chrome_off_by_default():
    schema = yaml.safe_load((REPO_ROOT / "config.schema.yaml").read_text())
    setting = schema["properties"]["integrations"]["properties"]["chrome_devtools"]
    assert setting["additionalProperties"] is False
    assert setting["properties"]["enabled"] == {"type": "boolean", "default": False}
    for name in ("config.minimal.example.yaml", "config.full.example.yaml"):
        example = yaml.safe_load((REPO_ROOT / name).read_text())
        assert example["integrations"]["chrome_devtools"] == {"enabled": False}


def test_chrome_configuration_rejects_an_untyped_server_setting():
    with pytest.raises(SystemExit, match="chrome_devtools must be an object"):
        config_compiler.chrome_devtools_enabled({"integrations": {"chrome_devtools": ["enabled"]}})
