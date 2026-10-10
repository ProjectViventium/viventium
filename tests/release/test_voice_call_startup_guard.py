from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CALL_LAUNCH = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "callLaunch.js"
)
CALL_BUTTON = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "client"
    / "src"
    / "components"
    / "Viventium"
    / "CallButton.tsx"
)
CALL_ERROR = CALL_BUTTON.with_name("voiceCallError.ts")
_agent_starter_react_dir = Path(
    os.environ.get(
        "VIVENTIUM_AGENT_STARTER_REACT_DIR",
        ROOT / "viventium_v0_4" / "agent-starter-react",
    )
).expanduser()
AGENT_STARTER_REACT_ROOT = (
    _agent_starter_react_dir
    if _agent_starter_react_dir.is_absolute()
    else ROOT / _agent_starter_react_dir
).resolve()
TYPESCRIPT = (
    AGENT_STARTER_REACT_ROOT
    / "node_modules"
    / "typescript"
    / "lib"
    / "typescript.js"
)


def _run_node(template: str, replacements: dict[str, str]) -> dict[str, object]:
    script = textwrap.dedent(template)
    for marker, value in replacements.items():
        script = script.replace(marker, json.dumps(value))
    result = subprocess.run(
        ["node", "-"],
        input=script,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "Node harness produced no result"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _readiness_harness(fetch_body: str) -> dict[str, object]:
    return _run_node(
        f"""
        process.env.PLAYGROUND_VARIANT = 'modern';
        process.env.VIVENTIUM_PLAYGROUND_SOURCE_REF = 'a'.repeat(40);
        process.env.VIVENTIUM_PLAYGROUND_URL = 'http://127.0.0.1:3300';
        let cancelled = false;
        let textCalled = false;
        global.fetch = async () => {{
          {fetch_body}
        }};
        const {{ verifyPlaygroundReadiness }} = require(__CALL_LAUNCH__);
        verifyPlaygroundReadiness().then((result) => {{
          process.stdout.write(JSON.stringify({{ result, cancelled, textCalled }}));
        }}).catch((error) => {{
          process.stderr.write(String(error?.stack || error));
          process.exit(1);
        }});
        """,
        {"__CALL_LAUNCH__": str(CALL_LAUNCH)},
    )


def test_voice_readiness_rejects_oversized_content_length_before_reading_body() -> None:
    result = _readiness_harness(
        """
        return {
          ok: true,
          status: 200,
          headers: { get: (name) => name.toLowerCase() === 'content-length' ? '65537' : null },
          text: async () => { textCalled = true; throw new Error('body must not be read'); },
        };
        """
    )

    assert result == {
        "result": {"ready": False, "reason": "playground_identity_mismatch"},
        "cancelled": False,
        "textCalled": False,
    }


def test_voice_readiness_bounds_chunked_response_while_streaming() -> None:
    result = _readiness_harness(
        """
        const chunks = [Buffer.alloc(40000, 'a'), Buffer.alloc(30000, 'b')];
        let index = 0;
        return {
          ok: true,
          status: 200,
          headers: { get: () => null },
          body: {
            getReader: () => ({
              read: async () => index < chunks.length
                ? { done: false, value: chunks[index++] }
                : { done: true },
              cancel: async () => { cancelled = true; },
              releaseLock: () => {},
            }),
          },
          text: async () => { textCalled = true; throw new Error('unbounded text read'); },
        };
        """
    )

    assert result == {
        "result": {"ready": False, "reason": "playground_identity_mismatch"},
        "cancelled": True,
        "textCalled": False,
    }


def test_voice_readiness_accepts_exact_identity_from_a_bounded_stream() -> None:
    identity = json.dumps(
        {
            "schema_version": 1,
            "product": "viventium-playground",
            "status": "ok",
            "surface": "modern-playground",
            "variant": "modern",
            "source_ref": "a" * 40,
        }
    )
    result = _readiness_harness(
        f"""
        const encoded = Buffer.from({json.dumps(identity)});
        const chunks = [encoded.subarray(0, 19), encoded.subarray(19)];
        let index = 0;
        return {{
          ok: true,
          status: 200,
          headers: {{ get: () => null }},
          body: {{
            getReader: () => ({{
              read: async () => index < chunks.length
                ? {{ done: false, value: chunks[index++] }}
                : {{ done: true }},
              cancel: async () => {{ cancelled = true; }},
              releaseLock: () => {{}},
            }}),
          }},
          text: async () => {{ textCalled = true; throw new Error('unbounded text read'); }},
        }};
        """
    )

    assert result == {
        "result": {"ready": True},
        "cancelled": False,
        "textCalled": False,
    }


def test_call_failure_copy_is_structured_concise_and_does_not_echo_server_details() -> None:
    result = _run_node(
        """
        const fs = require('fs');
        const Module = require('module');
        const ts = require(__TYPESCRIPT__);
        const file = __CALL_ERROR__;
        const source = fs.readFileSync(file, 'utf8');
        const transpiled = ts.transpileModule(source, {
          compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
          },
          fileName: file,
        });
        const loaded = new Module(file, module);
        loaded.filename = file;
        loaded.paths = Module._nodeModulePaths(require('path').dirname(file));
        loaded._compile(transpiled.outputText, file);
        const { readVoiceCallFailureMessage } = loaded.exports;
        const cases = [
          [
            503,
            {
              error: 'voice_runtime_not_ready',
              reason: 'playground_identity_mismatch',
              message: 'private internal detail that must never be echoed',
            },
          ],
          [400, { error: 'voice_agent_required', message: 'raw implementation detail' }],
          [409, { error: 'voice_not_enabled', message: 'raw setup detail' }],
          [404, { error: 'conversation_missing', message: 'raw database detail' }],
          [500, { error: 'unknown_private_failure', message: 'raw stack detail' }],
        ];
        Promise.all(cases.map(async ([status, body]) => {
          const response = new Response(JSON.stringify(body), {
            status,
            headers: { 'Content-Type': 'application/json' },
          });
          return readVoiceCallFailureMessage(response);
        })).then((messages) => process.stdout.write(JSON.stringify({ messages })));
        """,
        {"__TYPESCRIPT__": str(TYPESCRIPT), "__CALL_ERROR__": str(CALL_ERROR)},
    )

    assert result == {
        "messages": [
            "Voice needs attention. Open Viventium from the menu bar, check Status, then try again.",
            "Choose an assistant before starting Voice.",
            "Voice is not enabled yet. Open Viventium from the menu bar to set it up.",
            "This conversation changed. Refresh the page, then try Voice again.",
            "Voice could not start. Try again. If it keeps happening, check Viventium Status.",
        ]
    }


def test_call_button_reports_recoverable_errors_inline_without_alerts() -> None:
    source = CALL_BUTTON.read_text()

    assert "readVoiceCallFailureMessage" in source
    assert 'role="alert"' in source
    assert "aria-describedby={error ? errorId : undefined}" in source
    assert "alert(" not in source


def test_call_button_typescript_syntax_transpiles() -> None:
    result = _run_node(
        """
        const fs = require('fs');
        const ts = require(__TYPESCRIPT__);
        const file = __CALL_BUTTON__;
        const transpiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
          compilerOptions: {
            module: ts.ModuleKind.ESNext,
            target: ts.ScriptTarget.ES2022,
            jsx: ts.JsxEmit.ReactJSX,
          },
          fileName: file,
          reportDiagnostics: true,
        });
        const diagnostics = (transpiled.diagnostics || []).map((item) =>
          ts.flattenDiagnosticMessageText(item.messageText, '\\n')
        );
        process.stdout.write(JSON.stringify({ diagnostics }));
        """,
        {"__TYPESCRIPT__": str(TYPESCRIPT), "__CALL_BUTTON__": str(CALL_BUTTON)},
    )

    assert result == {"diagnostics": []}


def test_call_launch_preserves_owned_existing_chat_through_bootstrap_without_a_turn() -> None:
    result = _run_node(
        """
        const fs = require('fs');
        const Module = require('module');
        const ts = require(__TYPESCRIPT__);
        function loadTs(file) {
          const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
            fileName: file,
          });
          const loaded = new Module(file, module);
          loaded.filename = file;
          loaded.paths = Module._nodeModulePaths(require('path').dirname(file));
          loaded._compile(result.outputText, file);
          return loaded.exports;
        }
        process.env.VIVENTIUM_PLAYGROUND_URL = 'https://voice.example.test/playground';
        const { buildCallLaunchResponse } = require(__CALL_LAUNCH__);
        const { CALL_CAPABILITY_BOOTSTRAP_SCRIPT } = loadTs(__BOOTSTRAP__);
        const { readCallDeepLink } = loadTs(__CALL_START__);
        const results = [];
        for (const conversationId of ['conversation-existing', 'new', '', '../foreign', 'x'.repeat(161)]) {
          const capability = 'B'.repeat(43);
          const launch = buildCallLaunchResponse({callSessionId:'call-current', conversationId, browserCapability:capability}, {includeConversationId:true});
          const target = new URL(launch.playgroundUrl);
          const stored = new Map();
          let destination;
          const window = {
            location: {search:target.search, hash:target.hash, pathname:target.pathname, replace:(value)=>{destination=value;}},
            history: {state:null,replaceState:()=>{}},
            sessionStorage: {setItem:(key,value)=>stored.set(key,value)},
          };
          new Function('window','document',CALL_CAPABILITY_BOOTSTRAP_SCRIPT)(window,{referrer:'https://chat.example.test/c/conversation-existing'});
          const deepLink = readCallDeepLink(new URL(destination,target.origin).search);
          results.push({
            concreteChat:deepLink.expectedConversationId,
            exactCall:deepLink.expectedCallSessionId,
            autoConnect:deepLink.autoConnect,
            retainedOpener:stored.get('viventium.call.opener-origin.v1:call-current'),
            capabilityStored:stored.get('viventium.call.capability.v1:call-current')===capability,
            capabilityOutsideFragment:target.search.includes(capability)||destination.includes(capability),
          });
        }
        process.stdout.write(JSON.stringify({results}));
        """,
        {
            "__TYPESCRIPT__": str(TYPESCRIPT),
            "__CALL_LAUNCH__": str(CALL_LAUNCH),
            "__BOOTSTRAP__": str(AGENT_STARTER_REACT_ROOT / "lib" / "call-capability-bootstrap.ts"),
            "__CALL_START__": str(AGENT_STARTER_REACT_ROOT / "lib" / "call-start.ts"),
        },
    )
    assert [row["concreteChat"] for row in result["results"]] == [
        "conversation-existing", None, None, None, None
    ]
    for row in result["results"]:
        assert row == {
            "concreteChat": row["concreteChat"],
            "exactCall": "call-current",
            "autoConnect": True,
            "retainedOpener": "https://chat.example.test",
            "capabilityStored": True,
            "capabilityOutsideFragment": False,
        }
