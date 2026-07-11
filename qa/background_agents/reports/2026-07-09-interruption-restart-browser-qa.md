# Background Cortex Interruption/Restart Browser QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

- Started: 2026-07-10T04:24:22.479Z
- Scope: local synthetic QA account, real browser, Mongo persistence, supported runtime stop/start, normal stale-cortex recovery.
- QA user: dedicated local synthetic QA account (identifier intentionally omitted)
- Prompt hash: `51a20dea4ee88f2e`
- Conversation hash: `254684442d347a8a`
- Parent message hash: `ee59ba10030b48d7`
- Expected cortex: Red Team
- Active card visible before restart: true
- Active cortex persisted before restart: true
- Runtime API process changed: true
- Cortex card visible immediately after restart: true
- Persisted active state survived restart: true
- Recovered terminal cortex persisted: true
- Recovered terminal cortex visible after reload: true
- Expanded recovered detail visible: true
- Parent unfinished after recovery: false
- Misleading generation placeholder visible after recovery: false
- Post-restart console errors: 3
- Unexpected post-restart console errors: 0
- Post-restart failed requests: 0
- Unexpected post-restart failed requests: 0
- Post-restart HTTP errors: 2
- Unexpected post-restart HTTP errors: 0
- Expected diagnostic exclusions: local-QA pre-token 401 bootstrap and browser navigation abort only.
- Result: PASS
