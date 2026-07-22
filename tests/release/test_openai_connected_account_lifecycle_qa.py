from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = (
    REPO_ROOT
    / "qa"
    / "installer-resilience"
    / "scripts"
    / "openai-connected-account-lifecycle-qa.cjs"
)
README = REPO_ROOT / "qa" / "installer-resilience" / "README.md"
CASES = REPO_ROOT / "qa" / "installer-resilience" / "cases.md"
REPORT = (
    REPO_ROOT
    / "qa"
    / "installer-resilience"
    / "reports"
    / "2026-07-20-synthetic-openai-connected-account-lifecycle-qa.md"
)


def test_openai_lifecycle_harness_exercises_required_local_only_contract() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    for required_contract in (
        "assertLoopbackUrl",
        "auth.openai.com/oauth/authorize",
        "VIVENTIUM_QA_PROVIDER_PORT",
        "VIVENTIUM_QA_RESTART_ARGV_JSON",
        "externalNetworkAttempts",
        "authorization_denied",
        "popup_cancelled",
        "first_useful_answer",
        "second_useful_answer",
        "browser_refresh_persistence",
        "runtime_restart_persistence",
        "proactive_expiry_refresh",
        "early_401_refresh",
        "failed_refresh_reconnect_guidance",
        "local_disconnect",
        "disconnect_answer_refusal",
        "regrant_after_disconnect",
        "providerRevocation",
        "/api/keys/",
        "<private>",
        'page.locator("form#f")',
        'input[name="confirm_password"]',
        'name: "Create admin"',
    ):
        assert required_contract in source

    assert "context.route('**/*'" in source
    assert "mkdtempSync" in source
    assert "process.env.CI" in source
    assert "process.env.NODE_ENV" in source
    assert "production" in source
    assert "/oauth/revoke" not in source
    assert "VIVENTIUM_OPENAI_OAUTH_REVOKE_URL" not in source
    assert "revokeRequests" not in source


def test_openai_lifecycle_provider_stub_self_test_is_sanitized() -> None:
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
        "provider": "synthetic-loopback",
        "authorizationCodeExchanges": 1,
        "refreshExchanges": 1,
        "responsesRequests": 1,
        "providerRevocation": "unsupported",
        "evidenceDirectory": "<private>",
    }
    assert "access_token" not in result.stdout
    assert "refresh_token" not in result.stdout
    assert "state=" not in result.stdout


def test_openai_lifecycle_harness_rejects_non_loopback_and_ci_targets() -> None:
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


def test_openai_lifecycle_qa_docs_keep_unrun_browser_truth_visible() -> None:
    readme = README.read_text(encoding="utf-8")
    cases = CASES.read_text(encoding="utf-8")
    report = REPORT.read_text(encoding="utf-8")

    for content in (readme, cases, report):
        assert "openai-connected-account-lifecycle-qa.cjs" in content
    for runtime_setting in (
        "VIVENTIUM_OPENAI_OAUTH_TOKEN_URL",
        "VIVENTIUM_OPENAI_CODEX_BASE_URL",
        "VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH",
    ):
        assert runtime_setting in readme
    assert "not the Easy Install default" in readme
    assert "VIVENTIUM_OPENAI_OAUTH_REVOKE_URL" not in readme
    assert "provider-side revocation is unsupported" in readme.lower()
    assert "provider-side revocation is unsupported" in cases.lower()
    assert "provider-side revocation is unsupported" in report.lower()
    assert "Browser lifecycle: **NOT RUN**" in report
    assert "integrated LibreChat candidate" in report
    assert "no real provider" in report.lower()
    assert "PARTIAL" in cases
