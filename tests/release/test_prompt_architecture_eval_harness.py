from __future__ import annotations

import os
import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "run-exact-model-evals.cjs"
NATIVE_SURFACE_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "run-native-surface-playwright-qa.cjs"
)
VISIBLE_CARDS_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-visible-cards-browser-qa.cjs"
)
LATEST_USER_ACTIVATION_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-latest-user-activation-browser-qa.cjs"
)
AGENT_CLIENT_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "controllers"
    / "agents"
    / "client.js"
)
BACKGROUND_CORTEX_SERVICE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "BackgroundCortexService.js"
)
BACKGROUND_CORTEX_FOLLOWUP_SERVICE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "BackgroundCortexFollowUpService.js"
)


def test_exact_model_eval_harness_fails_closed_when_runtime_is_unreachable(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"

    result = subprocess.run(
        [
            "node",
            str(EVAL_SCRIPT),
            "--api-base=http://127.0.0.1:65535",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    private_json = private_dir / "exact-model-eval.json"
    assert private_json.exists(), result.stderr
    assert public_report.exists(), result.stderr

    payload = json.loads(private_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["blockedReason"].startswith("api_health_http_")

    public_text = public_report.read_text(encoding="utf-8")
    assert "Status: blocked" in public_text
    assert str(tmp_path) not in public_text
    assert "127.0.0.1:65535" not in public_text


def test_exact_model_eval_harness_does_not_embed_local_password() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"Viventium[A-Za-z0-9_-]*![0-9]{4}", script_text) is None
    allowed_password_lines = {
        "const QA_PASSWORD_ENV = 'VIVENTIUM_QA_PASSWORD';",
        "const password = process.env[QA_PASSWORD_ENV];",
        "if (!password) {",
        "reason: `missing_${QA_PASSWORD_ENV}`,",
        "password,",
    }
    unexpected = [
        line.strip()
        for line in script_text.splitlines()
        if "password" in line.lower() and line.strip() not in allowed_password_lines
    ]
    assert unexpected == []


def test_exact_model_eval_harness_defaults_semantic_judge_to_local_account_route() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "const DEFAULT_JUDGE_ROUTE = process.env.VIVENTIUM_EVAL_JUDGE_ROUTE || 'local-ephemeral';" in script_text
    assert "openai-direct" in script_text
    assert "unsupported_semantic_judge_route" in script_text
    assert "local_ephemeral_json_semantic_judge" in script_text
    assert "You are not Viventium" in script_text
    assert 'Range rubric note: if a rubric says "one or two"' in script_text
    assert "Architecture-language note:" in script_text
    assert "Citation marker note:" in script_text
    assert "provider-enforced JSON Schema" in script_text
    assert "prompt-constrained JSON plus local schema validation" in script_text


def test_exact_model_eval_harness_blocks_when_prompt_debug_local_enabled(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if self.path == "/api/config":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "appTitle": "Viventium",
                            "interface": {"defaultAgent": "agent_viventium_main_95aeb3"},
                            "viventiumConnectedAccountsEnabled": True,
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        private_dir = tmp_path / "private"
        public_report = tmp_path / "public-report.md"
        env = {
            **os.environ,
            "VIVENTIUM_PROMPT_FRAME_DEBUG_LOCAL": "1",
        }

        result = subprocess.run(
            [
                "node",
                str(EVAL_SCRIPT),
                f"--api-base=http://127.0.0.1:{server.server_port}",
                f"--output-dir={private_dir}",
                f"--public-report={public_report}",
                "--no-live",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode != 0
    payload = json.loads((private_dir / "exact-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["blockedReason"] == "prompt_frame_debug_local_enabled"
    public_text = public_report.read_text(encoding="utf-8")
    assert "Prompt debug-local gate: enabled" in public_text


def test_exact_model_eval_harness_requires_local_jwt_opt_in(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if self.path == "/api/config":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "appTitle": "Viventium",
                            "interface": {"defaultAgent": "agent_viventium_main_95aeb3"},
                            "viventiumConnectedAccountsEnabled": True,
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        private_dir = tmp_path / "private"
        public_report = tmp_path / "public-report.md"
        env = {
            **os.environ,
            "VIVENTIUM_QA_PASSWORD": "",
            "VIVENTIUM_QA_ALLOW_LOCAL_JWT": "",
        }

        result = subprocess.run(
            [
                "node",
                str(EVAL_SCRIPT),
                f"--api-base=http://127.0.0.1:{server.server_port}",
                f"--output-dir={private_dir}",
                f"--public-report={public_report}",
                "--run-live",
                "--local-jwt-fallback",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode != 0
    payload = json.loads((private_dir / "exact-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["blockedReason"] == (
        "local_jwt_fallback_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT"
    )


def test_native_surface_eval_harness_requires_local_jwt_opt_in() -> None:
    script_text = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';" in script_text
    assert "Local QA JWT auth is forbidden in CI or production" in script_text
    assert "Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1" in script_text
    assert "process.env[LOCAL_JWT_ALLOW_ENV] !== '1'" in script_text


def test_visible_cards_browser_eval_installs_refreshed_access_token() -> None:
    script_text = VISIBLE_CARDS_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "async function installAccessToken(page)" in script_text
    assert "fetch('/api/auth/refresh', { method: 'POST' })" in script_text
    assert "new CustomEvent('tokenUpdated', { detail: token })" in script_text
    assert "auth_refresh_failed_status_" in script_text
    assert "sanitizePublicError" in script_text
    assert script_text.count("await installAccessToken(page);") >= 1
    assert "window.location.pathname === '/c/new'" in script_text
    assert "getByLabel('Message input')" in script_text
    assert "getByTestId('send-button').last().click" in script_text
    assert "page.keyboard.press('Enter')" not in script_text
    assert "/^\\/c\\/(?!new$)[^/?#]+/.test(window.location.pathname)" in script_text
    assert "latest.parentHasVisibleMainAnswer === true" in script_text
    assert "latest.parentCortexOnly !== true" in script_text
    assert "answer.length < 24" in script_text
    assert r".replace(/\s+([:;,.!?])/g, '$1')" in script_text
    assert "ERR_ABORTED|NS_BINDING_ABORTED|Target closed" in script_text


def test_visible_cards_browser_eval_fails_groq_first_activation_drift() -> None:
    script_text = VISIBLE_CARDS_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "const EXPECTED_ACTIVATION_PROVIDER = 'groq';" in script_text
    assert (
        "const EXPECTED_ACTIVATION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct';"
        in script_text
    )
    assert "const DEFAULT_REQUIRED_CORTEX_AGENT_IDS_BY_NAME = {" in script_text
    assert "VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON" in script_text
    assert "requiredCortexAgentIdsByName" in script_text
    assert "background_cortices: 1" in script_text
    assert "runtimeActivationDriftNames" in script_text
    assert "runtimeActivationConfigPass: activationDriftNames.length === 0" in script_text
    assert "activationDriftNames.length === 0" in script_text
    assert "Runtime activation drift agents:" in script_text
    assert "Runtime activation config pass:" in script_text


def test_latest_user_activation_browser_eval_targets_latest_turn_not_setup_text() -> None:
    script_text = LATEST_USER_ACTIVATION_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';" in script_text
    assert "direct_access_token_fallback" in script_text
    assert "await waitForSetupCards(page, args.timeoutMs);" in script_text
    assert "expectedText: args.setupExpectedText" not in script_text
    assert "setupFollowUpReady" in script_text
    assert "Setup follow-up ready:" in script_text
    assert "setupAssistantParent" not in script_text
    assert "latestScopedCortexPartCount === 0" in script_text
    assert "latestPhaseBChildVisibleTextCount === 0" in script_text


def test_latest_user_activation_browser_eval_honors_custom_expected_text() -> None:
    script_text = LATEST_USER_ACTIVATION_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "testExpectedText: process.env.VIVENTIUM_QA_TEST_EXPECTED_TEXT || 'TEST_OK'" in script_text
    assert "textIncludesExpectedAnswer" in script_text
    assert "dedupeVisibleAnswerTextParts" in script_text
    assert "return dedupeVisibleAnswerTextParts([text, partText]).join('\\n').trim();" in script_text
    assert "expectedText: args.testExpectedText" in script_text
    assert "Expected text visible before reload:" in script_text
    assert "Expected text visible after reload:" in script_text
    assert "() => /\\bTEST_OK\\b/.test(document.body.innerText || '')" not in script_text
    assert "/\\bTEST_OK\\b/.test(await visibleBodyText(page))" not in script_text


def test_background_prompt_debug_logging_uses_hashes_not_raw_previews() -> None:
    client_text = AGENT_CLIENT_PATH.read_text(encoding="utf-8")
    cortex_text = BACKGROUND_CORTEX_SERVICE_PATH.read_text(encoding="utf-8")
    followup_text = BACKGROUND_CORTEX_FOLLOWUP_SERVICE_PATH.read_text(encoding="utf-8")

    assert "function hashCompletionTextForLog" in client_text
    assert "recentResponse.hash=${hashCompletionTextForLog(recentResponse)}" in client_text
    assert "recentResponse.preview" not in client_text

    assert "function shouldLogActivationPrompt" in cortex_text
    assert "VIVENTIUM_LOG_ACTIVATION_PROMPT" in cortex_text
    assert "NODE_ENV === 'development'" not in cortex_text
    assert "function promptDebugSummaryForLog" in cortex_text
    assert "Activation prompt summary" in cortex_text
    assert "Activation raw response" in cortex_text
    assert "clampLogText" not in cortex_text

    assert "function hashFollowUpTextForLog" in followup_text
    assert "raw_hash=${hashFollowUpTextForLog(rawText)}" in followup_text
    assert "hash=${hashFollowUpTextForLog(recentResponseResolution.text)}" in followup_text
    assert "preview=" not in followup_text


def test_exact_model_eval_harness_reports_partial_coverage(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"

    result = subprocess.run(
        [
            "node",
            str(EVAL_SCRIPT),
            "--api-base=http://127.0.0.1:65535",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    public_text = public_report.read_text(encoding="utf-8")
    assert "Runnable cases for this runner:" in public_text
    assert "Selected case limit:" in public_text
    assert "Surfaces in bank:" in public_text


def test_exact_model_eval_harness_fails_duplicate_and_unresolved_holds() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "function buildDuplicateResponseQualityFailures" in script_text
    assert "caseAllowsDuplicateResponse(testCase)" in script_text
    assert "resultHasResolvedRuntimeHoldEvidence" in script_text
    assert "Duplicate response quality failures:" in script_text
    assert "function buildUnresolvedAsyncQualityFailures" in script_text
    assert "hasRuntimeHold(stream.events)" in script_text
    assert "Runtime-hold responses fail the run" in script_text
    assert "report.summary.duplicateResponseQualityFailures.length > 0" in script_text
    assert "report.summary.unresolvedAsyncQualityFailures.length > 0" in script_text
    assert "'semantic_failed'" in script_text
    assert "'quality_failed'" in script_text


def test_native_surface_eval_harness_fails_duplicate_and_unresolved_holds() -> None:
    script_text = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "function caseAllowsDuplicateResponse" in script_text
    assert "function caseAllowsUnresolvedAsync" in script_text
    assert "function hasRuntimeHold" in script_text
    assert "resultHasResolvedRuntimeHoldEvidence" in script_text
    assert "duplicateResponseQualityFailures.length === 0" in script_text
    assert "unresolvedAsyncQualityFailures.length === 0" in script_text
    assert "semanticPartial === 0" in script_text
    assert "summary.semanticPartial > 0" in script_text
    assert "Duplicate response quality failures:" in script_text
    assert "Unresolved async quality failures:" in script_text


def test_prompt_architecture_evals_wait_for_async_phase_b_followup() -> None:
    for script_path in (EVAL_SCRIPT, NATIVE_SURFACE_EVAL_SCRIPT):
        script_text = script_path.read_text(encoding="utf-8")
        assert "followUpGraceMs" in script_text
        assert "VIVENTIUM_EVAL_FOLLOWUP_GRACE_MS || '30000'" in script_text
        assert "--follow-up-grace-ms=" in script_text
        assert "awaitingAsyncFollowUp" in script_text
        assert "latest.cortexInsightCount > 0" in script_text
        assert "latest.delayedMessageCount === 0" in script_text


def test_native_surface_judge_summary_includes_web_search_source_evidence() -> None:
    for script_path in (EVAL_SCRIPT, NATIVE_SURFACE_EVAL_SCRIPT):
        script_text = script_path.read_text(encoding="utf-8")
        assert "web_search_sources" in script_text
        assert "event?.data?.type === 'web_search'" in script_text
        assert "anchor: position > 0 ? `turn${turn}search${position - 1}` : ''" in script_text
        assert "link_host" in script_text
        assert "snippet_preview" in script_text


def test_wing_mode_disables_background_cortices_for_silence_and_budget() -> None:
    client_text = AGENT_CLIENT_PATH.read_text(encoding="utf-8")
    assert "const wingModeActive = isWingModeEnabledForRequest(this.options.req, inputMode);" in client_text
    assert re.search(
        r"const hasBackgroundCortices\s*=\s*cortexDetectTimeoutMs > 0 &&\s*!suppressBackgroundCortices &&\s*!wingModeActive &&",
        client_text,
        re.S,
    )
