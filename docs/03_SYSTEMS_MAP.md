# Systems Map

## v0.4 (Active Stack)

Location: `viventium_v0_4/`

Entrypoints:
- Full stack: `viventium_v0_4/viventium-librechat-start.sh`
- LibreChat only: `viventium_v0_4/LibreChat/scripts/viventium-start.sh`

Key directories:
- `viventium_v0_4/LibreChat/` (Node API + client + packages)
- `viventium_v0_4/voice-gateway/` (Python voice worker)
- `viventium_v0_4/telegram-viventium/` (Telegram bridge)
- `viventium_v0_4/agents-playground/` (legacy playground)
- `viventium_v0_4/agent-starter-react/` (modern playground)
- `viventium_v0_4/livekit/` (LiveKit server repo)

Nested git repos inside v0.4:
- `viventium_v0_4/LibreChat/`
- `viventium_v0_4/agents-playground/`
- `viventium_v0_4/agent-starter-react/`
- `viventium_v0_4/cartesia-voice-agent/`
- `viventium_v0_4/livekit/`
- `viventium_v0_4/MCPs/ms-365-mcp-server/`
- `viventium_v0_4/MCPs/google_workspace_mcp/`
- `viventium_v0_4/MCPs/yt_transcript/`
- `viventium_v0_4/openclaw/`
- `viventium_v0_4/skyvern-source/`

## v0.3 (Legacy Stack)

Location: `viventium_v0_3_py/`

Entrypoints:
- Full stack: `viventium_v0_3_py/start_all.sh`
- Root wrapper: `start_all.sh`

Key directories:
- `viventium_v0_3_py/viventium_v1/` (Python cortex system)
- `viventium_v0_3_py/interfaces/` (legacy Telegram, playgrounds, MCP servers)
- `viventium_v0_3_py/scripts/` (legacy scripts)
- `viventium_v0_3_py/docker/` (legacy docker stacks)
- `viventium_v0_3_py/mcps/` (MS365 MCP server + configs)

## Shared Resources

- `.env` / `.env.local`: shared secrets and overrides
- `.viventium/`: runtime logs and artifacts
- `docs/requirements_and_learnings/`: single source of truth per feature
