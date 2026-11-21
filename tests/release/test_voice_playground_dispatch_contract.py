import json
import os
import re
import sqlite3
import subprocess
import textwrap
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_shared_voice_capability_contracts_match_librechat_mirrors() -> None:
    parent = ROOT / "viventium_v0_4" / "shared" / "voice"
    librechat = ROOT / "viventium_v0_4" / "LibreChat" / "shared" / "voice"

    for name in (
        "tts_provider_capabilities.json",
        "cartesia_sonic3_capabilities.json",
        "xai_tts_capabilities.json",
    ):
        assert (librechat / name).read_bytes() == (parent / name).read_bytes(), name


_agent_starter_react_dir = Path(
    os.environ.get("VIVENTIUM_AGENT_STARTER_REACT_DIR", ROOT / "viventium_v0_4" / "agent-starter-react")
).expanduser()
AGENT_STARTER_REACT_ROOT = (
    _agent_starter_react_dir
    if _agent_starter_react_dir.is_absolute()
    else ROOT / _agent_starter_react_dir
).resolve()
# This contract reads the checked-out component for fast local review. Release readiness still
# requires components.lock.json to pin the merged component commit that clean installs will fetch.
APP_FILE = AGENT_STARTER_REACT_ROOT / "components" / "app" / "app.tsx"
AGENT_STARTER_PACKAGE = AGENT_STARTER_REACT_ROOT / "package.json"
AGENT_STARTER_LOCK = AGENT_STARTER_REACT_ROOT / "pnpm-lock.yaml"
CONNECTION_RECOVERY_HOOK_FILE = (
    AGENT_STARTER_REACT_ROOT / "hooks" / "useConnectionRecovery.ts"
)
CALL_SESSION_STATE_HOOK_FILE = (
    AGENT_STARTER_REACT_ROOT / "hooks" / "useCallSessionState.ts"
)
CALL_SESSION_VOICE_SETTINGS_HOOK_FILE = (
    AGENT_STARTER_REACT_ROOT / "hooks" / "useCallSessionVoiceSettings.ts"
)
VOICE_ROUTE_HOOK_FILE = AGENT_STARTER_REACT_ROOT / "hooks" / "useVoiceRoute.ts"
ROUTE_FILE = AGENT_STARTER_REACT_ROOT / "app" / "api" / "connection-details" / "route.ts"
CALL_START_HOOK_FILE = AGENT_STARTER_REACT_ROOT / "hooks" / "useCallStart.ts"
CALL_SESSION_VOICE_SETTINGS_ROUTE_FILE = (
    AGENT_STARTER_REACT_ROOT / "app" / "api" / "call-session-voice-settings" / "route.ts"
)
AUTHORITATIVE_CALL_SESSION_FILE = (
    AGENT_STARTER_REACT_ROOT / "lib" / "authoritative-call-session.ts"
)
NEXT_CONFIG_FILE = AGENT_STARTER_REACT_ROOT / "next.config.ts"
TS_CONFIG_FILE = AGENT_STARTER_REACT_ROOT / "tsconfig.json"
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
VOICE_GATEWAY_WORKER = ROOT / "viventium_v0_4" / "voice-gateway" / "worker.py"
RETIRED_XAI_VOICE_AGENT_ADAPTER = (
    ROOT / "viventium_v0_4" / "voice-gateway" / "xai_grok_voice_tts.py"
)
TTS_PROVIDER_CAPABILITIES = (
    ROOT / "viventium_v0_4" / "shared" / "voice" / "tts_provider_capabilities.json"
)
SYNTHETIC_AUDIO_QA_SCRIPT = (
    ROOT / "qa" / "modern-playground-voice" / "scripts" / "livekit_synthetic_audio_qa.js"
)
SYNTHETIC_AUDIO_FIXTURE_GENERATOR = (
    ROOT / "qa" / "modern-playground-voice" / "scripts" / "generate_synthetic_speech_fixtures.py"
)
CHROME_VOICE_SETUP_SCRIPT = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "scripts"
    / "chrome_voice_artifact_qa_setup.cjs"
)
TTS_ARTIFACT_BROWSER_QA_SCRIPT = (
    ROOT / "qa" / "modern-playground-voice" / "scripts" / "tts_artifact_browser_qa.cjs"
)
TYPESCRIPT_FILE = AGENT_STARTER_REACT_ROOT / "node_modules" / "typescript" / "lib" / "typescript.js"


