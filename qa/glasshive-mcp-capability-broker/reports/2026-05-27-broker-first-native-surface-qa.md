<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Native-Surface Playwright QA

Generated: 2026-05-27T15:19:48.059Z

## Status

- Status: completed_native_surface_evidence_without_semantic_judge
- Browser Chrome QA account probe: pass
- Prompt-bank cases exercised: 2
- Post-case observation window: 60000 ms
- Async follow-up grace after cortex completion: 45000 ms
- Native/API completed: 2
- Native/API failed: 0
- Semantic judge cases: 0
- Semantic pass: 0
- Semantic partial: 0
- Semantic fail or judge parse fail: 0
- Duplicate response quality failures: 0
- Unresolved async quality failures: 0
- Routes exercised: agents_api
- Prompt surfaces requested: web
- Prompt-frame surfaces observed: none

## Browser Evidence

- Local Chrome route: local-browser-route (1907c09a5927)
- QA identity hash matched: yes
- Refresh status: 200
- User endpoint status: 200
- Body had Viventium shell: yes
- Console errors: 0
- Failed requests: 0
- Private screenshot: [local_path]

## MCP Status

- MCP status endpoint: pass (200)

| Server | State | OAuth | Error |
| --- | --- | --- | --- |
| ms-365 | connected | yes | no |
| google_workspace | disconnected | yes | no |
| scheduling-cortex | connected | no | no |
| glasshive-workers-projects | disconnected | no | no |
| sequential-thinking | connected | no | no |

## Case Matrix

| Case | Surface | Native route | Route status | Semantic verdict | Score | Delayed msgs | Cortex insights | Frames | Frame surfaces | Error |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| generic_inbox_read_only_best_judgment | web | agents_api | completed | not_run |  | 0 | 0 | 0 |  |  |
| ambiguous_important_action_asks | web | agents_api | completed | not_run |  | 0 | 0 | 0 |  |  |

## Quality Gate Failures

- Duplicate non-silent response groups: none
- Unresolved async holds: none

## Evidence Policy

- Private raw JSON: [local_path]
- Public report stores statuses, hashes, counts, route names, sanitized errors, and frame summaries only.
- Full prompts, raw responses, frame payloads, screenshot pixels, cookies, tokens, user ids, and gateway secrets remain private.

## Known Limits

- Voice is exercised through the local voice gateway HTTP/SSE route with a fake browser STT/TTS selection, not a real microphone/audio device.
- Wing mode is exercised through the agent surface metadata path; LiveKit ambient interruption policy remains a separate audio-session QA gate.
- Semantic partial verdicts fail this gate unless a future runner adds an explicit reviewed-partial override.
- The semantic judge is a live local model-route judge through the same Viventium stack, not a deterministic unit-test oracle or provider-enforced JSON Schema route.
