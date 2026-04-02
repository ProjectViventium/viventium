# VIVENTIUM START
# E2E Setup — verifies prerequisites, creates LibreChat API key, and
# outputs an .env.e2e file with all values needed for the live E2E suite.
#
# Usage:
#   cd viventium_v0_4/MCPs/openclaw-bridge
#   python tests/e2e_setup.py
#
# The script will:
#   1. Verify .env.local is loadable (API keys present)
#   2. Verify LibreChat is running at localhost:3080
#   3. Log in and create an Agent API key
#   4. Verify the OpenClaw binary is runnable
#   5. Write tests/.env.e2e with all resolved values
# VIVENTIUM END

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

# ── Paths ──────────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # viventium_core
ENV_LOCAL = WORKSPACE_ROOT / ".env.local"
BRIDGE_DIR = Path(__file__).resolve().parent.parent
ENV_E2E = Path(__file__).resolve().parent / ".env.e2e"
OPENCLAW_DIR = WORKSPACE_ROOT / "viventium_v0_4" / "openclaw"
OPENCLAW_BIN = OPENCLAW_DIR / "openclaw.mjs"

# ── LibreChat ──────────────────────────────────────────────────────────
LIBRECHAT_URL = "http://localhost:3080"


def _load_env_local() -> dict[str, str]:
    """Parse .env.local into a dict (handles simple KEY=VALUE, ignores comments)."""
    env = {}
    if not ENV_LOCAL.exists():
        return env
    for line in ENV_LOCAL.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments (but not inside quotes)
        if "#" in line:
            m = re.match(r'^([^#]*?["\'].*?["\'])?([^#]*?)(?:\s*#.*)$', line)
            if m:
                line = (m.group(1) or "") + (m.group(2) or "")
                line = line.strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env[key] = value
    return env


