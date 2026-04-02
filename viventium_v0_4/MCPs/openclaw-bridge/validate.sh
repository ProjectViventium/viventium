#!/usr/bin/env bash
# VIVENTIUM START
# Validates the OpenClaw Bridge setup against REAL OpenClaw contracts.
# Usage: bash validate.sh [--integration]
# VIVENTIUM END

set -euo pipefail

PASS=0
FAIL=0
SKIP=0

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ✗ $1"; }
skip() { SKIP=$((SKIP + 1)); echo "  ○ $1 (skipped)"; }

echo "═══════════════════════════════════════════════"
echo " OpenClaw Bridge — Validation Suite"
echo "═══════════════════════════════════════════════"

BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BRIDGE_DIR"

# ------- Prerequisites -------
echo ""
echo "▸ Prerequisites"

if command -v python3 &>/dev/null; then
    pass "Python 3 available ($(python3 --version 2>&1))"
else
    fail "Python 3 not found"
fi

if command -v node &>/dev/null; then
    pass "Node.js available ($(node --version 2>&1))"
else
    skip "Node.js not found"
fi

if command -v openclaw &>/dev/null; then
    pass "OpenClaw binary found"
else
    skip "OpenClaw binary not found (npm install -g openclaw)"
fi

# ------- Python Dependencies -------
echo ""
echo "▸ Python Dependencies"

for pkg in httpx fastmcp pytest; do
    if python3 -c "import $pkg" 2>/dev/null; then
        pass "$pkg importable"
    else
        fail "$pkg not importable (pip install -r requirements.txt)"
    fi
done

# ------- File Structure -------
echo ""
echo "▸ File Structure"

for f in mcp_server.py openclaw_manager.py requirements.txt pytest.ini README.md Dockerfile docker-compose.yml; do
    if [ -f "$f" ]; then
        pass "$f exists"
    else
        fail "$f missing"
    fi
done

for d in tests viventium-channel-plugin; do
    if [ -d "$d" ]; then
        pass "$d/ directory exists"
    else
        fail "$d/ directory missing"
    fi
done

# ------- Plugin Manifest -------
echo ""
echo "▸ Plugin Manifest (openclaw.plugin.json)"

MANIFEST="viventium-channel-plugin/openclaw.plugin.json"
if [ -f "$MANIFEST" ]; then
    pass "openclaw.plugin.json exists (correct filename)"
else
    fail "openclaw.plugin.json missing — OpenClaw requires this filename"
fi

OLD_MANIFEST="viventium-channel-plugin/clawdbot.plugin.json"
if [ -f "$OLD_MANIFEST" ]; then
    fail "clawdbot.plugin.json still exists (wrong filename, delete it)"
else
    pass "No legacy clawdbot.plugin.json"
fi

if [ -f "$MANIFEST" ]; then
    if python3 -c "import json; m=json.load(open('$MANIFEST')); assert m.get('id'), 'missing id'; assert isinstance(m.get('configSchema'), dict), 'missing configSchema'" 2>/dev/null; then
        pass "Manifest has required fields (id, configSchema)"
    else
        fail "Manifest missing required fields (id, configSchema)"
    fi
fi

# ------- Contract Checks -------
echo ""
echo "▸ Contract Checks (vs OpenClaw source)"

# Single port model
if python3 -c "
from openclaw_manager import OpenClawInstance
i = OpenClawInstance(user_id='t', port=18800)
assert not hasattr(i, 'gateway_port'), 'should not have gateway_port'
assert not hasattr(i, 'http_port'), 'should not have http_port'
assert i.port == 18800
assert '18800' in i.tools_invoke_url
assert '18800' in i.responses_url
" 2>/dev/null; then
    pass "Single port model (no split gateway/http ports)"
else
    fail "Port model incorrect — should be single port"
fi