@lru_cache(maxsize=None)
def _run_react_contract_suite(relative_path: str) -> None:
    """Run the owning component's real-module checks, not obsolete source spellings.

    The checked-out, lock-pinned component owns its Vitest resolver and synthetic browser
    fixtures. Cache one completed suite per pytest process; never count an empty/skipped bank.
    """
    test_file = AGENT_STARTER_REACT_ROOT / relative_path
    assert test_file.is_file(), f"Missing component contract: {relative_path}"
    runner = AGENT_STARTER_REACT_ROOT / "node_modules" / "vitest" / "vitest.mjs"
    assert runner.is_file(), "Install the pinned playground development dependencies first"
    completed = subprocess.run(
        ["node", str(runner), "run", relative_path, "--reporter=json", "--maxWorkers=1",
         "--no-file-parallelism"],
        cwd=AGENT_STARTER_REACT_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, (
        f"Component contract failed: {relative_path}\n{completed.stdout}\n{completed.stderr}"
    )
    report = json.loads(completed.stdout)
    assert {Path(suite["name"]).resolve() for suite in report["testResults"]} == {
        test_file.resolve()
    }
    assert report["success"] is True
    assert report["numTotalTests"] > 0
    assert report["numPassedTests"] == report["numTotalTests"]
    assert report["numFailedTests"] == 0
    assert report.get("numPendingTests", 0) == 0
    assert report.get("numTodoTests", 0) == 0


def _run_connection_details_route_case(
    *,
    env: dict[str, str],
    request_body: dict[str, object],
    fetch_responses: list[dict[str, object]],
    existing_dispatches: list[dict[str, object]] | None = None,
    list_dispatch_error: bool = False,
    dispatch_job_status: int = 1,
    dispatch_worker_claimed: bool = True,
    canonical_session: dict[str, object] | None = None,
) -> dict[str, object]:
    # Synthetic backend state is a separate authority from the caller. Defaults preserve the
    # assigned values of the earlier fixtures; authority negatives can supply a different record.
    metadata = json.loads(str(request_body.get("agentMetadata") or "{}"))
    call_id = metadata.get("callSessionId")
    settings = next((row.get("json", {}) for row in fetch_responses
                     if str(row["match"]).endswith("/voice-settings") and row["status"] == 200), {})
    canonical = canonical_session if canonical_session is not None else {
        "callSessionId": call_id,
        "roomName": request_body.get("room_name") or f"room-{call_id}",
        "gatewayAgentName": "librechat-voice-gateway",
        "ownerParticipantIdentity": request_body.get("participant_identity") or f"owner-{call_id}",
        "status": "created",
        "requestedVoiceRoute": settings.get("requestedVoiceRoute") or metadata.get("requestedVoiceRoute") or {
            "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
            "tts": {"provider": "local_chatterbox_turbo_mlx_8bit", "variant": "local"},
        },
    }
    script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const path = require('path');
        const Module = require('module');
        const ts = require({json.dumps(str(TYPESCRIPT_FILE))});

        const routePath = {json.dumps(str(ROUTE_FILE))};
        const componentRoot = {json.dumps(str(AGENT_STARTER_REACT_ROOT))};

        const caseData = {{
          env: {json.dumps(env)},
          canonical: {json.dumps(canonical)},
          requestBody: {json.dumps(request_body)},
          fetchResponses: {json.dumps(fetch_responses)},
          existingDispatches: {json.dumps(existing_dispatches or [])},
          listDispatchError: {json.dumps(list_dispatch_error)},
          dispatchJobStatus: {json.dumps(dispatch_job_status)},
          dispatchWorkerClaimed: {json.dumps(dispatch_worker_claimed)},
        }};

        for (const key of Object.keys(process.env)) {{
          if (key.startsWith('VIVENTIUM_') || key.startsWith('LIVEKIT_') ||
              key === 'NEXT_PUBLIC_LIVEKIT_URL') delete process.env[key];
        }}
        for (const [key, value] of Object.entries(caseData.env)) {{
          process.env[key] = value;
        }}

        const dispatchCalls = [];
        const roomCalls = [];
        const fetchCalls = [];
        const tokenRoomConfigs = [];
        const liveDispatches = caseData.existingDispatches.map((entry, index) => {{
          const id = typeof entry.id === 'string' ? entry.id : `AD_existing_${{index + 1}}`;
          return {{
            ...entry,
            id,
            state:
              entry.state ||
              (id
                ? {{
                    jobs: [
                      {{
                        id: `AJ_existing_${{index + 1}}`,
                        dispatchId: id,
                        state: {{ status: 1, workerId: `AW_existing_${{index + 1}}` }},
                      }},
                    ],
                  }}
                : {{ jobs: [] }}),
          }};
        }});

        class FakeAccessToken {{
          constructor(_apiKey, _apiSecret, options) {{
            this.identity = options?.identity ?? '';
            this._roomConfig = null;
          }}

          addGrant() {{}}

          set roomConfig(value) {{
            this._roomConfig = value;
            tokenRoomConfigs.push(
              typeof value?.toJson === 'function' ? value.toJson() : value
            );
          }}

          get roomConfig() {{
            return this._roomConfig;
          }}

          toJwt() {{
            return 'fake-jwt';
          }}
        }}

        class FakeAgentDispatchClient {{
          constructor(host, apiKey, apiSecret) {{
            this.host = host;
            this.apiKey = apiKey;
            this.apiSecret = apiSecret;
          }}

          async listDispatch(_roomName) {{
            if (caseData.listDispatchError) {{
              throw new Error('list dispatch failed');
            }}
            return liveDispatches;
          }}

          async createDispatch(roomName, agentName, options) {{
            dispatchCalls.push({{ roomName, agentName, options }});
            const id = `AD_created_${{dispatchCalls.length}}`;
            const created = {{
              id,
              roomName,
              agentName,
              options,
              state: {{
                jobs: [
                  {{
                    id: `AJ_created_${{dispatchCalls.length}}`,
                    dispatchId: id,
                    state: {{
                      status: caseData.dispatchJobStatus,
                      workerId: `AW_created_${{dispatchCalls.length}}`,
                    }},
                  }},
                ],
              }},
            }};
            liveDispatches.push(created);
            return created;
          }}

          async getDispatch(dispatchId, _roomName) {{
            return liveDispatches.find((entry) => entry.id === dispatchId);
          }}

          async deleteDispatch(dispatchId, _roomName) {{
            const index = liveDispatches.findIndex((entry) => entry.id === dispatchId);
            if (index >= 0) liveDispatches.splice(index, 1);
          }}
        }}

        class FakeRoomServiceClient {{
          constructor(host, apiKey, apiSecret) {{
            this.host = host;
            this.apiKey = apiKey;
            this.apiSecret = apiSecret;
          }}

          async createRoom(options) {{
            roomCalls.push(options);
            return {{ name: options.name }};
          }}
        }}

        class FakeRoomConfiguration {{
          constructor(data = {{}}) {{
            this.agents = Array.isArray(data.agents)
              ? data.agents.map((agent) => new FakeRoomAgentDispatch(agent))
              : [];
          }}

          static fromJson(value) {{
            return new FakeRoomConfiguration(value && typeof value === 'object' ? value : {{}});
          }}

          toJson() {{
            return {{
              agents: this.agents.map((agent) => ({{
                agentName: agent.agentName,
                ...(agent.metadata ? {{ metadata: agent.metadata }} : {{}}),
              }})),
            }};
          }}
        }}

        class FakeRoomAgentDispatch {{
          constructor(data = {{}}) {{
            this.agentName = data.agentName ?? data.agent_name ?? '';
            this.metadata = data.metadata ?? '';
          }}
        }}

        const NextResponse = {{
          json(body, init = {{}}) {{
            const headers = Object.fromEntries(new Headers(init.headers || {{}}).entries());
            return {{
              status: init.status ?? 200,
              headers,
              body,
            }};
          }},
        }};

        globalThis.fetch = async (url, init = {{}}) => {{
          const urlText = String(url);
          fetchCalls.push({{
            url: urlText,
            method: init.method || 'GET',
            body: init.body || null,
          }});
          if (urlText.endsWith(`/api/viventium/calls/${{caseData.canonical.callSessionId}}/state`)) {{
            return {{ ok: true, status: 200,
              async json() {{ return caseData.canonical; }},
              async text() {{ return JSON.stringify(caseData.canonical); }} }};
          }}
          const matchIndex = caseData.fetchResponses.findIndex((item) =>
            urlText.endsWith(String(item.match))
          );
          if (matchIndex < 0) {{
            if (urlText.includes('/dispatch/status?claimId=')) {{
              return {{
                ok: true,
                status: 200,
                async json() {{
                  return {{
                    version: 1,
                    status: caseData.dispatchWorkerClaimed ? 'claimed' : 'waiting',
                    isWorkerClaimed: caseData.dispatchWorkerClaimed,
                  }};
                }},
                async text() {{ return ''; }},
              }};
            }}
            throw new Error(`Unexpected fetch: ${{urlText}}`);
          }}
          const match = caseData.fetchResponses.splice(matchIndex, 1)[0];
          return {{
            ok: Number(match.status) >= 200 && Number(match.status) < 300,
            status: Number(match.status),
            async json() {{
              return Object.prototype.hasOwnProperty.call(match, 'json') ? match.json : null;
            }},
            async text() {{
              if (Object.prototype.hasOwnProperty.call(match, 'text')) {{
                return String(match.text);
              }}
              return JSON.stringify(
                Object.prototype.hasOwnProperty.call(match, 'json') ? match.json : null
              );
            }},
          }};
        }};

        const fakeRequire = (specifier) => {{
          if (specifier === 'next/server') {{
            return {{ NextResponse }};
          }}
          if (specifier === 'livekit-server-sdk') {{
            return {{
              AccessToken: FakeAccessToken,
              RoomConfiguration: FakeRoomConfiguration,
              RoomAgentDispatch: FakeRoomAgentDispatch,
              AgentDispatchClient: FakeAgentDispatchClient,
              RoomServiceClient: FakeRoomServiceClient,
            }};
          }}
          if (specifier === '@livekit/protocol') {{
            return {{
              JobStatus: {{
                JS_PENDING: 0,
                JS_RUNNING: 1,
                JS_SUCCESS: 2,
                JS_FAILED: 3,
              }},
              RoomAgentDispatch: FakeRoomAgentDispatch,
              RoomConfiguration: FakeRoomConfiguration,
            }};
          }}
          return undefined;
        }};

        // Resolve the compatibility export and all real owning TS modules from the component,
        // preserving its alias/relative-module graph. Only external LiveKit/Next I/O is faked.
        const loaded = new Map();
        function loadTypeScript(file) {{
          const resolved = path.resolve(file);
          if (!resolved.startsWith(componentRoot + path.sep)) throw Error('Module outside component');
          if (loaded.has(resolved)) return loaded.get(resolved).exports;
          const localModule = new Module(resolved, module);
          localModule.filename = resolved;
          localModule.paths = Module._nodeModulePaths(path.dirname(resolved));
          loaded.set(resolved, localModule);
          const nativeRequire = Module.createRequire(resolved);
          localModule.require = (specifier) => {{
            const mocked = fakeRequire(specifier);
            if (mocked !== undefined) return mocked;
            if (specifier.startsWith('@/') || specifier.startsWith('.')) {{
              const target = specifier.startsWith('@/')
                ? path.join(componentRoot, specifier.slice(2))
                : path.resolve(path.dirname(resolved), specifier);
              const sourcePath = [target, target + '.ts', target + '.tsx',
                path.join(target, 'index.ts')].find((candidate) =>
                  fs.existsSync(candidate) && fs.statSync(candidate).isFile());
              if (!sourcePath) throw Error(`Unresolved component module: ${{specifier}}`);
              return loadTypeScript(sourcePath);
            }}
            return nativeRequire(specifier);
          }};
          const compiled = ts.transpileModule(fs.readFileSync(resolved, 'utf8'), {{
            compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
              esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX }}, fileName: resolved,
          }});
          localModule._compile(compiled.outputText, resolved);
          return localModule.exports;
        }}
        const routeExports = loadTypeScript(routePath);

        const request = {{
          url: 'https://playground.example.test/api/connection-details',
          headers: new Headers({{
            'content-type': 'application/json',
            'X-VIVENTIUM-CALL-CAPABILITY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
          }}),
          async json() {{
            return caseData.requestBody;
          }},
        }};

        Promise.resolve(routeExports.POST(request))
          .then((response) => {{
            process.stdout.write(
              JSON.stringify({{
                response,
                dispatchCalls,
                roomCalls,
                fetchCalls,
                tokenRoomConfigs,
              }})
            );
          }})
          .catch((error) => {{
            process.stderr.write(String(error?.stack || error));
            process.exit(1);
          }});
        """
    )

    completed = subprocess.run(
        ["node", "-"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "connection-details harness failed:\n"
            f"{completed.stderr.strip() or '<no stderr>'}"
        )
    stdout = completed.stdout.strip()
    if not stdout:
        raise AssertionError("connection-details harness returned no stdout")
    payload_line = stdout.splitlines()[-1]
    return json.loads(payload_line)


def _token_dispatch_agent(result: dict[str, object], agent_name: str = "librechat-voice-gateway") -> dict[str, object]:
    room_configs = result.get("tokenRoomConfigs") or []
    assert room_configs, "expected connection token to include roomConfig"
    agents = room_configs[-1].get("agents") or []
    matches = [agent for agent in agents if agent.get("agentName") == agent_name]
    assert len(matches) == 1
    return matches[0]


def _assert_no_token_dispatch(result: dict[str, object]) -> None:
    room_configs = result.get("tokenRoomConfigs") or []
    assert all(not (room_config.get("agents") or []) for room_config in room_configs)


def _single_explicit_dispatch(
    result: dict[str, object],
    *,
    room_name: str,
    agent_name: str = "librechat-voice-gateway",
) -> dict[str, object]:
    dispatch_calls = result.get("dispatchCalls") or []
    assert len(dispatch_calls) == 1
    dispatch_call = dispatch_calls[0]
    assert dispatch_call["roomName"] == room_name
    assert dispatch_call["agentName"] == agent_name
    room_calls = result.get("roomCalls") or []
    assert room_calls
    assert all(
        room_call
        == {
            "name": room_name,
            "emptyTimeout": 60,
            "departureTimeout": 60,
        }
        for room_call in room_calls
    )
    return dispatch_call


def test_playground_client_merges_deeplink_token_options_into_connection_details_request() -> None:
    _run_react_contract_suite('lib/call-token-source.test.ts')


def test_connection_details_route_accepts_only_call_session_identity_from_deeplink() -> None:
    _run_react_contract_suite('app/api/token/authority.test.ts')
    _run_react_contract_suite('app/api/connection-details/route.test.ts')


def test_signed_call_session_deeplink_autoconnects_without_an_app_setup_step() -> None:
    _run_react_contract_suite('components/app/app.test.tsx')
    _run_react_contract_suite('hooks/useCallStart.test.tsx')


def test_call_session_start_click_is_single_flight_and_disables_duplicate_starts() -> None:
    _run_react_contract_suite('hooks/useCallStart.test.tsx')
    _run_react_contract_suite('components/app/app.test.tsx')


def test_voice_route_preflight_blocks_connection_until_the_exact_saved_route_is_valid() -> None:
    _run_react_contract_suite('app/api/token/authority.test.ts')
    _run_react_contract_suite('components/app/app.test.tsx')
    _run_react_contract_suite('hooks/useCallStart.test.tsx')


def test_call_session_playground_extends_agent_join_timeout_for_local_cold_starts() -> None:
    hook = CALL_START_HOOK_FILE.read_text()
    app = APP_FILE.read_text()
    assert "export const CALL_AGENT_CONNECT_TIMEOUT_MS = 90_000;" in hook
    assert "agentConnectTimeoutMilliseconds: CALL_AGENT_CONNECT_TIMEOUT_MS" in app
    _run_react_contract_suite("lib/call-token-source.sdk.test.tsx")


def test_explicit_dispatch_call_connects_room_before_enabling_microphone() -> None:
    _run_react_contract_suite('hooks/useCallStart.test.tsx')
    _run_react_contract_suite('lib/call-token-source.sdk.test.tsx')
    app = APP_FILE.read_text()
    recovery = app.split("const recoverCall = useCallback(async () => {", 1)[1].split(
        "}, [startCall]);", 1
    )[0]
    assert "if (!(await startCall())) throw new Error('Viventium call recovery failed.');" in recovery
    recovery_options = app.split("useConnectionRecovery({", 1)[1].split("});", 1)[0]
    assert "start: recoverCall," in recovery_options


def test_voice_connection_recovery_preserves_background_reconnect_without_restarting_after_end_call() -> None:
    content = CONNECTION_RECOVERY_HOOK_FILE.read_text()

    assert "const RECONNECT_GRACE_MS = 5000;" in content
    assert "function isRecoverableActiveState(connectionState: ConnectionState): boolean {" in content
    assert "document.visibilityState === 'visible'" in content
    assert "if (wasConnectedRef.current && shouldRecoverOnVisibleRef.current)" in content
    assert "visible-page disconnect is intentional user action" in content
    assert "const scheduleRecoveryCheck = useCallback(() => {" in content
    assert "if (recoveryTimerRef.current)" in content
    assert "document.visibilityState !== 'visible'" in content
    assert "shouldRecoverOnVisibleRef.current = true;" in content
    assert "scheduleRecoveryCheck();" in content


def test_modern_playground_prewarm_is_bounded_and_warning_only() -> None:
    content = START_SCRIPT.read_text()

    assert 'VIVENTIUM_PLAYGROUND_PREWARM_REQUEST_TIMEOUT_SECONDS:-20' in content
    assert "request_timeout=20" in content
    assert "Prewarming ${PLAYGROUND_LABEL} voice startup routes" in content
    assert "/api/health" in content
    assert "health route did not prewarm before timeout" in content
    assert "call-session-voice-settings?callSessionId=viventium-prewarm" in content
    assert "call-session-state?callSessionId=viventium-prewarm" in content
    assert "GET intentionally exercises the Next.js route module compile without issuing a token." in content
    assert "connection-details route did not prewarm before timeout" in content
    assert "/api/call-tasks/viventium-prewarm/cancel" in content
    assert "task-action route did not prewarm before timeout" in content



def test_modern_task_action_prewarm_runs_once_without_auth_and_stays_warning_only() -> None:
    function = START_SCRIPT.read_text().split("\nprewarm_modern_playground_routes() {\n", 1)[1].split("\n}\n", 1)[0]
    shell = """
    exec 3>&1
    log_info() { printf 'INFO %s\\n' "$*"; }
    log_warn() { printf 'WARN %s\\n' "$*"; }
    get_playground_port() { printf '3300'; }
    curl() {
      printf 'CURL' >&3; printf ' %s' "$@" >&3; printf '\\n' >&3
      case "$*" in *'/api/health'*) printf '%s' "$TEST_HEALTH_CODE"; return "$TEST_CURL_EXIT";; *'/api/call-tasks/'*) printf '%s' "$TEST_HTTP_CODE"; return "$TEST_CURL_EXIT";; esac
      printf '200'
    }
    prewarm_modern_playground_routes() {
    """ + function + "\n}\nprewarm_modern_playground_routes 3300\n"
    for code, curl_exit, configured, expected, health_code in [("405", "0", "7", "7", "200"), ("000", "28", "bad", "20", "000")]:
        env = {"PATH": os.environ["PATH"], "PLAYGROUND_VARIANT": "modern", "PLAYGROUND_LABEL": "Synthetic",
               "TEST_HTTP_CODE": code, "TEST_CURL_EXIT": curl_exit, "TEST_HEALTH_CODE": health_code,
               "VIVENTIUM_PLAYGROUND_PREWARM_REQUEST_TIMEOUT_SECONDS": configured}
        result = subprocess.run(["bash", "-c", shell], env=env, capture_output=True, text=True, check=True)
        calls = [line.split()[1:] for line in result.stdout.splitlines() if line.startswith("CURL ")]
        assert len(calls) == 5
        assert [args[-1] for args in calls] == [
            "http://localhost:3300/api/health",
            "http://localhost:3300/api/call-session-voice-settings?callSessionId=viventium-prewarm",
            "http://localhost:3300/api/call-session-state?callSessionId=viventium-prewarm",
            "http://localhost:3300/api/connection-details",
            "http://localhost:3300/api/call-tasks/viventium-prewarm/cancel",
        ]
        assert all(args[:-1] == ["-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", expected] for args in calls)
        assert ("task-action route prewarmed (HTTP 405)" if code == "405" else
                "task-action route did not prewarm before timeout") in result.stdout
        assert ("health route prewarmed (HTTP 200)" if health_code == "200" else
                "health route did not prewarm before timeout") in result.stdout
    for setting in [{"PLAYGROUND_VARIANT": "classic"}, {"VIVENTIUM_PLAYGROUND_PREWARM": "false"}]:
        result = subprocess.run(["bash", "-c", shell], env={**env, **setting}, capture_output=True, text=True, check=True)
        assert "CURL " not in result.stdout


def test_native_next_task_action_get_never_invokes_post_or_core() -> None:
    route = AGENT_STARTER_REACT_ROOT / "app/api/call-tasks/[taskId]/[action]/route.ts"
    script = r"""
    const fs = require('fs'), path = require('path'), Module = require('module');
    const app = process.argv[1], route = process.argv[2];
    const requireApp = Module.createRequire(path.join(app, 'package.json'));
    const ts = requireApp('typescript'), cache = new Map();
    let fetchCalls = 0;
    global.fetch = () => { fetchCalls++; throw new Error('Unexpected external fetch'); };
    function load(file) {
      if (cache.has(file)) return cache.get(file).exports;
      const mod = new Module(file); cache.set(file, mod);
      mod.filename = file; mod.paths = Module._nodeModulePaths(path.dirname(file));
      mod.require = name => name.startsWith('@/') ? load(path.join(app, name.slice(2) + '.ts')) : requireApp(name);
      mod._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {compilerOptions:
        {module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText, file);
      return mod.exports;
    }
    (async () => {
      const handlers = load(route);
      const {autoImplementMethods} = requireApp('next/dist/server/route-modules/app-route/helpers/auto-implement-methods');
      const methods = autoImplementMethods(handlers);
      const response = await methods.GET(new Request('http://localhost:3300/api/call-tasks/viventium-prewarm/cancel'));
      console.log(JSON.stringify({status:response.status,body:await response.text(),fetchCalls,
        exportedMethods:Object.keys(handlers),postPreserved:methods.POST === handlers.POST}));
    })().catch(() => process.exitCode = 1);
    """
    result = subprocess.run(["node", "-e", script, str(AGENT_STARTER_REACT_ROOT), str(route)],
                            env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"status": 405, "body": "", "fetchCalls": 0,
                                      "exportedMethods": ["POST"], "postPreserved": True}

def test_xai_voice_runtime_exposes_only_standalone_tts() -> None:
    launcher = START_SCRIPT.read_text()
    worker = VOICE_GATEWAY_WORKER.read_text()
    capabilities = json.loads(TTS_PROVIDER_CAPABILITIES.read_text())

    assert not RETIRED_XAI_VOICE_AGENT_ADAPTER.exists()
    assert "VIVENTIUM_XAI_WSS_URL" not in launcher
    assert "VIVENTIUM_XAI_INSTRUCTIONS" not in launcher
    assert "_build_legacy_xai_voice_agent_tts" not in worker
    assert capabilities["providers"]["xai"]["runtime_models"] == [
        {"id": "xai-tts", "api_route": "tts", "legacy": False}
    ]


def test_synthetic_audio_qa_can_force_an_external_relay_media_path() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "VIVENTIUM_QA_EXTERNAL_TURN_URLS" in content
    assert "VIVENTIUM_QA_EXTERNAL_TURN_USERNAME" in content
    assert "VIVENTIUM_QA_EXTERNAL_TURN_CREDENTIAL" in content
    assert "VIVENTIUM_QA_FORCE_RELAY" in content
    assert "installExternalTurnProbe" in content
    assert "collectRtcEvidence" in content
    assert re.search(
        r'''iceTransportPolicy:\s*forceRelay\s*\?\s*["']relay["']''', content
    )
    assert "selectedCandidatePairs" in content
    assert "externalTurnConfigured" in content
    assert "openrelayprojectsecret" not in content


def test_synthetic_audio_qa_can_tunnel_public_tcp_candidates_for_off_lan_qa() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "VIVENTIUM_QA_PUBLIC_MEDIA_CANDIDATE" in content
    assert "VIVENTIUM_QA_PUBLIC_MEDIA_PROXY" in content
    assert "rewriteRemoteCandidate" in content
    assert "publicCandidateRewriteCount" in content
    assert "externalTcpMediaSelected" in content


def test_synthetic_audio_qa_can_force_livekit_turn_tls_through_an_off_lan_proxy() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "VIVENTIUM_QA_TURN_PROXY_URL" in content
    assert "VIVENTIUM_QA_TURN_PROXY_HOST_RULE" in content
    assert "turnProxyConfigured" in content
    assert "turnTlsRelaySelected" in content
    assert "configuration?.iceServers" in content


def test_synthetic_audio_qa_can_run_the_entire_browser_from_an_off_lan_proxy() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "VIVENTIUM_QA_BROWSER_PLAYGROUND_URL" in content
    assert "VIVENTIUM_QA_BROWSER_PROXY" in content
    assert "VIVENTIUM_QA_DISABLE_NON_PROXIED_UDP" in content
    assert "browserProxyConfigured" in content
    assert "browserProxyMediaSelected" in content


def test_synthetic_audio_qa_requires_received_audio_not_only_an_attached_element() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert '"inbound-rtp"' in content
    assert 'stat.kind !== "audio"' in content
    assert "inboundAudioBytesReceived" in content
    assert "receivedAudioEnergy" in content
    assert "deliveredAudioBytesDelta" in content
    assert "finalInteractiveMessages" in content
    assert "waitForDeliveredAudio" in content
    assert "waitForCompletedPlayback" in content
    assert "playbackCompleted" in content
    assert "waitForCompletedInteractiveTask" in content
    assert "audioState.delivered" not in content


def test_synthetic_audio_qa_requires_a_live_published_microphone_before_waiting() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "async function ensurePublishedMicrophone" in content
    assert 'throw new Error("microphone_not_published")' in content
    assert "result.microphonePublished = true" in content
    assert "result.microphonePublished &&" in content


def test_synthetic_audio_fixture_waits_for_deferred_microphone_publication() -> None:
    content = SYNTHETIC_AUDIO_FIXTURE_GENERATOR.read_text()

    assert '"--lead-silence-s"' in content
    assert "default=15.0" in content
    assert '"leadSilenceSeconds": lead_silence_s' in content


def test_synthetic_audio_qa_proves_listen_only_has_no_response_plane() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert "voiceTaskCount" in content
    assert "listenOnlyIsolationObserved" in content
    assert "result.assistantResponsePresent === false" in content
    assert 'state.text.includes("speaking")' in content
    assert "result.voiceTaskCount === 0" in content


def test_synthetic_audio_qa_can_prove_intentional_wing_silence() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert 'item === "--expect-silence"' in content
    assert "waitForInteractiveUserTranscript" in content
    assert "waitForIntentionalSilence" in content
    assert "isNoResponseOnly" in content
    assert "intentionalSilenceObserved" in content
    assert "args.expectSilence && args.mode !== \"wing\"" in content


def test_synthetic_audio_qa_rejects_late_browser_errors_and_incomplete_cleanup() -> None:
    script = textwrap.dedent(
        f"""
        const {{ finalizeSyntheticQaResult }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});

        function result(cleanup = {{ users: 1, callSessions: 1 }}) {{
          return {{ seeded: true, transportOk: true, ok: true, errorCodes: [], cleanup }};
        }}

        process.stdout.write(JSON.stringify({{
          healthy: finalizeSyntheticQaResult(result(), [], true),
          lateBrowserError: finalizeSyntheticQaResult(result(), [new Error("private browser details")], true),
          failedCleanup: finalizeSyntheticQaResult(result({{ errorCode: "cleanup_failed" }}), [], true),
          disabledCleanup: finalizeSyntheticQaResult(result(null), [], false),
          repeatedSpeech: finalizeSyntheticQaResult({{
            ...result(), transcriptCountWithinLimit: false,
          }}, [], true),
          exposedIdentity: finalizeSyntheticQaResult({{
            ...result(), rawParticipantIdentityExposed: true,
          }}, [], true),
          unauthenticatedCoreBrowser: finalizeSyntheticQaResult({{
            ...result(), coreBrowserRequested: true,
            coreBrowserAuthenticated: false, coreBrowserOwnerMatched: false,
          }}, [], true),
          authenticatedCoreBrowser: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, loginSessions: 1 }}),
            coreBrowserRequested: true, coreBrowserAuthenticated: true,
            coreBrowserOwnerMatched: true, coreBrowserComposerReady: true,
          }}, [], true),
          leakedCoreBrowserSession: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, loginSessions: 0 }}),
            coreBrowserRequested: true, coreBrowserAuthenticated: true,
            coreBrowserOwnerMatched: true, coreBrowserComposerReady: true,
          }}, [], true),
          missingTranscript: finalizeSyntheticQaResult({{
            ...result(), autoConnected: true, transcriptMatchedExpected: false,
          }}, [], true),
          missingPlayback: finalizeSyntheticQaResult({{
            ...result(), interactive: true, completedVoiceTask: true,
            playbackCompleted: false,
          }}, [], true),
          passiveWingResponse: finalizeSyntheticQaResult({{
            ...result(), silenceExpected: true, assistantResponsePresent: true,
          }}, [], true),
          runningTask: finalizeSyntheticQaResult({{
            ...result(), interactive: true, transcriptMatchedExpected: true,
            voiceTaskCount: 1, completedVoiceTask: false, completedVoiceTaskState: "running",
          }}, [], true),
          unknownOwner: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true, speakerActorTrust: ["unknown"],
          }}, [], true),
          trustedOwner: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true, speakerActorTrust: ["owner_participant"],
          }}, [], true),
          verifiedFinalTurn: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true,
            speakerActorTrust: ["unknown", "owner_participant"],
            authoritativeSpeakerActorTrust: ["owner_participant"],
            currentTurnAllVerified: true,
          }}, [], true),
          verifiedOwnerBlockedByInterim: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true,
            speakerActorTrust: ["unknown", "owner_participant"],
            authoritativeSpeakerActorTrust: ["unknown", "owner_participant"],
            currentTurnSpeakerCount: 2,
            currentTurnFinalSpeakerCount: 1,
            currentTurnVerifiedFinalSpeakerCount: 1,
            currentTurnUnverifiedInterimCount: 1,
            currentTurnProviderSpeakerIdCount: 1,
            currentTurnAllVerified: false,
          }}, [], true),
          providerSpeakerIdentityMissing: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true,
            speakerActorTrust: ["unknown"],
            authoritativeSpeakerActorTrust: ["unknown"],
            currentTurnSpeakerCount: 1,
            currentTurnProviderSpeakerIdCount: 0,
            currentTurnAllVerified: false,
          }}, [], true),
          sharedMicrophoneTurn: finalizeSyntheticQaResult({{
            ...result(), ownerTrustRequired: true,
            speakerActorTrust: ["owner_participant"],
            authoritativeSpeakerActorTrust: ["owner_participant"],
            currentTurnAllVerified: true,
            speakerAttributionState: "shared_mic_unverified",
          }}, [], true),
          untrustedSideEffect: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, scheduledTasks: 1 }}),
            mode: "call", speakerActorTrust: ["unknown"],
          }}, [], true),
          passiveWingSideEffect: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, scheduledTasks: 1 }}),
            mode: "wing", silenceExpected: true, speakerActorTrust: ["owner_participant"],
          }}, [], true),
          listenOnlySideEffect: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, scheduledTasks: 1 }}),
            mode: "listen_only", speakerActorTrust: ["owner_participant"],
          }}, [], true),
          trustedSideEffect: finalizeSyntheticQaResult({{
            ...result({{ users: 1, callSessions: 1, scheduledTasks: 1 }}),
            mode: "call", speakerActorTrust: ["owner_participant"],
          }}, [], true),
          bootstrapSchedule: finalizeSyntheticQaResult({{
            ...result({{
              users: 1, callSessions: 1, scheduledTasks: 1,
              bootstrapScheduledTasks: 1, unsafeScheduledTasks: 0,
            }}),
            mode: "call", speakerActorTrust: ["unknown"],
          }}, [], true),
          missingAudio: finalizeSyntheticQaResult({{
            ...result(), outputAudioRequested: true, outputAudioEvidence: null,
          }}, [], true),
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    actual = json.loads(completed.stdout)

    assert actual["healthy"]["ok"] is True
    assert actual["healthy"]["pageErrorCount"] == 0
    assert actual["lateBrowserError"]["ok"] is False
    assert actual["lateBrowserError"]["transportOk"] is False
    assert actual["lateBrowserError"]["pageErrorCount"] == 1
    assert actual["lateBrowserError"]["errorCodes"] == ["browser_page_error"]
    assert "private browser details" not in completed.stdout
    assert actual["failedCleanup"]["ok"] is False
    assert actual["failedCleanup"]["errorCodes"] == ["synthetic_cleanup_incomplete"]
    assert actual["disabledCleanup"]["ok"] is False
    assert actual["disabledCleanup"]["errorCodes"] == ["synthetic_cleanup_required"]
    assert actual["repeatedSpeech"]["errorCodes"] == ["unexpected_transcript_count"]
    assert actual["exposedIdentity"]["errorCodes"] == ["participant_identity_exposed"]
    assert actual["unauthenticatedCoreBrowser"]["errorCodes"] == [
        "synthetic_core_browser_not_authenticated"
    ]
    assert actual["authenticatedCoreBrowser"]["ok"] is True
    assert actual["leakedCoreBrowserSession"]["errorCodes"] == [
        "synthetic_core_browser_session_cleanup_incomplete"
    ]
    assert actual["missingTranscript"]["errorCodes"] == ["expected_transcript_not_observed"]
    assert actual["missingPlayback"]["errorCodes"] == ["audible_playback_not_observed"]
    assert actual["passiveWingResponse"]["errorCodes"] == ["passive_wing_response_observed"]
    assert actual["runningTask"]["errorCodes"] == ["voice_task_not_terminal"]
    assert actual["unknownOwner"]["ownerTrustVerified"] is False
    assert actual["unknownOwner"]["errorCodes"] == ["owner_speaker_not_verified"]
    assert actual["trustedOwner"]["ownerTrustVerified"] is True
    assert actual["trustedOwner"]["ok"] is True
    assert actual["verifiedFinalTurn"]["ownerTrustVerified"] is True
    assert actual["verifiedFinalTurn"]["ok"] is True
    assert actual["verifiedOwnerBlockedByInterim"]["ownerTrustVerified"] is False
    assert (
        actual["verifiedOwnerBlockedByInterim"]["ownerTrustFailureReason"]
        == "unverified_interim_segment_blocks_owner"
    )
    assert actual["verifiedOwnerBlockedByInterim"]["errorCodes"] == [
        "owner_speaker_not_verified"
    ]
    assert (
        actual["providerSpeakerIdentityMissing"]["ownerTrustFailureReason"]
        == "provider_speaker_identity_missing"
    )
    assert actual["sharedMicrophoneTurn"]["ownerTrustVerified"] is False
    assert (
        actual["sharedMicrophoneTurn"]["ownerTrustFailureReason"]
        == "shared_microphone_unverified"
    )
    assert actual["sharedMicrophoneTurn"]["errorCodes"] == ["owner_speaker_not_verified"]
    assert actual["untrustedSideEffect"]["errorCodes"] == ["unauthorized_schedule_side_effect"]
    assert actual["passiveWingSideEffect"]["errorCodes"] == ["unauthorized_schedule_side_effect"]
    assert actual["listenOnlySideEffect"]["errorCodes"] == ["unauthorized_schedule_side_effect"]
    assert actual["trustedSideEffect"]["ok"] is True
    assert actual["bootstrapSchedule"]["ok"] is True
    assert actual["missingAudio"]["errorCodes"] == ["output_audio_missing"]