def check_env_local() -> dict[str, str]:
    """Verify .env.local exists and has required keys."""
    print("\n[1/5] Checking .env.local ...")
    env = _load_env_local()
    if not env:
        print(f"  FAIL: Cannot load {ENV_LOCAL}")
        sys.exit(1)

    required = ["ANTHROPIC_API_KEY"]
    for key in required:
        if not env.get(key):
            print(f"  FAIL: Missing required key '{key}' in .env.local")
            sys.exit(1)
        # Mask key for display
        val = env[key]
        masked = val[:8] + "..." + val[-4:] if len(val) > 16 else val[:4] + "..."
        print(f"  OK: {key} = {masked}")

    optional = ["OPENAI_API_KEY", "XAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
    for key in optional:
        if env.get(key):
            print(f"  OK: {key} = (present)")

    return env


def check_librechat() -> bool:
    """Verify LibreChat is running and reachable."""
    print("\n[2/5] Checking LibreChat at", LIBRECHAT_URL, "...")
    try:
        resp = httpx.get(f"{LIBRECHAT_URL}/api/health", timeout=5)
        if resp.status_code == 200:
            print(f"  OK: LibreChat health → {resp.status_code}")
            return True
        print(f"  WARN: LibreChat returned HTTP {resp.status_code}")
        return True  # Still up, just different status
    except httpx.ConnectError:
        print("  FAIL: Cannot connect to LibreChat. Is it running?")
        print("  Run: cd viventium_v0_4 && ./viventium-librechat-start.sh")
        return False


def create_librechat_api_key(email: str, password: str) -> str | None:
    """Log in to LibreChat and create an Agent API key."""
    print("\n[3/5] Creating LibreChat Agent API key ...")

    # Step 1: Login to get JWT
    try:
        resp = httpx.post(
            f"{LIBRECHAT_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"  FAIL: Login failed (HTTP {resp.status_code}): {resp.text[:200]}")
            return None
        jwt_token = resp.json().get("token")
        if not jwt_token:
            print("  FAIL: No token in login response")
            return None
        print("  OK: Logged in to LibreChat")
    except Exception as e:
        print(f"  FAIL: Login error: {e}")
        return None

    # Step 2: Create Agent API key
    try:
        resp = httpx.post(
            f"{LIBRECHAT_URL}/api/api-keys",
            json={"name": "openclaw-bridge-e2e-test"},
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            # The key is returned in the response — save it
            api_key = data.get("key") or data.get("apiKey") or data.get("value")
            if api_key:
                print(f"  OK: Created API key: {api_key[:12]}...")
                return api_key
            else:
                print(f"  WARN: Key created but couldn't extract value: {json.dumps(data)[:200]}")
                return None
        else:
            print(f"  FAIL: API key creation failed (HTTP {resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  FAIL: API key creation error: {e}")
        return None


def check_openclaw_binary() -> str | None:
    """Verify the OpenClaw binary is runnable."""
    print("\n[4/5] Checking OpenClaw binary ...")

    # Check local build first
    if OPENCLAW_BIN.exists():
        bin_path = f"node {OPENCLAW_BIN}"
        try:
            result = subprocess.run(
                ["node", str(OPENCLAW_BIN), "--version"],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "OPENCLAW_STATE_DIR": "/tmp/openclaw-version-check"},
            )
            # Version is usually the last line (errors print before it)
            version_line = result.stdout.strip().split("\n")[-1] if result.stdout else ""
            if result.returncode == 0 and version_line:
                print(f"  OK: OpenClaw {version_line} (local build)")
                return bin_path
        except Exception as e:
            print(f"  WARN: Local build failed: {e}")

    # Check global install
    try:
        result = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[-1]
            print(f"  OK: OpenClaw {version} (global)")
            return "openclaw"
    except FileNotFoundError:
        pass

    print("  FAIL: OpenClaw binary not found")
    print(f"  Expected at: {OPENCLAW_BIN}")
    print("  Or install globally: npm install -g openclaw")
    return None


def write_env_e2e(env: dict[str, str], api_key: str | None, openclaw_bin: str):
    """Write the .env.e2e file with all resolved values."""
    print("\n[5/5] Writing .env.e2e ...")

    lines = [
        "# Auto-generated by e2e_setup.py — do not commit",
        f"ANTHROPIC_API_KEY={env.get('ANTHROPIC_API_KEY', '')}",
        f"OPENAI_API_KEY={env.get('OPENAI_API_KEY', '')}",
        f"XAI_API_KEY={env.get('XAI_API_KEY', '')}",
        f"GROQ_API_KEY={env.get('GROQ_API_KEY', '')}",
        f"OPENROUTER_API_KEY={env.get('OPENROUTER_API_KEY', '')}",
        f"GEMINI_API_KEY={env.get('GEMINI_API_KEY', '')}",
        f"DEEPSEEK_API_KEY={env.get('DEEPSEEK_API_KEY', '')}",
        "",
        f"OPENCLAW_BIN={openclaw_bin}",
        "OPENCLAW_BRIDGE_AUTH_TOKEN=viventium-bridge-e2e",
        "OPENCLAW_MODEL=anthropic/claude-sonnet-4-20250514",
        "OPENCLAW_PORT_START=18900",
        "OPENCLAW_PORT_END=18950",
        "OPENCLAW_READINESS_TIMEOUT=60",
        "",
        f"LIBRECHAT_URL={LIBRECHAT_URL}",
        f"VIVENTIUM_MAIN_AGENT_ID={env.get('VIVENTIUM_MAIN_AGENT_ID', 'agent_viventium_main_95aeb3')}",
    ]
    if api_key:
        lines.append(f"LIBRECHAT_AGENT_API_KEY={api_key}")
    else:
        lines.append("# LIBRECHAT_AGENT_API_KEY=  (could not create — set manually)")

    ENV_E2E.write_text("\n".join(lines) + "\n")
    print(f"  OK: Written to {ENV_E2E}")


def main():
    print("=" * 60)
    print("OpenClaw Bridge — E2E Setup")
    print("=" * 60)

    # 1. Load .env.local
    env = check_env_local()

    # 2. Check LibreChat
    lc_ok = check_librechat()

    # 3. Create API key (only if LibreChat is up)
    api_key = None
    if lc_ok:
        email = env.get("VIVENTIUM_TELEGRAM_USER_EMAIL", "")
        if not email:
            print("  SKIP: No VIVENTIUM_TELEGRAM_USER_EMAIL in .env.local")
            print("  Set LIBRECHAT_AGENT_API_KEY manually in .env.e2e")
        else:
            # Prompt for password (not stored in .env.local)
            password = input(f"\n  Enter LibreChat password for {email}: ").strip()
            if password:
                api_key = create_librechat_api_key(email, password)
            else:
                print("  SKIP: No password provided")
    else:
        print("  SKIP: LibreChat not running — set LIBRECHAT_AGENT_API_KEY manually")

    # 4. Check OpenClaw binary
    openclaw_bin = check_openclaw_binary()
    if not openclaw_bin:
        sys.exit(1)

    # 5. Write .env.e2e
    write_env_e2e(env, api_key, openclaw_bin)

    print("\n" + "=" * 60)
    print("Setup complete!")
    print()
    print("Run E2E tests:")
    print("  cd viventium_v0_4/MCPs/openclaw-bridge")
    print("  python -m pytest tests/test_e2e_live.py -v -s")
    print("=" * 60)


if __name__ == "__main__":
    main()
