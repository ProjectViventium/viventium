# VIVENTIUM START
# Tests for config generation — validates output matches OpenClawConfig schema.
#
# This replaces the old template-based tests since config is now
# generated programmatically in _generate_config().
#
# Source: openclaw/src/config/types.openclaw.ts (OpenClawConfig)
# Source: openclaw/src/config/types.gateway.ts (GatewayConfig)
# Source: openclaw/src/config/types.plugins.ts (PluginsConfig)
# Source: openclaw/src/config/types.models.ts (ModelsConfig — no "default" key)
# Source: openclaw/src/config/types.agents.ts (AgentsConfig — model in agents.defaults.model)
# Source: openclaw/src/config/zod-schema.agent-defaults.ts (model must be object, not string)
# VIVENTIUM END

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import openclaw_manager as mgr


class TestConfigSchema:
    """Validate that generated configs match OpenClawConfig structure."""

    def _generate(self, fresh_manager, user="user-1", port=18800):
        state_dir = fresh_manager._get_user_state_dir(user)
        config_path = fresh_manager._generate_config(user, state_dir, port)
        return json.loads(config_path.read_text())

    def test_top_level_keys_are_valid(self, fresh_manager):
        """All top-level keys must be valid OpenClawConfig keys.
        Source: types.openclaw.ts lines 28-99
        """
        cfg = self._generate(fresh_manager)
        valid_keys = {
            "meta", "auth", "env", "wizard", "diagnostics", "logging",
            "update", "browser", "ui", "skills", "plugins", "models",
            "nodeHost", "agents", "tools", "bindings", "broadcast",
            "audio", "messages", "commands", "approvals", "session",
            "web", "channels", "cron", "hooks", "discovery",
            "canvasHost", "talk", "gateway", "memory",
        }
        for key in cfg:
            assert key in valid_keys, f"Invalid top-level key: {key}"

    def test_gateway_keys_are_valid(self, fresh_manager):
        """All gateway keys must be valid GatewayConfig keys.
        Source: types.gateway.ts lines 214-248
        """
        cfg = self._generate(fresh_manager)
        valid_gw_keys = {
            "port", "mode", "bind", "customBindHost", "controlUi",
            "auth", "tailscale", "remote", "reload", "tls",
            "http", "nodes", "trustedProxies",
        }
        for key in cfg.get("gateway", {}):
            assert key in valid_gw_keys, f"Invalid gateway key: {key}"

    def test_gateway_auth_keys_are_valid(self, fresh_manager):
        """Auth keys must match GatewayAuthConfig.
        Source: types.gateway.ts lines 81-90
        """
        cfg = self._generate(fresh_manager)
        valid_auth_keys = {"mode", "token", "password", "allowTailscale"}
        for key in cfg["gateway"].get("auth", {}):
            assert key in valid_auth_keys, f"Invalid auth key: {key}"

    def test_gateway_http_structure(self, fresh_manager):
        """HTTP config structure must match GatewayHttpConfig.
        Source: types.gateway.ts lines 196-198
        """
        cfg = self._generate(fresh_manager)
        http = cfg["gateway"].get("http", {})
        # http only has "endpoints" key
        for key in http:
            assert key == "endpoints", f"Invalid gateway.http key: {key}"

    def test_plugins_keys_are_valid(self, fresh_manager):
        """Plugin keys must match PluginsConfig.
        Source: types.plugins.ts lines 25-36
        """
        cfg = self._generate(fresh_manager)
        valid_plugin_keys = {
            "enabled", "allow", "deny", "load", "slots", "entries", "installs",
        }
        for key in cfg.get("plugins", {}):
            assert key in valid_plugin_keys, f"Invalid plugins key: {key}"

    def test_port_is_integer(self, fresh_manager):
        """gateway.port must be an integer, not a string.
        Source: types.gateway.ts:215 — port?: number
        """
        cfg = self._generate(fresh_manager, port=29050)
        assert isinstance(cfg["gateway"]["port"], int)
        assert cfg["gateway"]["port"] == 29050

    def test_bind_is_string_enum(self, fresh_manager):
        """gateway.bind must be one of the GatewayBindMode values.
        Source: types.gateway.ts:1 — "auto"|"lan"|"loopback"|"custom"|"tailnet"
        """
        cfg = self._generate(fresh_manager)
        assert cfg["gateway"]["bind"] in ("auto", "lan", "loopback", "custom", "tailnet")

    def test_no_models_default(self, fresh_manager):
        """models.default is NOT a valid key in ModelsConfig.
        Source: types.models.ts — ModelsConfig has: mode, providers, bedrockDiscovery
        """
        cfg = self._generate(fresh_manager)
        if "models" in cfg:
            assert "default" not in cfg["models"], \
                "models.default is invalid — use agents.defaults.model instead"

    def test_agents_defaults_model_is_object(self, fresh_manager):
        """agents.defaults.model must be an object with 'primary'.
        Source: zod-schema.agent-defaults.ts — model is z.object({primary,fallbacks}).strict()
        """
        cfg = self._generate(fresh_manager)
        model = cfg.get("agents", {}).get("defaults", {}).get("model", {})
        assert isinstance(model, dict), \
            f"agents.defaults.model must be an object, got {type(model).__name__}"
        assert "primary" in model, "agents.defaults.model must have 'primary'"
        assert model["primary"], "agents.defaults.model.primary must be non-empty"

    def test_no_top_level_agent(self, fresh_manager):
        """'agent' (singular) is NOT a valid top-level key."""
        cfg = self._generate(fresh_manager)
        assert "agent" not in cfg, "Top-level 'agent' is not valid in OpenClawConfig"

    def test_responses_endpoint_enabled(self, fresh_manager):
        """gateway.http.endpoints.responses.enabled must be true for /v1/responses."""
        cfg = self._generate(fresh_manager)
        responses = cfg["gateway"]["http"]["endpoints"]["responses"]
        assert responses["enabled"] is True