def test_synthetic_audio_qa_cleans_only_exact_disposable_owner_schedules(tmp_path: Path) -> None:
    database = tmp_path / "schedules.db"
    synthetic_owner = "a" * 24
    protected_owner = "b" * 24
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE scheduled_tasks (id TEXT, user_id TEXT)")
        connection.executemany(
            "INSERT INTO scheduled_tasks VALUES (?, ?)",
            [("fixture-schedule", synthetic_owner), ("protected-schedule", protected_owner)],
        )

    script = textwrap.dedent(
        f"""
        const {{ cleanupSyntheticSchedules }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const database = {json.dumps(str(database))};
        let invalidRejected = false;
        try {{
          cleanupSyntheticSchedules({{
            userId: "unsafe' OR 1=1 --",
            email: "viventium-voice-qa-safe@example.com",
          }}, database);
        }} catch {{
          invalidRejected = true;
        }}
        const removed = cleanupSyntheticSchedules({{
          userId: {json.dumps(synthetic_owner)},
          email: "viventium-voice-qa-safe@example.com",
        }}, database);
        process.stdout.write(JSON.stringify({{ invalidRejected, removed }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {"invalidRejected": True, "removed": 1}
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id, user_id FROM scheduled_tasks").fetchall() == [
            ("protected-schedule", protected_owner)
        ]


def test_synthetic_audio_qa_distinguishes_default_bootstrap_from_unauthorized_schedules(
    tmp_path: Path,
) -> None:
    database = tmp_path / "schedules.db"
    synthetic_owner = "a" * 24
    protected_owner = "b" * 24
    bootstrap = json.dumps(
        {
            "template_id": "synthetic-template",
            "bootstrap_source": "synthetic-bootstrap",
            "bootstrap_surface": "voice",
        }
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE scheduled_tasks "
            "(id TEXT, user_id TEXT, created_source TEXT, metadata_json TEXT)"
        )
        connection.executemany(
            "INSERT INTO scheduled_tasks VALUES (?, ?, ?, ?)",
            [
                ("default-bootstrap", synthetic_owner, "agent", bootstrap),
                ("unauthorized-reminder", synthetic_owner, "user", "{}"),
                ("protected-reminder", protected_owner, "user", "{}"),
            ],
        )

    script = textwrap.dedent(
        f"""
        const {{ inspectSyntheticSchedules }} =
          require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const inventory = inspectSyntheticSchedules({{
          userId: {json.dumps(synthetic_owner)},
          email: "viventium-voice-qa-safe@example.com",
        }}, {json.dumps(str(database))});
        process.stdout.write(JSON.stringify(inventory));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {"total": 2, "bootstrap": 1, "unsafe": 1}


def test_synthetic_audio_qa_cancels_only_its_own_active_voice_tasks() -> None:
    script = textwrap.dedent(
        f"""
        const {{
          cancelSyntheticActiveVoiceTasks,
          createBrowserCallCapability,
        }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const capability = createBrowserCallCapability().capability;
        const seeded = {{
          userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
          email: "viventium-voice-qa-safe@example.com",
          callSessionId: "call-fixture-001",
          browserCapability: capability,
        }};
        let observedFilter;
        let observedRequest;
        const db = {{
          collection(name) {{
            if (name !== "viventiumvoicetasks") throw new Error("wrong collection");
            return {{
              find(filter) {{
                observedFilter = filter;
                return {{
                  toArray: async () => [{{ payload: {{ taskId: "task-fixture-001" }} }}],
                }};
              }},
            }};
          }},
        }};
        global.fetch = async (url, options) => {{
          observedRequest = {{ url: String(url), options }};
          return {{ ok: true, status: 200 }};
        }};
        (async () => {{
          const cancelled = await cancelSyntheticActiveVoiceTasks(
            db,
            seeded,
            "http://127.0.0.1:3300",
          );
          let invalidOwnerRejected = false;
          try {{
            await cancelSyntheticActiveVoiceTasks(
              db,
              {{ ...seeded, email: "protected-owner@example.com" }},
              "http://127.0.0.1:3300",
            );
          }} catch {{ invalidOwnerRejected = true; }}
          process.stdout.write(JSON.stringify({{
            cancelled,
            scopedUser: observedFilter.userId,
            scopedSession: observedFilter.callSessionId,
            url: observedRequest.url,
            method: observedRequest.options.method,
            capabilityMatched:
              observedRequest.options.headers["X-VIVENTIUM-CALL-CAPABILITY"] === capability,
            sessionBound:
              JSON.parse(observedRequest.options.body).callSessionId === seeded.callSessionId,
            invalidOwnerRejected,
          }}));
        }})().catch(error => {{ process.stderr.write(error.message); process.exitCode = 1; }});
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "cancelled": 1,
        "scopedUser": "aaaaaaaaaaaaaaaaaaaaaaaa",
        "scopedSession": "call-fixture-001",
        "url": "http://127.0.0.1:3300/api/call-tasks/task-fixture-001/cancel",
        "method": "POST",
        "capabilityMatched": True,
        "sessionBound": True,
        "invalidOwnerRejected": True,
    }


def test_synthetic_audio_qa_uses_the_installed_speech_routes_by_default(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic.wav"
    fixture.write_bytes(b"synthetic-audio")
    script = textwrap.dedent(
        f"""
        delete process.env.VIVENTIUM_QA_STT_PROVIDER;
        delete process.env.VIVENTIUM_QA_STT_VARIANT;
        delete process.env.VIVENTIUM_QA_TTS_PROVIDER;
        delete process.env.VIVENTIUM_QA_TTS_VARIANT;
        process.env.VIVENTIUM_STT_PROVIDER = "whisper_local";
        process.env.VIVENTIUM_STT_MODEL = "large-v3-turbo";
        process.env.VIVENTIUM_TTS_PROVIDER = "xai";
        process.env.VIVENTIUM_XAI_VOICE = "Sal";
        const {{ parseArgs }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const args = parseArgs([
          "--audio", {json.dumps(str(fixture))},
          "--output-root", {json.dumps(str(tmp_path))},
        ]);
        process.stdout.write(JSON.stringify({{
          sttProvider: args.sttProvider,
          sttVariant: args.sttVariant,
          ttsProvider: args.ttsProvider,
          ttsVariant: args.ttsVariant,
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "sttProvider": "whisper_local",
        "sttVariant": "large-v3-turbo",
        "ttsProvider": "xai",
        "ttsVariant": "Sal",
    }


def test_synthetic_audio_qa_restricts_core_browser_login_to_local_origins(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic.wav"
    fixture.write_bytes(b"synthetic-audio")
    script = textwrap.dedent(
        f"""
        const {{ parseArgs }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const base = [
          "--audio", {json.dumps(str(fixture))},
          "--output-root", {json.dumps(str(tmp_path))},
          "--verify-core-browser",
        ];
        function rejected(url) {{
          try {{ parseArgs([...base, "--core-url", url]); return false; }}
          catch {{ return true; }}
        }}
        const valid = parseArgs([...base, "--core-url", "http://127.0.0.1:3190"]);
        process.stdout.write(JSON.stringify({{
          enabled: valid.verifyCoreBrowser,
          coreUrl: valid.coreUrl,
          externalRejected: rejected("https://example.com"),
          embeddedCredentialsRejected: rejected("http://user:pass@127.0.0.1:3190"),
          queryRejected: rejected("http://127.0.0.1:3190/?unsafe=1"),
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "enabled": True,
        "coreUrl": "http://127.0.0.1:3190",
        "externalRejected": True,
        "embeddedCredentialsRejected": True,
        "queryRejected": True,
    }


def test_synthetic_audio_qa_core_login_uses_disposable_private_credentials() -> None:
    script = textwrap.dedent(
        f"""
        const path = require("path");
        const {{ createRequire }} = require("module");
        const source = {json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))};
        const librechatRequire = createRequire(path.join(
          {json.dumps(str(ROOT))}, "viventium_v0_4", "LibreChat", "package.json",
        ));
        const bcrypt = librechatRequire("bcryptjs");
        const {{ seedCallSession }} = require(source);
        const records = {{}};
        const db = {{
          collection: name => ({{ insertOne: async record => {{ records[name] = record; }} }}),
        }};
        (async () => {{
          const seeded = await seedCallSession(db, {{
            caseId: "safe-login", agentName: "synthetic-gateway", agentId: "synthetic-main",
            interactive: true, mode: "call", sttProvider: "whisper_local",
            sttVariant: "large-v3-turbo", ttsProvider: "xai", ttsVariant: "Sal",
            verifyCoreBrowser: true,
          }});
          const serialized = JSON.stringify(seeded);
          process.stdout.write(JSON.stringify({{
            syntheticEmail: /^viventium-voice-qa-[a-z0-9-]+@example\\.com$/i.test(seeded.email),
            approved: records.users.viventiumApprovalStatus === "approved",
            passwordHashed: bcrypt.compareSync(seeded.syntheticPassword, records.users.password),
            privatePassword: !serialized.includes(seeded.syntheticPassword),
            passwordStrong: seeded.syntheticPassword.length >= 32,
            signedCallOwnerBound: records.viventiumcallsessions.userId === seeded.userId,
          }}));
        }})().catch(error => {{ process.stderr.write(error.message); process.exitCode = 1; }});
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "syntheticEmail": True,
        "approved": True,
        "passwordHashed": True,
        "privatePassword": True,
        "passwordStrong": True,
        "signedCallOwnerBound": True,
    }


def test_synthetic_audio_qa_captures_actual_remote_audio_as_private_audible_wav(
    tmp_path: Path,
) -> None:
    webm = tmp_path / "remote.webm"
    output = tmp_path / "private-output.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.35",
            "-c:a",
            "libopus",
            str(webm),
        ],
        capture_output=True,
        check=True,
    )
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const {{ inspectAudiblePcmWav, persistCapturedOutputAudio }} =
          require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        (async () => {{
          const page = {{
            evaluate: async () => ({{
              bytes: Array.from(fs.readFileSync({json.dumps(str(webm))})),
            }}),
          }};
          const evidence = await persistCapturedOutputAudio(
            page,
            {json.dumps(str(output))},
          );
          const silent = Buffer.from(fs.readFileSync({json.dumps(str(output))}));
          const data = silent.indexOf(Buffer.from("data"));
          silent.fill(0, data + 8);
          process.stdout.write(JSON.stringify({{
            evidence,
            privateMode: fs.statSync({json.dumps(str(output))}).mode & 0o777,
            silenceRejected: inspectAudiblePcmWav(silent) === null,
            malformedRejected: inspectAudiblePcmWav(Buffer.from("not audio")) === null,
          }}));
        }})().catch(error => {{ process.stderr.write(error.message); process.exitCode = 1; }});
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    actual = json.loads(completed.stdout)

    assert actual["evidence"]["format"] == "wav"
    assert actual["evidence"]["sampleRate"] == 48000
    assert actual["evidence"]["channels"] == 1
    assert actual["evidence"]["peak"] > 32
    assert actual["evidence"]["durationSeconds"] >= 0.3
    assert len(actual["evidence"]["sha256"]) == 64
    assert actual["privateMode"] == 0o600
    assert actual["silenceRejected"] is True
    assert actual["malformedRejected"] is True


def test_synthetic_audio_qa_rejects_unsafe_or_silent_output_capture(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic.wav"
    fixture.write_bytes(b"synthetic-audio")
    output = tmp_path / "private-output.wav"
    script = textwrap.dedent(
        f"""
        const {{ parseArgs }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const base = [
          "--audio", {json.dumps(str(fixture))},
          "--output-root", {json.dumps(str(tmp_path))},
        ];
        function rejected(argv) {{
          try {{ parseArgs(argv); return false; }} catch {{ return true; }}
        }}
        const valid = parseArgs([
          ...base, "--interactive", "--output-audio", {json.dumps(str(output))},
        ]);
        process.stdout.write(JSON.stringify({{
          outputAudio: valid.outputAudio,
          listenOnlyRejected: rejected([
            ...base, "--mode", "listen_only", "--output-audio", {json.dumps(str(output))},
          ]),
          passiveWingRejected: rejected([
            ...base, "--mode", "wing", "--expect-silence", "--output-audio", {json.dumps(str(output))},
          ]),
          outsideRootRejected: rejected([
            ...base, "--interactive", "--output-audio", {json.dumps(str(tmp_path.parent / "outside.wav"))},
          ]),
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "outputAudio": str(output),
        "listenOnlyRejected": True,
        "passiveWingRejected": True,
        "outsideRootRejected": True,
    }


def test_synthetic_audio_qa_starts_audio_evidence_before_the_assistant_can_reply() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    assert content.index("const audioBaselineAtMs = Date.now();") < content.index(
        "const transcript = args.expectSilence"
    )
    assert "async function missedInteractiveObservation" in content
    assert "expected_transcript_not_observed" in content
    assert "audible_playback_not_observed" in content


def test_chrome_call_setup_keeps_browser_capability_out_of_public_tree() -> None:
    content = CHROME_VOICE_SETUP_SCRIPT.read_text()

    assert "VIVENTIUM_QA_OUTPUT_ROOT" in content
    assert "assertPrivateOutputRoot" in content
    assert "mode: 0o700" in content
    assert "mode: 0o600" in content


def test_voice_browser_qa_cleanup_removes_every_call_owned_runtime_record() -> None:
    setup_content = CHROME_VOICE_SETUP_SCRIPT.read_text()
    artifact_content = TTS_ARTIFACT_BROWSER_QA_SCRIPT.read_text()
    synthetic_content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()

    for content in (artifact_content, synthetic_content):
        assert "viventiumvoicetasks" in content
        assert "viventiumvoicespeakersegments" in content
        assert "voiceTasks:" in content
        assert "speakerSegments:" in content

    assert "cleanupCallArtifacts" in setup_content


def test_call_ui_uses_livekit_release_that_seeds_existing_agent_state() -> None:
    package = json.loads(AGENT_STARTER_PACKAGE.read_text())
    lock = AGENT_STARTER_LOCK.read_text()
    expected = {
        "@livekit/components-react": "2.9.25",
        "@livekit/protocol": "1.48.0",
        "livekit-client": "2.23.0",
        "livekit-server-sdk": "2.18.0",
    }
    for name, version in expected.items():
        assert package["dependencies"][name] == version
        assert f"{name}@{version}" in lock
    # Exercise the installed SDK's existing-agent, prewarm, disconnect and End consumer.
    _run_react_contract_suite("lib/call-token-source.sdk.test.tsx")


def test_call_session_hooks_normalize_transient_fetch_failures_and_retry_initial_loads() -> None:
    state_hook = CALL_SESSION_STATE_HOOK_FILE.read_text()
    voice_settings_hook = CALL_SESSION_VOICE_SETTINGS_HOOK_FILE.read_text()

    assert "const INITIAL_STATE_RETRY_MS = 1500;" in state_hook
    assert "const INITIAL_STATE_MAX_ATTEMPTS = 2;" in state_hook
    assert "function isAbortError(error: unknown): boolean {" in state_hook
    assert "error instanceof CallRequestError ? error.retryable : error instanceof TypeError" in state_hook
    assert "Viventium is reconnecting to the voice runtime. Retrying call state..." in state_hook
    assert "Viventium could not reach the voice runtime for call state." in state_hook
    assert "loadState(attempt + 1);" in state_hook
    assert "clearTimeout(retryTimeoutId);" in state_hook

    assert "const INITIAL_LOAD_RETRY_MS = 1500;" in voice_settings_hook
    assert "const INITIAL_LOAD_MAX_ATTEMPTS = 2;" in voice_settings_hook
    assert "const VOICE_SETTINGS_REQUEST_TIMEOUT_MS = 5000;" in voice_settings_hook
    assert "class VoiceSettingsTimeoutError extends CallRequestError" in voice_settings_hook
    assert "function isTransientVoiceSettingsLoadError(error: unknown): boolean {" in voice_settings_hook
    assert "Viventium is reconnecting to the voice runtime. Retrying voice settings..." in voice_settings_hook
    assert "Viventium could not reach the voice runtime for voice settings." in voice_settings_hook
    assert "Viventium could not load voice settings before the voice runtime responded." in voice_settings_hook
    assert "requestController.abort();" in voice_settings_hook
    assert "loadVoiceSettings(attempt + 1);" in voice_settings_hook
    assert "clearTimeout(retryTimeoutId);" in voice_settings_hook


def test_voice_settings_proxy_and_start_hydration_are_timeout_bounded() -> None:
    _run_react_contract_suite('app/api/call-session-voice-settings/route.test.ts')
    _run_react_contract_suite('app/api/token/authority.test.ts')


def test_playground_client_retries_connection_details_fetch_and_hides_raw_browser_fetch_error() -> None:
    _run_react_contract_suite('lib/call-token-source.test.ts')
    _run_react_contract_suite('hooks/useCallStart.test.tsx')


def test_cartesia_playground_selector_exposes_named_voices_not_model_choices() -> None:
    _run_react_contract_suite('components/app/voice-picker.test.tsx')


def test_connection_details_route_uses_the_server_owned_session_route_and_identity() -> None:
    _run_react_contract_suite('app/api/token/authority.test.ts')

    canonical = {
        "callSessionId": "call-owned",
        "roomName": "room-owned",
        "gatewayAgentName": "librechat-voice-gateway",
        "ownerParticipantIdentity": "owner-owned",
        "status": "created",
        "requestedVoiceRoute": {
            "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
            "tts": {"provider": "cartesia", "variant": "saved-voice"},
        },
    }
    configured = {
        "LIVEKIT_API_KEY": "synthetic-key",
        "LIVEKIT_API_SECRET": "synthetic-secret",
        "LIVEKIT_URL": "ws://livekit.example.test",
        "VIVENTIUM_LIBRECHAT_ORIGIN": "https://core.example.test",
        "VIVENTIUM_CALL_SESSION_SECRET": "synthetic-call-secret",
    }
    request = {"room_name": "forged-room", "agentMetadata": json.dumps({
        "callSessionId": "call-owned",
        "requestedVoiceRoute": {"tts": {"provider": "untrusted-browser"}},
    })}
    for record, body, code in (
        (canonical, request, "auth_expired"),
        ({**canonical, "requestedVoiceRoute": None},
         {**request, "room_name": "room-owned"}, "no_route"),
    ):
        result = _run_connection_details_route_case(
            env=configured, request_body=body, fetch_responses=[], canonical_session=record,
        )
        assert result["response"]["status"] == 409
        assert result["response"]["body"]["code"] == code
        assert result["dispatchCalls"] == []
        assert result["roomCalls"] == []
        assert result["tokenRoomConfigs"] == []
        assert len(result["fetchCalls"]) == 1
        assert result["fetchCalls"][0]["url"].endswith("/calls/call-owned/state")


def test_modern_playground_launcher_isolates_next_dev_output_and_allows_public_dev_origins() -> None:
    next_config = NEXT_CONFIG_FILE.read_text()
    ts_config = TS_CONFIG_FILE.read_text()
    launcher = START_SCRIPT.read_text()

    assert "function resolvePlaygroundDistDir()" in next_config
    assert "process.env.VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR" in next_config
    assert "allowedDevOrigins" in next_config
    assert "process.env.VIVENTIUM_PUBLIC_PLAYGROUND_URL" in next_config
    assert '".next-viventium-dev/types/**/*.ts"' in ts_config

    assert 'export VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR="${VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR:-.next-viventium-dev/${VIVENTIUM_RUNTIME_PROFILE}-${PLAYGROUND_PORT}}"' in launcher
    assert 'next_dist_dir="$VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR"' in launcher


def test_modern_playground_dist_output_separates_runtime_ports_and_keeps_override() -> None:
    launcher = START_SCRIPT.read_text()
    export_line = next(
        line.strip() for line in launcher.splitlines()
        if line.strip().startswith('export VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR=')
    )
    def resolve(profile: str, port: str, explicit: str = '') -> str:
        result = subprocess.run(
            ['bash', '-c', export_line + '\nprintf \"%s\" \"$VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR\"'],
            env={**os.environ, 'VIVENTIUM_RUNTIME_PROFILE': profile,
                 'PLAYGROUND_PORT': port, 'VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR': explicit},
            check=True, capture_output=True, text=True,
        )
        return result.stdout
    primary = resolve('isolated', '3300')
    side_by_side = resolve('isolated', '4300')
    other_profile = resolve('compat', '3300')
    assert len({primary, side_by_side, other_profile}) == 3
    assert primary.startswith('.next-viventium-dev/')
    assert side_by_side.startswith('.next-viventium-dev/')
    assert resolve('isolated', '3300', '.next-custom') == '.next-custom'
    assert resolve('isolated', '4300', '.next-custom') == '.next-custom'


def test_modern_playground_launcher_prewarms_voice_startup_routes_before_worker_start() -> None:
    launcher = START_SCRIPT.read_text()

    assert "prewarm_modern_playground_routes()" in launcher
    assert "VIVENTIUM_PLAYGROUND_PREWARM" in launcher
    assert "/api/call-session-voice-settings?callSessionId=viventium-prewarm" in launcher
    assert "/api/call-session-state?callSessionId=viventium-prewarm" in launcher
    prewarm = launcher.split("\nprewarm_modern_playground_routes() {\n", 1)[1].split("\n}\n", 1)[0]
    assert "/api/health" in prewarm
    assert prewarm.index("/api/health") < prewarm.index("/api/call-session-voice-settings")
    assert "/api/connection-details" in launcher
    assert 'wait_for_http "http://localhost:${voice_playground_port}" "${PLAYGROUND_LABEL} before Voice Gateway start"' in launcher
    assert 'prewarm_modern_playground_routes "$voice_playground_port"' in launcher


def test_connection_details_route_runtime_hydrates_dispatch_metadata_from_call_session_voice_settings() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_ALLOW_DIRECT_AGENT_DISPATCH": "true",
        },
        request_body={
            "room_name": "room-123",
            "participant_identity": "user-123",
            "participant_name": "User 123",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-123"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-123/voice-settings",
                "status": 200,
                "json": {
                        "requestedVoiceRoute": {
                            "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
                            "tts": {
                                "provider": "cartesia",
                                "variant": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
                            },
                        }
                    },
                },
            {
                "match": "/api/viventium/calls/call-123/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-123"},
            },
            {
                "match": "/api/viventium/calls/call-123/dispatch/confirm",
                "status": 200,
                "json": {"status": "ok"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-123")
    explicit_metadata = json.loads(dispatch_call["options"]["metadata"])
    assert explicit_metadata["callSessionId"] == "call-123"
    assert explicit_metadata["requestedVoiceRoute"]["stt"] == {
        "provider": "assemblyai",
        "variant": "u3-rt-pro",
    }
    _assert_no_token_dispatch(result)


def test_connection_details_route_accepts_the_exact_server_gateway_claim() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-assigned",
            "participant_identity": "owner-assigned",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-assigned"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-assigned/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-assigned"},
            },
            {
                "match": "/api/viventium/calls/call-assigned/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
    )

    _single_explicit_dispatch(result, room_name="room-assigned")
    assert result["response"]["status"] == 200
    assert any(
        "/api/viventium/calls/call-assigned/dispatch/status?claimId=claim-assigned" in call["url"]
        for call in result["fetchCalls"]
    )
    _assert_no_token_dispatch(result)


def test_connection_details_route_runtime_preserves_existing_requested_voice_route() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_ALLOW_DIRECT_AGENT_DISPATCH": "true",
        },
        request_body={
            "room_name": "room-keep",
            "participant_identity": "user-keep",
            "participant_name": "User Keep",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps(
                {
                    "callSessionId": "call-keep",
                    "requestedVoiceRoute": {
                        "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
                        "tts": {"provider": "local_chatterbox_turbo_mlx_8bit", "variant": "mlx-community/chatterbox-turbo-8bit"},
                    },
                }
            ),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-keep/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-keep"},
            },
            {
                "match": "/api/viventium/calls/call-keep/dispatch/confirm",
                "status": 200,
                "json": {"status": "ok"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-keep")
    assert json.loads(dispatch_call["options"]["metadata"])["requestedVoiceRoute"]["tts"] == {
        "provider": "local_chatterbox_turbo_mlx_8bit",
        "variant": "mlx-community/chatterbox-turbo-8bit",
    }
    _assert_no_token_dispatch(result)
    assert not any(
        call["url"].endswith("/api/viventium/calls/call-keep/voice-settings")
        for call in result["fetchCalls"]
    )


def test_connection_details_route_replaces_browser_metadata_when_legacy_settings_fetch_fails() -> None:
    original_metadata = {
        "callSessionId": "call-fail",
        "note": "keep-me",
    }
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_ALLOW_DIRECT_AGENT_DISPATCH": "true",
        },
        request_body={
            "room_name": "room-fail",
            "participant_identity": "user-fail",
            "participant_name": "User Fail",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps(original_metadata),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-fail/voice-settings",
                "status": 500,
                "json": {"error": "unavailable"},
            },
            {
                "match": "/api/viventium/calls/call-fail/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-fail"},
            },
            {
                "match": "/api/viventium/calls/call-fail/dispatch/confirm",
                "status": 200,
                "json": {"status": "ok"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-fail")
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-fail"
    assert "requestedVoiceRoute" in metadata
    assert "note" not in metadata
    _assert_no_token_dispatch(result)


def test_connection_details_route_replaces_browser_metadata_when_legacy_settings_are_empty() -> None:
    original_metadata = {
        "callSessionId": "call-empty",
        "note": "still-here",
    }
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_ALLOW_DIRECT_AGENT_DISPATCH": "true",
        },
        request_body={
            "room_name": "room-empty",
            "participant_identity": "user-empty",
            "participant_name": "User Empty",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps(original_metadata),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-empty/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-empty/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-empty"},
            },
            {
                "match": "/api/viventium/calls/call-empty/dispatch/confirm",
                "status": 200,
                "json": {"status": "ok"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-empty")
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-empty"
    assert "requestedVoiceRoute" in metadata
    assert "note" not in metadata
    _assert_no_token_dispatch(result)


def test_connection_details_route_creates_explicit_dispatch_for_confirmed_session_after_restart() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-restarted",
            "participant_identity": "user-restarted",
            "participant_name": "User Restarted",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-restarted"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-restarted/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-restarted/dispatch/claim",
                "status": 200,
                "json": {"status": "already"},
            },
            {
                "match": "/api/viventium/calls/call-restarted/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-restarted"},
            },
            {
                "match": "/api/viventium/calls/call-restarted/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
        existing_dispatches=[],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-restarted")
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-restarted"
    assert metadata["dispatchClaimId"] == "claim-restarted"
    _assert_no_token_dispatch(result)
    claim_bodies = [
        json.loads(call["body"])
        for call in result["fetchCalls"]
        if call["url"].endswith("/api/viventium/calls/call-restarted/dispatch/claim")
    ]
    assert claim_bodies[0]["reclaimConfirmed"] is False
    assert claim_bodies[1]["reclaimConfirmed"] is True
    assert len(claim_bodies) == 2


def test_connection_details_route_forces_dispatch_for_claim_winner_with_room_config_listing() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-claim-winner",
            "participant_identity": "user-claim-winner",
            "participant_name": "User Claim Winner",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-claim-winner"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-claim-winner/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-claim-winner/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-winner"},
            },
            {
                "match": "/api/viventium/calls/call-claim-winner/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
        existing_dispatches=[{"id": "AD_room_config", "agentName": "librechat-voice-gateway"}],
        list_dispatch_error=True,
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-claim-winner")
    assert (
        json.loads(dispatch_call["options"]["metadata"])["callSessionId"]
        == "call-claim-winner"
    )


def test_connection_details_route_can_use_token_room_config_dispatch_only_when_configured() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_LIVEKIT_AGENT_DISPATCH_MODE": "token_room_config",
        },
        request_body={
            "room_name": "room-token-config",
            "participant_identity": "user-token-config",
            "participant_name": "User Token Config",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-token-config"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-token-config/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-token-config/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-token-config"},
            },
            {
                "match": "/api/viventium/calls/call-token-config/dispatch/confirm",
                "status": 200,
                "json": {"status": "ok"},
            },
        ],
    )

    assert result["dispatchCalls"] == []
    metadata = json.loads(_token_dispatch_agent(result)["metadata"])
    assert metadata["callSessionId"] == "call-token-config"
    assert metadata["dispatchClaimId"] == "claim-token-config"


def test_connection_details_route_reclaims_token_room_config_through_explicit_dispatch() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_LIVEKIT_AGENT_DISPATCH_MODE": "token_room_config",
        },
        request_body={
            "room_name": "room-token-reconnect",
            "participant_identity": "user-token-reconnect",
            "participant_name": "User Token Reconnect",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-token-reconnect"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-token-reconnect/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-token-reconnect/dispatch/claim",
                "status": 200,
                "json": {"status": "already"},
            },
            {
                "match": "/api/viventium/calls/call-token-reconnect/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-token-reconnect"},
            },
            {
                "match": "/api/viventium/calls/call-token-reconnect/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(
        result, room_name="room-token-reconnect"
    )
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-token-reconnect"
    assert metadata["dispatchClaimId"] == "claim-token-reconnect"
    _assert_no_token_dispatch(result)
    claim_bodies = [
        json.loads(call["body"])
        for call in result["fetchCalls"]
        if call["url"].endswith(
            "/api/viventium/calls/call-token-reconnect/dispatch/claim"
        )
    ]
    assert [body["reclaimConfirmed"] for body in claim_bodies] == [False, True]


def test_connection_details_watchdog_reclaim_is_explicit_in_token_room_config_mode() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_LIVEKIT_AGENT_DISPATCH_MODE": "token_room_config",
        },
        request_body={
            "room_name": "room-token-watchdog",
            "participant_identity": "user-token-watchdog",
            "participant_name": "User Token Watchdog",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-token-watchdog"}),
            "reclaimDispatch": True,
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-token-watchdog/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-token-watchdog/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-token-watchdog"},
            },
            {
                "match": "/api/viventium/calls/call-token-watchdog/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
    )

    dispatch_call = _single_explicit_dispatch(
        result, room_name="room-token-watchdog"
    )
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-token-watchdog"
    assert metadata["dispatchClaimId"] == "claim-token-watchdog"
    _assert_no_token_dispatch(result)


def test_connection_details_route_keeps_existing_livekit_dispatch_for_confirmed_session() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
            "VIVENTIUM_LIVEKIT_AGENT_DISPATCH_MODE": "token_room_config",
        },
        request_body={
            "room_name": "room-already-live",
            "participant_identity": "user-already-live",
            "participant_name": "User Already Live",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-already-live"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-already-live/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-already-live/dispatch/claim",
                "status": 200,
                "json": {"status": "already"},
            },
        ],
        existing_dispatches=[{"id": "AD_existing", "agentName": "librechat-voice-gateway"}],
    )

    assert result["dispatchCalls"] == []
    _assert_no_token_dispatch(result)


def test_connection_details_route_creates_explicit_dispatch_when_list_only_shows_room_config_agent() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-token-config-listed",
            "participant_identity": "user-token-config-listed",
            "participant_name": "User Token Config Listed",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-token-config-listed"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-token-config-listed/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-token-config-listed/dispatch/claim",
                "status": 200,
                "json": {"status": "already"},
            },
            {
                "match": "/api/viventium/calls/call-token-config-listed/dispatch/claim",
                "status": 200,
                "json": {"status": "claimed", "claimId": "claim-token-config-listed"},
            },
            {
                "match": "/api/viventium/calls/call-token-config-listed/dispatch/confirm",
                "status": 200,
                "json": {"status": "created"},
            },
        ],
        existing_dispatches=[{"id": "", "agentName": "librechat-voice-gateway"}],
    )

    dispatch_call = _single_explicit_dispatch(result, room_name="room-token-config-listed")
    metadata = json.loads(dispatch_call["options"]["metadata"])
    assert metadata["callSessionId"] == "call-token-config-listed"
    assert metadata["dispatchClaimId"] == "claim-token-config-listed"
    _assert_no_token_dispatch(result)


def test_connection_details_route_does_not_duplicate_dispatch_while_claim_in_flight() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-in-flight",
            "participant_identity": "user-in-flight",
            "participant_name": "User In Flight",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-in-flight"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-in-flight/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-in-flight/dispatch/claim",
                "status": 200,
                "json": {"status": "in_flight"},
            },
        ],
        existing_dispatches=[],
    )

    assert result["dispatchCalls"] == []
    _assert_no_token_dispatch(result)


def test_connection_details_route_fails_closed_when_dispatch_claim_fails_before_token_issue() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-claim-error",
            "participant_identity": "user-claim-error",
            "participant_name": "User Claim Error",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-claim-error"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-claim-error/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-claim-error/dispatch/claim",
                "status": 503,
                "json": {"error": "unavailable"},
            },
        ],
    )

    assert result["response"]["status"] == 503
    assert result["dispatchCalls"] == []
    assert result["tokenRoomConfigs"] == []
    claim_calls = [
        call
        for call in result["fetchCalls"]
        if call["url"].endswith("/api/viventium/calls/call-claim-error/dispatch/claim")
    ]
    assert len(claim_calls) == 1


def test_connection_details_route_rejects_expired_call_session_before_token_issue() -> None:
    result = _run_connection_details_route_case(
        env={
            "LIVEKIT_API_KEY": "lk-api-key",
            "LIVEKIT_API_SECRET": "lk-api-secret",
            "LIVEKIT_URL": "ws://localhost:7888",
            "LIVEKIT_API_HOST": "http://localhost:7888",
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://librechat.local",
            "VIVENTIUM_CALL_SESSION_SECRET": "call-secret",
        },
        request_body={
            "room_name": "room-expired",
            "participant_identity": "user-expired",
            "participant_name": "User Expired",
            "agentName": "librechat-voice-gateway",
            "agentMetadata": json.dumps({"callSessionId": "call-expired"}),
        },
        fetch_responses=[
            {
                "match": "/api/viventium/calls/call-expired/voice-settings",
                "status": 200,
                "json": {},
            },
            {
                "match": "/api/viventium/calls/call-expired/dispatch/claim",
                "status": 200,
                "json": {"status": "expired"},
            },
        ],
        existing_dispatches=[],
    )

    assert result["response"]["status"] == 410
    assert "expired" in result["response"]["body"]["message"]
    assert result["dispatchCalls"] == []
    assert result["tokenRoomConfigs"] == []


def test_connection_details_route_uses_public_livekit_only_for_configured_public_playground_origin() -> None:
    _run_react_contract_suite('lib/viventium/livekit-url.test.ts')
    _run_react_contract_suite('app/api/token/authority.test.ts')



def test_synthetic_audio_qa_uses_declared_voice_pipeline_capabilities() -> None:
    script = textwrap.dedent(
        f"""
        const {{ voicePipelineSupported }} = require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const route = {{ provider: "synthetic-provider", model: "synthetic-high" }};
        const cases = [
          [true, route, {{ "synthetic-provider": {{ voice_pipeline_llm: true }} }}],
          [true, route, {{ "synthetic-provider": {{ realtime_voice: true }} }}],
          [true, route, {{ "synthetic-provider": {{ voice_pipeline_llm: false, realtime_voice: false }} }}],
          [true, route, {{}}],
          [true, route, {{ "other-provider": {{ voice_pipeline_llm: true }} }}],
          [true, route, {{ "synthetic-provider": {{ voice_pipeline_llm: "true" }} }}],
          [false, route, {{ "synthetic-provider": {{ voice_pipeline_llm: true }} }}],
          [true, null, {{ "synthetic-provider": {{ voice_pipeline_llm: true }} }}],
          [true, {{ provider: "glasshive-harness", model: "synthetic-high" }},
            {{ "glasshive-harness": {{ voice_pipeline_llm: true, realtime_voice: false }} }}],
        ];
        process.stdout.write(JSON.stringify(cases.map((args) => voicePipelineSupported(...args))));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, check=True, text=True,
    )
    assert json.loads(completed.stdout) == [True, True, False, False, False, False, False, False, True]


def test_synthetic_audio_qa_reads_the_compiled_capability_registry(tmp_path: Path) -> None:
    config = tmp_path / "compiled.yaml"
    config.write_text(
        "endpoints:\n  agents:\n    providerCapabilities:\n"
        "      synthetic-provider:\n        voice_pipeline_llm: true\n        realtime_voice: false\n"
    )
    missing_registry = tmp_path / "missing-registry.yaml"
    missing_registry.write_text("endpoints:\n  agents: {}\n")
    malformed_config = tmp_path / "malformed.yaml"
    malformed_config.write_text("endpoints: [\n")
    script = textwrap.dedent(
        f"""
        const {{ readCompiledProviderCapabilities, voicePipelineSupported }} =
          require({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))});
        const route = {{ provider: "synthetic-provider", model: "synthetic-high" }};
        process.env.CONFIG_PATH = {json.dumps(str(config))};
        const registry = readCompiledProviderCapabilities();
        let missingConfigRejected = false;
        let malformedConfigRejected = false;
        try {{ readCompiledProviderCapabilities({json.dumps(str(tmp_path / "absent.yaml"))}); }}
        catch {{ missingConfigRejected = true; }}
        try {{ readCompiledProviderCapabilities({json.dumps(str(malformed_config))}); }}
        catch {{ malformedConfigRejected = true; }}
        process.stdout.write(JSON.stringify({{
          registry, missingConfigRejected, malformedConfigRejected,
          supported: voicePipelineSupported(true, route, registry),
          missingRegistry: voicePipelineSupported(true, route,
            readCompiledProviderCapabilities({json.dumps(str(missing_registry))})),
        }}));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, check=True, text=True,
    )
    assert json.loads(completed.stdout) == {
        "registry": {"synthetic-provider": {"voice_pipeline_llm": True, "realtime_voice": False}},
        "supported": True,
        "missingRegistry": False,
        "missingConfigRejected": True,
        "malformedConfigRejected": True,
    }


def test_synthetic_audio_qa_checks_pipeline_capability_for_speech_and_wing() -> None:
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const source = fs.readFileSync({json.dumps(str(SYNTHETIC_AUDIO_QA_SCRIPT))}, "utf8");
        const start = source.indexOf("    result.transportOk =");
        const end = source.indexOf("    result.ok = result.transportOk;", start);
        if (start < 0 || end < 0) throw new Error("transport_contract_missing");
        const evaluate = new Function("result", "args", "pageErrors",
          source.slice(start, end) + "return result.transportOk;");
        const healthy = {{
          seeded: true, autoConnected: true, microphonePublished: true, rtcConnected: true,
          zeroSetupStartActions: 0, activeJobPresent: true, transcriptCount: 1,
          transcriptCountWithinLimit: true, transcriptMatchedExpected: true,
          listenOnlyIsolationObserved: true, intentionalSilenceObserved: true,
          interactiveTurnCompleted: true, assistantResponsePresent: true,
          deliveredAudioPresent: true, playbackCompleted: true,
        }};
        const cases = [];
        for (const expectSilence of [false, true]) {{
          for (const supported of [true, false]) {{
            cases.push(evaluate({{ ...healthy, voiceLlmProviderSupportsPipeline: supported,
              voiceLlmProviderIsIndependent: !supported }},
              {{ interactive: true, expectSilence }}, []));
          }}
        }}
        cases.push(evaluate({{ ...healthy, voiceLlmProviderSupportsPipeline: false }},
          {{ interactive: false, expectSilence: false }}, []));
        process.stdout.write(JSON.stringify(cases));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, check=True, text=True,
    )
    assert json.loads(completed.stdout) == [True, False, True, False, True]


def test_synthetic_audio_qa_keeps_browser_network_security_checks() -> None:
    content = SYNTHETIC_AUDIO_QA_SCRIPT.read_text()
    assert "--disable-features=LocalNetworkAccessChecks" not in content
    assert '"--use-fake-ui-for-media-stream"' in content
    assert '"--use-fake-device-for-media-stream"' in content
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in content