# Config schema
if python3 -c "
import json, tempfile
from pathlib import Path
import openclaw_manager as m
from unittest.mock import patch
with tempfile.TemporaryDirectory() as td:
    p = Path(td)
    (p / 'workspace').mkdir()
    with patch.object(m, 'DATA_DIR', p), \
         patch.object(m, 'LOG_DIR', p), \
         patch.object(m, 'OPENCLAW_BRIDGE_AUTH_TOKEN', 'test'), \
         patch.object(m, 'OPENCLAW_MODEL', 'test/model'):
        mgr = m.OpenClawManager()
        cp = mgr._generate_config('user1', p, 18800)
        cfg = json.loads(cp.read_text())
        assert cp.name == 'openclaw.json', f'wrong filename: {cp.name}'
        assert 'agent' not in cfg, 'should not have top-level agent'
        assert cfg['gateway']['port'] == 18800, 'wrong port'
        assert isinstance(cfg['gateway']['port'], int), 'port must be int'
        bind = cfg['gateway']['bind']
        assert bind in ('auto','lan','loopback','custom','tailnet'), f'bad bind: {bind}'
        assert ':' not in bind, 'bind should be mode, not IP:PORT'
" 2>/dev/null; then
    pass "Config matches OpenClawConfig schema"
else
    fail "Config schema mismatch"
fi

# No /health endpoint check
if grep -q '"/health"' openclaw_manager.py 2>/dev/null; then
    fail "openclaw_manager.py references /health (does not exist on OpenClaw)"
else
    pass "No /health HTTP endpoint reference in manager"
fi

if grep -q 'tools/invoke' openclaw_manager.py 2>/dev/null; then
    pass "Readiness probe uses /tools/invoke"
else
    fail "Readiness probe should use /tools/invoke"
fi

# MCP server security
if python3 -c "
from mcp_server import MCP_HOST
assert MCP_HOST == '127.0.0.1', f'Default host should be loopback, got {MCP_HOST}'
" 2>/dev/null; then
    pass "MCP server defaults to loopback (127.0.0.1)"
else
    fail "MCP server should default to 127.0.0.1"
fi

# Plugin source checks
echo ""
echo "▸ Plugin Source Checks"

PLUGIN_SRC="viventium-channel-plugin/index.ts"
if [ -f "$PLUGIN_SRC" ]; then
    if grep -q 'api\.tools\.invoke' "$PLUGIN_SRC" 2>/dev/null; then
        fail "Plugin uses api.tools.invoke (does not exist on OpenClawPluginApi)"
    else
        pass "No api.tools.invoke usage"
    fi

    if grep -q 'api\.on(' "$PLUGIN_SRC" 2>/dev/null; then
        pass "Uses typed hook API (api.on)"
    else
        fail "Should use api.on() for hooks"
    fi

    if grep -q '/api/agents/v1/responses' "$PLUGIN_SRC" 2>/dev/null; then
        pass "Uses correct LibreChat endpoint (/api/agents/v1/responses)"
    else
        fail "Should use /api/agents/v1/responses"
    fi

    if grep -q '/api/ask/agent' "$PLUGIN_SRC" 2>/dev/null; then
        fail "References non-existent /api/ask/agent endpoint"
    else
        pass "No reference to non-existent /api/ask/agent"
    fi
else
    fail "Plugin source not found"
fi

# ------- Unit Tests -------
echo ""
echo "▸ Unit Tests"

if python3 -m pytest tests/ -v -m "not integration" -x 2>&1; then
    pass "All unit tests passed"
else
    fail "Some unit tests failed"
fi

# ------- Integration Tests (optional) -------
if [ "${1:-}" = "--integration" ]; then
    echo ""
    echo "▸ Integration Tests"
    if curl -sf http://127.0.0.1:8086/health >/dev/null 2>&1; then
        python3 -m pytest tests/ -v -m integration 2>&1 || true
    else
        skip "Bridge server not running (start with: python mcp_server.py)"
    fi
fi

# ------- Summary -------
echo ""
echo "═══════════════════════════════════════════════"
echo " Results: $PASS passed, $FAIL failed, $SKIP skipped"
echo "═══════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
