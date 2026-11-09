"""Exercise the Core broker selection through both actual Native harness adapters."""
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "viventium_v0_4/LibreChat"
NATIVE = ROOT / "viventium_v0_4/xPerfect/runtime_phase1"


@pytest.mark.parametrize("broker_owns_browser", [False, True])
def test_core_selection_matches_both_native_harnesses(tmp_path, monkeypatch, broker_owns_browser):
    node = shutil.which("node")
    if not node or not (CORE / "packages/api/dist/index.js").is_file() or not (NATIVE / "src").is_dir():
        pytest.skip("Built Core and Native source are required")
    script = r"""
const api = require('./packages/api');
if (typeof api.composeBrokerNativeMcpConfig !== 'function') throw new Error('Build current Core first');
const allowed = JSON.parse(process.argv[1]) ? ['owned-browser'] : [];
const ids = api.brokerOwnedNativeServerIds([
 {serverName:'owned-browser',policy:{nativeServerIds:['native-browser']}}
], allowed);
process.stdout.write(JSON.stringify({codex_config_append: api.composeBrokerNativeMcpConfig({
 brokerServerName:'scoped-broker',brokerUrl:'http://localhost:3180/mcp',
 bearerTokenEnvVar:'BROKER_TOKEN',nativeServerIds:ids,
})}));
"""
    output = subprocess.run([node, "-e", script, json.dumps(broker_owns_browser)], cwd=CORE,
                            check=True, capture_output=True, text=True, timeout=30)
    bundle = json.loads(output.stdout)
    monkeypatch.syspath_prepend(str(NATIVE / "src"))
    from workers_projects_runtime.profile_runtime import HostClaudeCodeRuntime
    owner = tmp_path / "owner"
    home = owner / ".codex"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(owner))
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("GLASSHIVE_HOST_CODEX_NATIVE_MCP_ALLOWLIST", "native-browser,other-native")
    monkeypatch.setenv("GLASSHIVE_HOST_PLUGIN_DENYLIST", "")
    monkeypatch.setenv("WPR_HOST_PLUGIN_DENYLIST", "")
    monkeypatch.setenv("WPR_CODEX_CLI_PERSONALITY", "inherit")
    original = ('[mcp_servers.native-browser]\ncommand="/synthetic/browser"\n'
                '[mcp_servers.other-native]\ncommand="/synthetic/other"\n')
    source = home / "config.toml"
    source.write_text(original)
    runtime = HostClaudeCodeRuntime(base_dir=str(tmp_path / "state"))
    codex = tomllib.loads(runtime._host_codex_worker_config(bundle["codex_config_append"]))["mcp_servers"]
    broker = {"type": "http", "url": "http://localhost:3180/mcp"}
    claude, _ = runtime._host_claude_project_mcp_payload(bundle, {"scoped-broker": broker})
    claude_servers = claude["mcpServers"]
    assert (codex["native-browser"].get("enabled") is False) is broker_owns_browser
    assert ("native-browser" not in claude_servers) is broker_owns_browser
    assert codex["other-native"]["command"] == "/synthetic/other"
    assert claude_servers["other-native"]["command"] == "/synthetic/other"
    assert "scoped-broker" in codex and claude_servers["scoped-broker"] == broker
    assert source.read_text() == original
