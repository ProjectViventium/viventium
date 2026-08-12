# Live browser saved-memory model-route QA — 2026-08-08

- Status: PASS
- Signed-in surface: local LibreChat, non-admin QA account
- Writer route: openai / gpt-5.6-luna
- Conversation recall during both turns: disabled
- Synthetic fact written through browser chat: yes
- Stored fact visible in Memories panel: yes
- Fresh conversation recovered both requested fields: yes
- Reload preserved the visible answer: yes
- DB/message/receipt evidence agreed: yes
- Revision-safe memory cleanup verified: yes
- LibreChat and GlassHive synthetic conversation/session cleanup verified: yes
- Original account preferences restored: yes
- Account hash: f9ffb8f8a012
- Write conversation hash: cb053628a9df
- Read conversation hash: e1f49091b1b4
- Private screenshot/result artifacts: saved outside repository

The test used a unique synthetic preference, never repeated that preference in the recovery prompt, and disabled conversation recall before both turns. This proves the general saved-memory write/read path rather than transcript recall or knowledge of a particular person/entity.

Raw prompts, responses, memory values, account identifiers, screenshots, tokens, local paths, and database identifiers are intentionally excluded from this public report.
