# OpenClaw Bridge MCP Server

Bridges Viventium agents to OpenClaw running in VM-scoped runtimes.
Each `(user_id, vm_id)` maps to an isolated runtime instance.

## POC Scope (E2B VM Control)

This bridge now supports Codex-chat-first VM control for:

- `start`, `resume`, `stop (pause)`, `terminate`
- `list`, `status`, `takeover`
- per-VM execution routing with `vm_id` on core tools (`openclaw_exec`, `openclaw_browser`, `openclaw_agent`)

## Architecture

```
LibreChat/Codex ──MCP──▶ openclaw-bridge (FastMCP)
                          ├─ VM lifecycle tools (openclaw_vm_*)
                          ├─ Execution tools (openclaw_exec/browser/agent/...)
                          └─ Runtime manager (user_id + vm_id)
                               ├─ E2B adapter (default)
                               │    ├─ Sandbox create/connect/pause/kill/list
                               │    ├─ Desktop takeover stream URL/auth
                               │    └─ Metrics collection
                               └─ Direct runtime adapter (compat fallback)
```

## No-Reinvention Policy (E2B Native Features Reused)

This implementation intentionally uses E2B primitives instead of custom equivalents:

- lifecycle: `create/connect/beta_pause/kill/list`
- sandbox metadata tags for `(viventium_user, viventium_vm_id)`
- port host mapping via `get_host(...)`
- interactive takeover via `e2b-desktop` stream APIs
- runtime metrics via E2B metrics API

References:
- [E2B Docs](https://e2b.dev/docs)
- [E2B SDK / Sandbox API](https://e2b.dev/docs/sdk-reference)
- [E2B OSS](https://github.com/e2b-dev/E2B)
- [E2B Desktop OSS](https://github.com/e2b-dev/desktop)
- [E2B MCP server tools package](https://www.npmjs.com/package/@e2b/mcp-server)

## Runtime Modes

- `OPENCLAW_RUNTIME=e2b` (default for this POC)
- `OPENCLAW_RUNTIME=direct` (local OpenClaw process fallback)

If E2B dependencies are unavailable and `OPENCLAW_RUNTIME_ALLOW_FALLBACK=true`, manager falls back to `direct`.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 22+
- OpenClaw installed globally: `npm install -g openclaw`
- E2B key for VM mode: `E2B_API_KEY`
- LLM provider key used by OpenClaw (for agent tasks)

### Install

```bash
cd viventium_v0_4/MCPs/openclaw-bridge
pip install -r requirements.txt
```

### Run (native)

```bash
export OPENCLAW_RUNTIME=e2b
export E2B_API_KEY="..."
export ANTHROPIC_API_KEY="..."
python mcp_server.py
```

### Run (script)

```bash
cd viventium_v0_4
bash viventium-openclaw-bridge-start.sh start
```

## MCP Tools

### VM Lifecycle

- `openclaw_vm_start(vm_id="001")`
- `openclaw_vm_resume(vm_id="001")`
- `openclaw_vm_stop(vm_id="001")`
- `openclaw_vm_terminate(vm_id="001")`
- `openclaw_vm_list()`
- `openclaw_vm_status(vm_id="001")`
- `openclaw_vm_takeover(vm_id="001", require_auth=true, view_only=false)`

### Execution Surface

- `openclaw_exec(command, working_dir="", vm_id="001")`
- `openclaw_browser(action, url="", selector="", text="", vm_id="001")`
- `openclaw_agent(task, model="", tools="", vm_id="001")`
- `openclaw_status(vm_id="001")` (alias of VM status)

Other OpenClaw tools (`message`, `cron`, `nodes`, `canvas`, `web_search`, `web_fetch`) also accept `vm_id`.

## Codex-First CLI

Use `vm_control.py` for direct VM management from terminal/Codex:

```bash
cd viventium_v0_4/MCPs/openclaw-bridge

python vm_control.py start --user demo --vm 001
python vm_control.py start --user demo --vm 002
python vm_control.py list --user demo
python vm_control.py stop --user demo --vm 001
python vm_control.py resume --user demo --vm 001
python vm_control.py takeover --user demo --vm 001
python vm_control.py terminate --user demo --vm 002
```

## Benchmarks / Artifacts

Run the POC benchmark script:

```bash
cd viventium_v0_4/MCPs/openclaw-bridge
python benchmarks/e2b_vm_poc.py --user demo --vm 001 --second-vm 002
```

Artifacts are written to:

- `.viventium/artifacts/openclaw-e2b-poc/<timestamp>/benchmark.json`
- `.viventium/artifacts/openclaw-e2b-poc/<timestamp>/benchmark.md`
- `.viventium/artifacts/openclaw-e2b-poc/<timestamp>/dependencies_licenses.json`

Recorded fields include cold start, pause/resume timing, first tool invoke latency,
agent task latency, metrics snapshot, and dependency version/license metadata.

## LLM-Usable VM MCP Acceptance Extension

Success requires that an LLM (Codex/Claude/etc.) can control VMs purely via MCP tools:

1. Start two VMs for the same user by `vm_id`.
2. Execute tasks against a chosen VM using `vm_id` in execution tools.
3. Pause/resume/terminate specific VMs independently.
4. Request takeover URL/auth for a specific VM.
5. Confirm VM isolation via distinct sandbox IDs.

## Security

- Default bind: `127.0.0.1`
- Bridge secret for header trust boundary: `OPENCLAW_BRIDGE_SECRET`
- Gateway auth: per-VM token auth (`Authorization: Bearer <token>`)

## Testing

```bash
# Unit tests
python -m pytest tests/ -v --ignore=tests/test_e2e*.py

# Integration tests (requires running bridge + configured env)
python -m pytest tests/ -v -m integration
```
