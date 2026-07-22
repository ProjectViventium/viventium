from __future__ import annotations

from e2b_runtime import (
    E2BRuntimeAdapter,
    OPENCLAW_E2B_RUNTIME_ROOT,
    OPENCLAW_REQUIRED_NODE_VERSION,
    OPENCLAW_REQUIRED_VERSION,
    OPENCLAW_RUNTIME_LOCK_SHA256,
)


def test_bootstrap_requires_reviewed_lock_binary_node_and_private_discovery(monkeypatch) -> None:
    monkeypatch.setattr(E2BRuntimeAdapter, "_load_sdk_modules", lambda self: None)
    adapter = E2BRuntimeAdapter(gateway_port=18789, default_model="synthetic/model")

    script = adapter._build_bootstrap_script(vm_id="001", gateway_token="synthetic-token")

    assert OPENCLAW_REQUIRED_VERSION in script
    assert OPENCLAW_REQUIRED_NODE_VERSION in script
    assert OPENCLAW_RUNTIME_LOCK_SHA256 in script
    assert f"{OPENCLAW_E2B_RUNTIME_ROOT}/package-lock.json" in script
    assert f"{OPENCLAW_E2B_RUNTIME_ROOT}/node_modules/.bin/openclaw" in script
    assert "OPENCLAW_DISABLE_BONJOUR=1" in script
    assert "npm install" not in script
    assert "openclaw@latest" not in script
