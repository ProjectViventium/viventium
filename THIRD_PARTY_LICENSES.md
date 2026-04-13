# Third-Party Licenses

The main `viventium` repo coordinates multiple separately licensed component
repos. Those components are not relicensed by the root `LICENSE`.

| Component repo | Upstream | License |
|---|---|---|
| `viventium-librechat` | [LibreChat](https://github.com/danny-avila/LibreChat) | MIT |
| `viventium-openclaw` | [OpenClaw](https://github.com/openclaw/openclaw) | MIT |
| `skyvern-source` | [Skyvern](https://github.com/Skyvern-AI/skyvern) | AGPL-3.0 |
| `google_workspace_mcp` | [google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) | MIT |
| `ms-365-mcp-server` | [ms-365-mcp-server](https://github.com/softeria/ms-365-mcp-server) | MIT |
| `mcp-youtube-transcript` | [mcp-youtube-transcript](https://github.com/jkawamoto/mcp-youtube-transcript) | MIT |
| `agents-playground` | [agents-playground](https://github.com/livekit/agents-playground) | Apache-2.0 |
| `livekit` | [livekit](https://github.com/livekit/livekit) | Apache-2.0 |
| `cartesia-voice-agent` | [cartesia-voice-agent](https://github.com/livekit-examples/cartesia-voice-agent) | Apache-2.0 |
| `agent-starter-react` | [agent-starter-react](https://github.com/livekit-examples/agent-starter-react) | MIT |

## Boundary

The public product repo publishes:

- the installer and CLI,
- product-facing orchestration scripts,
- config compilation and health checks,
- Viventium-owned public docs,
- compatibility glue for the public component repos.

Users who need the full product follow the main repo and allow the installer to
fetch the pinned component repos listed in `components.lock.json`.
