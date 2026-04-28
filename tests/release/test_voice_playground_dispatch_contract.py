import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_FILE = ROOT / "viventium_v0_4" / "agent-starter-react" / "components" / "app" / "app.tsx"
VOICE_ROUTE_HOOK_FILE = ROOT / "viventium_v0_4" / "agent-starter-react" / "hooks" / "useVoiceRoute.ts"
ROUTE_FILE = (
    ROOT / "viventium_v0_4" / "agent-starter-react" / "app" / "api" / "connection-details" / "route.ts"
)
NEXT_CONFIG_FILE = ROOT / "viventium_v0_4" / "agent-starter-react" / "next.config.ts"
TS_CONFIG_FILE = ROOT / "viventium_v0_4" / "agent-starter-react" / "tsconfig.json"
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
TYPESCRIPT_FILE = (
    ROOT
    / "viventium_v0_4"
    / "agent-starter-react"
    / "node_modules"
    / "typescript"
    / "lib"
    / "typescript.js"
)


def _run_connection_details_route_case(
    *,
    env: dict[str, str],
    request_body: dict[str, object],
    fetch_responses: list[dict[str, object]],
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
        }};

        for (const [key, value] of Object.entries(caseData.env)) {{
          process.env[key] = value;
        }}

        const dispatchCalls = [];
        const fetchCalls = [];

        class FakeAccessToken {{
          constructor(_apiKey, _apiSecret, options) {{
            this.identity = options?.identity ?? '';
          }}

          addGrant() {{}}

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
            return [];
          }}

          async createDispatch(roomName, agentName, options) {{
            dispatchCalls.push({{ roomName, agentName, options }});
            return {{ roomName, agentName, options }};
          }}
        }}

        class FakeRoomConfiguration {{
          static fromJson(value) {{
            return value;
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
          const match = caseData.fetchResponses.find((item) => urlText.endsWith(String(item.match)));
          if (!match) {{
            throw new Error(`Unexpected fetch: ${{urlText}}`);
          }}
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
              AgentDispatchClient: FakeAgentDispatchClient,
            }};
          }}
          if (specifier === '@livekit/protocol') {{
            return {{ RoomConfiguration: FakeRoomConfiguration }};
          }}
          return require(specifier);
        }};

        const routeModule = new Module(routePath, module);
        routeModule.filename = routePath;
        routeModule.paths = Module._nodeModulePaths(path.dirname(routePath));
        routeModule.require = fakeRequire;
        routeModule._compile(transpiled.outputText, routePath);

        const request = {{
          headers: new Headers({{ 'content-type': 'application/json' }}),
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
                fetchCalls,
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
        check=True,
        cwd=ROOT,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise AssertionError("connection-details harness returned no stdout")
    payload_line = stdout.splitlines()[-1]
    return json.loads(payload_line)


def test_playground_client_merges_deeplink_token_options_into_connection_details_request() -> None:
    content = APP_FILE.read_text()

    assert "function getConnectionDetailsTokenSource(fallbackOptions?: AgentTokenOptions)" in content
    assert "const mergedOptions = {" in content
    assert "...(fallbackOptions ?? {})," in content
    assert "...(options ?? {})," in content
    assert "body: JSON.stringify(mergedOptions)" in content
    assert ": getConnectionDetailsTokenSource(effectiveTokenOptions);" in content


def test_connection_details_route_recovers_agent_dispatch_inputs_from_deeplink_referer() -> None:
    content = ROUTE_FILE.read_text()

    assert "function extractDeepLinkFallbacks(req: Request)" in content
    assert "const referer = req.headers.get('referer') || req.headers.get('referrer') || '';" in content
    assert "const deepLinkFallbacks = extractDeepLinkFallbacks(req);" in content
    assert "if (!options.agentName && deepLinkFallbacks.agentName)" in content
    assert "if (!currentCallSessionId && deepLinkFallbacks.callSessionId)" in content
    assert "const metadata = JSON.stringify({ callSessionId: deepLinkFallbacks.callSessionId });" in content


def test_call_session_deeplink_requires_browser_mic_gesture_before_connect() -> None:
    content = APP_FILE.read_text()

    assert "const shouldAutoConnect = params.get('autoConnect') === '1';" in content
    assert "autoConnect: shouldAutoConnect && !callSessionId," in content
    assert "Tap Start chat to turn on your mic. Viventium joins right after." in content


def test_call_session_playground_extends_agent_join_timeout_for_local_cold_starts() -> None:
    content = APP_FILE.read_text()

    assert "const VIVENTIUM_CALL_AGENT_CONNECT_TIMEOUT_MS = 90_000;" in content
    assert "agentConnectTimeoutMilliseconds: expectedCallSessionId" in content
    assert "? VIVENTIUM_CALL_AGENT_CONNECT_TIMEOUT_MS" in content


def test_cartesia_playground_selector_exposes_named_voices_not_model_choices() -> None:
    content = VOICE_ROUTE_HOOK_FILE.read_text()

    assert "const CARTESIA_MEGAN_VOICE_ID = 'e8e5fffb-252c-436d-b842-8879b84445b6';" in content
    assert "const CARTESIA_LYRA_VOICE_ID = '6ccbfb76-1fc6-48f7-b71d-91ac6298247b';" in content
    assert "{ id: CARTESIA_MEGAN_VOICE_ID, label: 'Megan' }" in content
    assert "{ id: CARTESIA_LYRA_VOICE_ID, label: 'Lyra' }" in content
    assert "variantLabel: 'Voice'" in content
    assert "{ id: 'sonic-2', label: 'sonic-2' }" not in content
    assert "{ id: 'sonic-3', label: 'sonic-3' }" not in content


def test_connection_details_route_hydrates_requested_voice_route_from_call_session_settings() -> None:
    content = ROUTE_FILE.read_text()

    assert "async function fetchCallSessionVoiceSettings(" in content
    assert "async function hydrateAgentMetadataWithVoiceSettings(" in content
    assert "const authoritativeRequestedVoiceRoute =" in content
    assert "voiceSettings?.requestedVoiceRoute ?? voiceSettings?.savedVoiceRoute" in content
    assert "Hydrated Viventium requestedVoiceRoute from authoritative call-session settings" in content
    assert "requestedVoiceRoute: authoritativeRequestedVoiceRoute" in content
    assert "const hydratedAgentMetadata = await hydrateAgentMetadataWithVoiceSettings(" in content


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
                            "stt": {"provider": "assemblyai", "variant": "universal-streaming"},
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

    dispatch_calls = result["dispatchCalls"]
    assert len(dispatch_calls) == 1
    metadata = json.loads(dispatch_calls[0]["options"]["metadata"])
    assert metadata["callSessionId"] == "call-123"
    assert metadata["requestedVoiceRoute"]["tts"] == {
        "provider": "cartesia",
        "variant": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
    }
    assert metadata["requestedVoiceRoute"]["stt"] == {
        "provider": "assemblyai",
        "variant": "universal-streaming",
    }


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
                        "stt": {"provider": "assemblyai", "variant": "universal-streaming"},
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

    dispatch_calls = result["dispatchCalls"]
    assert len(dispatch_calls) == 1
    metadata = json.loads(dispatch_calls[0]["options"]["metadata"])
    assert metadata["requestedVoiceRoute"]["tts"] == {
        "provider": "local_chatterbox_turbo_mlx_8bit",
        "variant": "mlx-community/chatterbox-turbo-8bit",
    }
    assert not any(
        call["url"].endswith("/api/viventium/calls/call-keep/voice-settings")
        for call in result["fetchCalls"]
    )


def test_connection_details_route_runtime_keeps_original_metadata_when_voice_settings_fetch_fails() -> None:
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

    dispatch_calls = result["dispatchCalls"]
    assert len(dispatch_calls) == 1
    metadata = json.loads(dispatch_calls[0]["options"]["metadata"])
    assert metadata == original_metadata


def test_connection_details_route_runtime_keeps_original_metadata_when_voice_settings_have_no_route() -> None:
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

    dispatch_calls = result["dispatchCalls"]
    assert len(dispatch_calls) == 1
    metadata = json.loads(dispatch_calls[0]["options"]["metadata"])
    assert metadata == original_metadata


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
