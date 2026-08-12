import json
import os
import subprocess
import textwrap
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
TYPESCRIPT_FILE = AGENT_STARTER_REACT_ROOT / "node_modules" / "typescript" / "lib" / "typescript.js"


def _run_connection_details_route_case(
    *,
    env: dict[str, str],
    request_body: dict[str, object],
    fetch_responses: list[dict[str, object]],
    existing_dispatches: list[dict[str, object]] | None = None,
    list_dispatch_error: bool = False,
    dispatch_job_status: int = 1,
    dispatch_worker_claimed: bool = True,
) -> dict[str, object]:
    script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const path = require('path');
        const Module = require('module');
        const ts = require({json.dumps(str(TYPESCRIPT_FILE))});

        const routePath = {json.dumps(str(ROUTE_FILE))};
        const source = fs.readFileSync(routePath, 'utf8');
        const transpiled = ts.transpileModule(source, {{
          compilerOptions: {{
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
            esModuleInterop: true,
          }},
          fileName: routePath,
        }});

        const caseData = {{
          env: {json.dumps(env)},
          requestBody: {json.dumps(request_body)},
          fetchResponses: {json.dumps(fetch_responses)},
          existingDispatches: {json.dumps(existing_dispatches or [])},
          listDispatchError: {json.dumps(list_dispatch_error)},
          dispatchJobStatus: {json.dumps(dispatch_job_status)},
          dispatchWorkerClaimed: {json.dumps(dispatch_worker_claimed)},
        }};

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
          if (specifier === '@/lib/call-proxy') {{
            return {{
              parseCallIdentifier(value) {{
                return typeof value === 'string' && /^[A-Za-z0-9_-]{{1,200}}$/.test(value)
                  ? value
                  : null;
              }},
            }};
          }}
          if (specifier === '@/lib/call-browser-capability') {{
            const CALL_CAPABILITY_HEADER = 'X-VIVENTIUM-CALL-CAPABILITY';
            return {{
              CALL_CAPABILITY_HEADER,
              readRequestCallBrowserCapability(request) {{
                const value = request?.headers?.get(CALL_CAPABILITY_HEADER);
                return typeof value === 'string' && value.length > 0 ? value : null;
              }},
            }};
          }}
          if (specifier === '@/lib/authoritative-call-session') {{
            class AuthoritativeCallSessionError extends Error {{
              constructor(code, message, status, retryable) {{
                super(message);
                this.code = code;
                this.status = status;
                this.retryable = retryable;
              }}
            }}
            return {{
              AuthoritativeCallSessionError,
              async fetchAuthoritativeCallSession(callSessionId, browserCapability) {{
                if (!browserCapability) {{
                  throw new AuthoritativeCallSessionError(
                    'auth_expired',
                    'The call capability is missing or invalid.',
                    401,
                    false
                  );
                }}
                let metadata = {{}};
                try {{ metadata = JSON.parse(caseData.requestBody.agentMetadata || '{{}}'); }} catch {{}}
                const settings = caseData.fetchResponses.find((item) =>
                  String(item.match).endsWith(`/api/viventium/calls/${{callSessionId}}/voice-settings`)
                );
                const requestedVoiceRoute =
                  settings?.json?.requestedVoiceRoute ||
                  metadata.requestedVoiceRoute || {{
                    stt: {{ provider: 'assemblyai', variant: 'u3-rt-pro' }},
                    tts: {{ provider: 'local_chatterbox_turbo_mlx_8bit', variant: 'local' }},
                  }};
                return {{
                  callSessionId,
                  roomName: caseData.requestBody.room_name || `room-${{callSessionId}}`,
                  gatewayAgentName: caseData.requestBody.agentName || 'librechat-voice-gateway',
                  ownerParticipantIdentity:
                    caseData.requestBody.participant_identity || `owner-${{callSessionId}}`,
                  status: 'created',
                  requestedVoiceRoute,
                }};
              }},
              applyAuthoritativeCallSession(options, canonical) {{
                options.room_name = canonical.roomName;
                options.roomName = canonical.roomName;
                options.participant_identity = canonical.ownerParticipantIdentity;
                options.participantIdentity = canonical.ownerParticipantIdentity;
                options.agentName = canonical.gatewayAgentName;
                options.agentMetadata = JSON.stringify({{
                  callSessionId: canonical.callSessionId,
                  requestedVoiceRoute: canonical.requestedVoiceRoute,
                }});
              }},
            }};
          }}
          if (specifier === 'livekit-server-sdk') {{
            return {{
              AccessToken: FakeAccessToken,
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
          return require(specifier);
        }};

        const routeModule = new Module(routePath, module);
        routeModule.filename = routePath;
        routeModule.paths = Module._nodeModulePaths(path.dirname(routePath));
        routeModule.require = fakeRequire;
        routeModule._compile(transpiled.outputText, routePath);

        const request = {{
          headers: new Headers({{
            'content-type': 'application/json',
            'X-VIVENTIUM-CALL-CAPABILITY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
          }}),
          async json() {{
            return caseData.requestBody;
          }},
        }};

        Promise.resolve(routeModule.exports.POST(request))
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
    content = APP_FILE.read_text()

    assert "const CONNECTION_DETAILS_CACHE_MS = 2_000;" in content
    assert "function getConnectionDetailsTokenSource(fallbackOptions?: AgentTokenOptions)" in content
    assert "type ConnectionDetailsCacheEntry = {" in content
    assert "const connectionDetailsCache = new Map<string, ConnectionDetailsCacheEntry>();" in content
    assert "function stableCacheStringify(value: unknown): string {" in content
    assert ".sort(([left], [right]) => left.localeCompare(right));" in content
    assert "const mergedOptions = {" in content
    assert "...(fallbackOptions ?? {})," in content
    assert "...(options ?? {})," in content
    assert "const cacheKey = stableCacheStringify(mergedOptions);" in content
    assert "const cached = connectionDetailsCache.get(cacheKey);" in content
    assert "if (cached.promise) {" in content
    assert "return cached.promise;" in content
    assert "Date.now() - cached.createdAt < CONNECTION_DETAILS_CACHE_MS" in content
    assert "if (connectionDetailsCache.get(cacheKey)?.promise === connectionDetailsPromise)" in content
    assert "connectionDetailsCache.delete(cacheKey);" in content
    assert "body: JSON.stringify(mergedOptions)" in content
    assert ": getConnectionDetailsTokenSource(effectiveTokenOptions);" in content


def test_connection_details_route_accepts_only_call_session_identity_from_deeplink() -> None:
    content = ROUTE_FILE.read_text()

    assert "function extractDeepLinkFallbacks(req: Request)" in content
    assert "const referer = req.headers.get('referer') || req.headers.get('referrer') || '';" in content
    assert "const deepLinkFallbacks = extractDeepLinkFallbacks(req);" in content
    assert "const currentCallSessionId = parseCallIdentifier(" in content
    assert "const browserCapability = readRequestCallBrowserCapability(req);" in content
    assert "const canonical = await fetchAuthoritativeCallSession(" in content
    assert "currentCallSessionId," in content
    assert "browserCapability" in content
    assert "applyAuthoritativeCallSession(options, canonical);" in content
    assert "!currentCallSessionId &&" in content
    assert "!VIVENTIUM_LIBRECHAT_ORIGIN &&" in content
    assert "!VIVENTIUM_CALL_SESSION_SECRET &&" in content
    assert "!ALLOW_DIRECT_AGENT_DISPATCH &&" in content
    assert "deepLinkFallbacks.agentName" in content


def test_signed_call_session_deeplink_autoconnects_without_an_app_setup_step() -> None:
    app = APP_FILE.read_text()
    call_start = (AGENT_STARTER_REACT_ROOT / "lib" / "call-start.ts").read_text()

    assert "autoConnect: params.get('autoConnect') === '1'," in call_start
    assert "if (deepLink.autoConnect)" in app
    assert "setAutoConnect(true);" in app
    assert "if (!autoConnect || hasAutoStarted || !canStartCall)" in app
    assert "startCall().finally(() =>" in app
    assert "Tap Start chat to turn on your mic" not in app


def test_call_session_start_click_is_single_flight_and_disables_duplicate_starts() -> None:
    content = APP_FILE.read_text()

    assert "const [isStartInProgress, setIsStartInProgress] = useState(autoConnect && canStartCall);" in content
    assert "const startPromiseRef = useRef<Promise<boolean> | null>(null);" in content
    assert "if (startPromiseRef.current) {" in content
    assert "return startPromiseRef.current;" in content
    assert "setIsStartInProgress(true);" in content
    assert "startPromiseRef.current = startPromise;" in content
    assert "startPromiseRef.current = null;" in content
    assert "const START_LATCH_WATCHDOG_MS = 1_000;" in content
    assert "const effectiveCanStartCall = canStartCall && !isStartInProgress && !hasEnded;" in content
    assert "Starting call..." in content


def test_voice_route_preflight_blocks_connection_until_the_exact_saved_route_is_valid() -> None:
    content = APP_FILE.read_text()

    assert "const voiceSettingsStillLoading = Boolean(expectedCallSessionId) && voiceSettings.isLoading;" in content
    assert "!voiceSettings.isSaving &&" in content
    assert "!voiceSettingsStillLoading" in content
    assert "!voiceSettings.error" in content
    assert "hasAuthoritativeRoute" in content
    assert "Preparing your configured voice route..." in content
    assert "Viventium did not switch providers automatically." in content


def test_call_session_playground_extends_agent_join_timeout_for_local_cold_starts() -> None:
    content = APP_FILE.read_text()

    assert "const VIVENTIUM_CALL_AGENT_CONNECT_TIMEOUT_MS = 90_000;" in content
    assert "agentConnectTimeoutMilliseconds: expectedCallSessionId" in content
    assert "? VIVENTIUM_CALL_AGENT_CONNECT_TIMEOUT_MS" in content


def test_explicit_dispatch_call_connects_room_before_enabling_microphone() -> None:
    content = APP_FILE.read_text()

    assert "const shouldDeferMicrophoneUntilConnected = Boolean(expectedCallSessionId || appConfig.agentName);" in content
    assert "const startSession = useCallback(async () => {" in content
    assert "await session.start();" in content
    assert "await session.start({" in content
    assert "microphone: {" in content
    assert "enabled: false," in content
    assert "setIsMicrophoneStartupPending(true);" in content
    assert "const MICROPHONE_START_TIMEOUT_MS = 15_000;" in content
    assert "const permissionState = await queryMicrophonePermissionState();" in content
    assert "await enableCallMicrophone({" in content
    assert "permissionState," in content
    assert "enable: () => session.room.localParticipant.setMicrophoneEnabled(true)," in content
    assert "disable: () => session.room.localParticipant.setMicrophoneEnabled(false)," in content
    assert "grantedTimeoutMs: MICROPHONE_START_TIMEOUT_MS," in content
    assert "classifyCallIssue" in content
    assert "const issue = classifyCallIssue(error);" in content
    assert "setStartError(issue);" in content
    assert "Turning on your microphone..." in content
    assert "Turning on mic..." in content
    assert "await session.end().catch((disconnectError) => {" in content
    assert "useConnectionRecovery({" in content
    assert "start: startSession," in content
    assert "await startSession();" in content


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
    assert "call-session-voice-settings?callSessionId=viventium-prewarm" in content
    assert "call-session-state?callSessionId=viventium-prewarm" in content
    assert "GET intentionally exercises the Next.js route module compile without issuing a token." in content
    assert "connection-details route did not prewarm before timeout" in content


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
    assert 'iceTransportPolicy: forceRelay ? "relay"' in content
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
    proxy_route = CALL_SESSION_VOICE_SETTINGS_ROUTE_FILE.read_text()
    authoritative_session = AUTHORITATIVE_CALL_SESSION_FILE.read_text()

    assert "const VOICE_SETTINGS_PROXY_TIMEOUT_MS = 4500;" in proxy_route
    assert "function getVoiceSettingsProxyTimeoutMs()" in proxy_route
    assert "VIVENTIUM_VOICE_SETTINGS_PROXY_TIMEOUT_MS" in proxy_route
    assert "controller.abort();" in proxy_route
    assert "status: 504" in proxy_route
    assert "Viventium could not load voice settings before the voice runtime responded." in proxy_route

    assert "function canonicalRequestTimeoutMs()" in authoritative_session
    assert "VIVENTIUM_CALL_SESSION_VOICE_SETTINGS_TIMEOUT_MS" in authoritative_session
    assert "signal: controller.signal" in authoritative_session
    assert "controller.abort();" in authoritative_session
    assert "timedOut ? 504 : 503" in authoritative_session


def test_playground_client_retries_connection_details_fetch_and_hides_raw_browser_fetch_error() -> None:
    content = APP_FILE.read_text()

    assert "const CONNECTION_DETAILS_RETRY_MS = 1500;" in content
    assert "const CONNECTION_DETAILS_MAX_ATTEMPTS = 2;" in content
    assert "error instanceof TypeError && attempt + 1 < CONNECTION_DETAILS_MAX_ATTEMPTS" in content
    assert "await wait(CONNECTION_DETAILS_RETRY_MS);" in content
    assert "Viventium could not reach the voice runtime." in content
    assert "const issue = classifyCallIssue(error);" in content
    assert "setStartError(issue);" in content


def test_cartesia_playground_selector_exposes_named_voices_not_model_choices() -> None:
    content = VOICE_ROUTE_HOOK_FILE.read_text()

    assert "const CARTESIA_MEGAN_VOICE_ID = 'e8e5fffb-252c-436d-b842-8879b84445b6';" in content
    assert "const CARTESIA_LYRA_VOICE_ID = '6ccbfb76-1fc6-48f7-b71d-91ac6298247b';" in content
    assert "{ id: CARTESIA_MEGAN_VOICE_ID, label: 'Megan' }" in content
    assert "{ id: CARTESIA_LYRA_VOICE_ID, label: 'Lyra' }" in content
    assert "variantLabel: 'Voice'" in content
    assert "{ id: 'sonic-2', label: 'sonic-2' }" not in content
    assert "{ id: 'sonic-3', label: 'sonic-3' }" not in content


def test_connection_details_route_uses_the_server_owned_session_route_and_identity() -> None:
    route = ROUTE_FILE.read_text()
    authoritative = AUTHORITATIVE_CALL_SESSION_FILE.read_text()

    assert "fetchAuthoritativeCallSession" in route
    assert "applyAuthoritativeCallSession" in route
    assert "roomName" in authoritative
    assert "gatewayAgentName" in authoritative
    assert "ownerParticipantIdentity" in authoritative
    assert "requestedVoiceRoute" in authoritative
    assert "options.room_name = canonical.roomName;" in authoritative
    assert "options.participant_identity = canonical.ownerParticipantIdentity;" in authoritative
    assert "options.agentName = canonical.gatewayAgentName;" in authoritative
    assert "requestedVoiceRoute: canonical.requestedVoiceRoute" in authoritative


def test_modern_playground_launcher_isolates_next_dev_output_and_allows_public_dev_origins() -> None:
    next_config = NEXT_CONFIG_FILE.read_text()
    ts_config = TS_CONFIG_FILE.read_text()
    launcher = START_SCRIPT.read_text()

    assert "function resolvePlaygroundDistDir()" in next_config
    assert "process.env.VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR" in next_config
    assert "allowedDevOrigins" in next_config
    assert "process.env.VIVENTIUM_PUBLIC_PLAYGROUND_URL" in next_config
    assert '".next-viventium-dev/types/**/*.ts"' in ts_config

    assert 'export VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR="${VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR:-.next-viventium-dev}"' in launcher
    assert 'next_dist_dir="$VIVENTIUM_PLAYGROUND_NEXT_DIST_DIR"' in launcher


def test_modern_playground_launcher_prewarms_voice_startup_routes_before_worker_start() -> None:
    launcher = START_SCRIPT.read_text()

    assert "prewarm_modern_playground_routes()" in launcher
    assert "VIVENTIUM_PLAYGROUND_PREWARM" in launcher
    assert "/api/call-session-voice-settings?callSessionId=viventium-prewarm" in launcher
    assert "/api/call-session-state?callSessionId=viventium-prewarm" in launcher
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
    content = ROUTE_FILE.read_text()

    assert "const VIVENTIUM_PUBLIC_PLAYGROUND_URL = process.env.VIVENTIUM_PUBLIC_PLAYGROUND_URL;" in content
    assert "const VIVENTIUM_PUBLIC_LIVEKIT_URL = process.env.VIVENTIUM_PUBLIC_LIVEKIT_URL;" in content
    assert "function normalizeOrigin(value: string | undefined): string | null {" in content
    assert "function requestOrigin(req: Request): string | null {" in content
    assert "const forwardedProto = (req.headers.get('x-forwarded-proto') || '').trim();" in content
    assert "function resolveBrowserLiveKitUrl(req: Request): string | undefined {" in content
    assert "const publicPlaygroundOrigin = normalizeOrigin(VIVENTIUM_PUBLIC_PLAYGROUND_URL);" in content
    assert "requestOrigin(req) === publicPlaygroundOrigin" in content
    assert "return publicLivekitUrl;" in content
    assert "return NEXT_PUBLIC_LIVEKIT_URL ?? LIVEKIT_URL;" in content
    assert "const browserLiveKitUrl = resolveBrowserLiveKitUrl(req);" in content
    assert "serverUrl: browserLiveKitUrl," in content


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
