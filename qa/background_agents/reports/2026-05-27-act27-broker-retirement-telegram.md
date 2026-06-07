<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# ACT-27 Broker-First Retirement Telegram QA
- Started: 2026-05-27T07:27:04.941Z
- Scope: local Telegram bridge route with existing linked account mapping; public-safe hashes only.
- API hash: `49e73564e9d328ef`
- QA user hash: `4cec47b586b8232b`
- Telegram mapping hash: `2f392d3c670f6812`
- Prompt hash: `08532e93aec1abac`
- Conversation hash: `39af37dfa85aa7f4`
- Chat HTTP status: 200
- Stream HTTP status: 200
- Stream event count: 159
- Stream terminal event seen: true
- Assistant message count: 1
- Answer text length: 2132
- Forbidden retired stored cortex names: none
- Stored cortex names: Confirmation Bias
- Background-cortex promise present: false
- GlassHive/direct-tool evidence present: true
- Limitation wording present in promoted Telegram reply: false
- Supporting DB detail: the canonical parent turn for the same conversation included a structured `workspace_launch_mcp_glasshive-workers-projects` tool call and no background-cortex promise.
- Evidence scope: primary visible Telegram acceptance is the absence of retired background-agent output or background-cortex promises; the GlassHive handoff proof is structured DB evidence from the same conversation.
- Result: PASS for ACT-27 local soft-retirement; this does not prove full GlassHive broker parity/removal readiness.
