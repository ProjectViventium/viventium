from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = (
    REPO_ROOT
    / "qa"
    / "installer-resilience"
    / "scripts"
    / "openai-api-key-lifecycle-qa.cjs"
)


def test_api_key_lifecycle_harness_owns_the_stable_easy_install_contract() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    for required_contract in (
        "assertLoopbackUrl",
        "VIVENTIUM_QA_CLIENT_BASE",
        "VIVENTIUM_QA_PROVIDER_PORT",
        "VIVENTIUM_QA_RESTART_ARGV_JSON",
        "valid_key_first_answer",
        "valid_key_second_answer",
        "browser_refresh_persistence",
        "runtime_restart_persistence",
        "invalid_key_repair",
        "quota_repair",
        "provider_outage_repair",
        "network_failure_repair",
        "local_disconnect",
        "disconnect_prevents_provider_request",
        "missing_key_one_click_recovery",
        "valid_key_readded",
        "waitForConversationAnswer",
        'getByTestId("nav-user")',
        '"99-failure.png"',
        "response.output_item.added",
        "response.output_text.done",
        "response.output_item.done",
        "Use OpenAI API key",
        "Use Anthropic API key",
        "Use Groq API key",
        "Use Grok (xAI) API key",
        '"x-api-key"',
        "message_start",
        "content_block_delta",
        "message_stop",
        "VIVENTIUM_QA_PROVIDER",
        "parseRuntimeProviderTarget",
        "OPENAI_REVERSE_PROXY",
        "Force the disposable backend to inherit the verified loopback provider target",
        "/api/keys/",
        "externalNetworkAttempts",
        "assertBrowserCredentialAbsent",
        "context.storageState",
        "indexedDB.databases",
        "browserCredentialResidueChecks",
        "<private>",
        "const recoveryButtonsBefore = await page",
        ".nth(recoveryButtonsBefore)",
        'name: "Connected Accounts"',
        'page.keyboard.press("Enter")',
        'page.locator("form#f")',
        'input[name="confirm_password"]',
        'name: "Create admin"',
        "Saved locally — send a message to test it",
    ):
        assert required_contract in source

    assert "context.route('**/*'" in source
    assert 'response.request().method() === "PUT"' in source
    assert "mkdtempSync" in source
    assert "process.env.CI" in source
    assert "process.env.NODE_ENV" in source
    assert "oauth" not in source.lower()
    assert "VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH" not in source
    assert "Local credential saved" not in source


def test_browser_credential_residue_guard_self_test_is_fail_closed_and_sanitized() -> None:
    result = subprocess.run(
        ["node", str(HARNESS), "--storage-self-test"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert json.loads(result.stdout) == {
        "result": "PASS",
        "mode": "storage-self-test",
        "cleanStateAccepted": True,
        "localStorageLeakRejected": True,
        "indexedDbLeakRejected": True,
    }
    assert "synthetic-valid-provider-key" not in result.stdout
    assert "synthetic-invalid-provider-key" not in result.stdout


def test_api_key_provider_stub_self_test_is_sanitized() -> None:
    result = subprocess.run(
        ["node", str(HARNESS), "--self-test"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "result": "PASS",
        "mode": "self-test",
        "provider": "synthetic-openai-compatible-loopback",
        "modelsRequests": 1,
        "chatRequests": 2,
        "successfulAnswers": 1,
        "evidenceDirectory": "<private>",
    }
    assert "sk-viventium" not in result.stdout
    assert "authorization" not in result.stdout.lower()


def test_anthropic_messages_provider_stub_self_test_is_sanitized() -> None:
    result = subprocess.run(
        ["node", str(HARNESS), "--self-test"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "VIVENTIUM_QA_PROVIDER": "anthropic"},
        timeout=30,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "result": "PASS",
        "mode": "self-test",
        "provider": "synthetic-anthropic-compatible-loopback",
        "modelsRequests": 0,
        "chatRequests": 2,
        "successfulAnswers": 1,
        "evidenceDirectory": "<private>",
    }
    assert "synthetic-valid-provider-key" not in result.stdout
    assert "x-api-key" not in result.stdout.lower()


def test_api_key_lifecycle_harness_rejects_non_loopback_and_ci_targets() -> None:
    base_env = {
        **os.environ,
        "VIVENTIUM_QA_CLIENT_BASE": "https://example.com",
        "VIVENTIUM_QA_EMAIL": "synthetic@example.invalid",
        "VIVENTIUM_QA_PASSWORD": "synthetic-password",
    }
    non_loopback = subprocess.run(
        ["node", str(HARNESS), "--contract-check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=base_env,
        timeout=30,
    )
    assert non_loopback.returncode != 0
    assert "loopback" in non_loopback.stderr.lower()

    ci = subprocess.run(
        ["node", str(HARNESS), "--contract-check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={
            **base_env,
            "VIVENTIUM_QA_CLIENT_BASE": "http://127.0.0.1:3190",
            "CI": "1",
        },
        timeout=30,
    )
    assert ci.returncode != 0
    assert "ci/production" in ci.stderr.lower()


def test_api_key_lifecycle_harness_requires_backend_loopback_provider_target() -> None:
    base_env = {
        **os.environ,
        "VIVENTIUM_QA_CLIENT_BASE": "http://127.0.0.1:3190",
        "VIVENTIUM_QA_EMAIL": "synthetic@example.invalid",
        "VIVENTIUM_QA_PASSWORD": "synthetic-password",
        "VIVENTIUM_QA_PROVIDER_PORT": "14661",
    }
    missing = subprocess.run(
        ["node", str(HARNESS), "--contract-check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**base_env, "OPENAI_REVERSE_PROXY": ""},
        timeout=30,
    )
    assert missing.returncode != 0
    assert "OPENAI_REVERSE_PROXY" in missing.stderr

    external = subprocess.run(
        ["node", str(HARNESS), "--contract-check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**base_env, "OPENAI_REVERSE_PROXY": "https://api.example.com/v1"},
        timeout=30,
    )
    assert external.returncode != 0
    assert "loopback" in external.stderr.lower()


def test_browser_launch_failure_releases_the_synthetic_provider_port(
    tmp_path: Path,
) -> None:
    playwright_fixture = tmp_path / "playwright-fixture.cjs"
    playwright_fixture.write_text(
        "module.exports = { chromium: { launch: async () => { throw new Error(\"Executable doesn't exist at <synthetic>\"); } } };\n",
        encoding="utf-8",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        provider_port = probe.getsockname()[1]

    result = subprocess.run(
        ["node", str(HARNESS)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "empty-playwright-cache"),
            "VIVENTIUM_QA_CLIENT_BASE": "http://127.0.0.1:3190",
            "VIVENTIUM_QA_EMAIL": "synthetic@example.invalid",
            "VIVENTIUM_QA_PASSWORD": "synthetic-password",
            "VIVENTIUM_QA_PROVIDER_PORT": str(provider_port),
            "OPENAI_REVERSE_PROXY": f"http://127.0.0.1:{provider_port}/v1",
            "VIVENTIUM_QA_RESTART_ARGV_JSON": '["/usr/bin/true"]',
            "VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR": str(tmp_path / "evidence"),
            "VIVENTIUM_QA_PLAYWRIGHT_MODULE": str(playwright_fixture),
        },
        timeout=30,
    )

    assert result.returncode != 0
    assert "executable doesn't exist" in result.stderr.lower()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reuse:
        reuse.bind(("127.0.0.1", provider_port))
