# VIVENTIUM START
# Tests for the Viventium Channel Bridge OpenClaw plugin.
#
# Validates:
#   - Plugin manifest filename: openclaw.plugin.json (NOT clawdbot.plugin.json)
#   - Plugin manifest has required fields: id, configSchema
#   - Plugin exports match OpenClawPluginDefinition
#   - No reference to api.tools.invoke (does not exist on OpenClawPluginApi)
# VIVENTIUM END

import json
from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).parent.parent / "viventium-channel-plugin"


class TestPluginManifest:
    """Validate plugin manifest matches OpenClaw's requirements.

    Source: openclaw/src/plugins/manifest.ts
    - Filename: openclaw.plugin.json (line 7: PLUGIN_MANIFEST_FILENAME)
    - Required: id (string), configSchema (object) (lines 62-69)
    """

    def test_manifest_filename(self):
        """Manifest MUST be openclaw.plugin.json.
        Source: manifest.ts:7 — PLUGIN_MANIFEST_FILENAME = "openclaw.plugin.json"
        """
        assert (PLUGIN_DIR / "openclaw.plugin.json").exists()
        # Old incorrect filename should NOT exist
        assert not (PLUGIN_DIR / "clawdbot.plugin.json").exists()

    def test_manifest_is_valid_json(self):
        manifest = json.loads((PLUGIN_DIR / "openclaw.plugin.json").read_text())
        assert isinstance(manifest, dict)

    def test_manifest_has_required_id(self):
        """id is required and must be a non-empty string.
        Source: manifest.ts:62-63
        """
        manifest = json.loads((PLUGIN_DIR / "openclaw.plugin.json").read_text())
        assert "id" in manifest
        assert isinstance(manifest["id"], str)
        assert manifest["id"].strip() != ""

    def test_manifest_has_required_config_schema(self):
        """configSchema is required and must be an object.
        Source: manifest.ts:66-69
        """
        manifest = json.loads((PLUGIN_DIR / "openclaw.plugin.json").read_text())
        assert "configSchema" in manifest
        assert isinstance(manifest["configSchema"], dict)

    def test_manifest_config_schema_has_type(self):
        """configSchema should be a JSON Schema object."""
        manifest = json.loads((PLUGIN_DIR / "openclaw.plugin.json").read_text())
        schema = manifest["configSchema"]
        assert schema.get("type") == "object"


class TestPluginSource:
    """Validate plugin TypeScript source uses correct APIs."""

    def test_source_exists(self):
        assert (PLUGIN_DIR / "index.ts").exists()

    def test_no_api_tools_invoke(self):
        """Plugin must NOT call api.tools.invoke — this does not exist.
        Source: types.ts OpenClawPluginApi (lines 244-283) — no tools.invoke method
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "api.tools.invoke" not in source

    def test_uses_typed_hook_api(self):
        """Plugin should use api.on() for typed hooks.
        Source: types.ts:278 — on<K extends PluginHookName>(hookName, handler)
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "api.on(" in source

    def test_hooks_message_received(self):
        """Plugin should hook into message_received.
        Source: types.ts:304 — "message_received" is a valid PluginHookName
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "'message_received'" in source or '"message_received"' in source

    def test_hooks_gateway_start(self):
        """Plugin should hook into gateway_start.
        Source: types.ts:311 — "gateway_start" is a valid PluginHookName
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "'gateway_start'" in source or '"gateway_start"' in source

    def test_uses_correct_librechat_endpoint(self):
        """Plugin should call generic gateway chat endpoint.
        Source: /api/viventium/gateway/chat
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "/api/viventium/gateway/chat" in source
        assert "/api/agents/v1/responses" not in source
        assert "/api/ask/agent" not in source

    def test_sends_responses_via_tools_invoke(self):
        """Plugin should send messages back via POST /tools/invoke on gateway."""
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "/tools/invoke" in source

    def test_uses_bearer_auth_for_gateway(self):
        """Gateway calls should use Bearer token auth."""
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "Bearer" in source

    def test_exports_plugin_definition(self):
        """Plugin should export an OpenClawPluginDefinition-compatible object.
        Source: types.ts:229-238 — OpenClawPluginDefinition
        """
        source = (PLUGIN_DIR / "index.ts").read_text()
        assert "register" in source  # Required method
        assert "export default" in source
