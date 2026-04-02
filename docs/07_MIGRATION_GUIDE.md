# Migration Guide (v0.3 -> v0.4)

This is a high-level migration map. The goal is parity without breaking production workflows.

## What Changes

| Area | v0.3 (Python) | v0.4 (LibreChat) |
| --- | --- | --- |
| Agent runtime | LiveKit agent in Python | LibreChat agent pipeline + background agents |
| Background logic | Cortices + SubconsciousRuntime | BackgroundCortexService + follow-ups |
| Insight surface | ResponseController | Follow-up assistant message |
| Voice | LiveKit agent directly | Voice Gateway worker |
| Memory | Markdown + vectors | LibreChat DB + metadata |

## Recommended Migration Steps

1. Keep v0.3 running in parallel until v0.4 parity is confirmed.
2. Rebuild core cortices as background agents (activation + prompt + cooldown).
3. Map critical tools (web search, MCPs) to LibreChat tool configs.
4. Align voice behavior: barge-in, low latency, allowed nonverbal markers.
5. Replace v0.3 memory lookups with LibreChat memory workflows.
6. Validate Telegram bridge behavior (v0.4 uses its own bridge).

## Parity Checklist

- [ ] Voice calls connect reliably and support barge-in
- [ ] Background agent updates do not block main response
- [ ] MS365 + Google MCPs reachable with correct auth
- [ ] Follow-up messages generated correctly
- [ ] Logs and monitoring equivalent to v0.3

## References

- v0.4 docs: `viventium_v0_4/docs/`
- v0.3 docs: `viventium_v0_3_py/docs/`
