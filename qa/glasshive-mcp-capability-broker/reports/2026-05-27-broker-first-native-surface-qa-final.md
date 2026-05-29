# Native-Surface Playwright QA

Generated: 2026-05-27T15:37:10.192Z

## Status

- Status: completed_with_failures_or_gaps
- Browser Chrome QA account probe: fail
- Prompt-bank cases exercised: 2
- Post-case observation window: 60000 ms
- Async follow-up grace after cortex completion: 45000 ms
- Native/API completed: 0
- Native/API failed: 2
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
- Body had Viventium shell: no
- Console errors: 6
- Failed requests: 0
- Private screenshot: [local_path]

## MCP Status

- MCP status endpoint: fail (500)

| Server | State | OAuth | Error |
| --- | --- | --- | --- |
| none | n/a | n/a | n/a |

## Case Matrix

| Case | Surface | Native route | Route status | Semantic verdict | Score | Delayed msgs | Cortex insights | Frames | Frame surfaces | Error |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| generic_inbox_read_only_best_judgment | web | agents_api | failed | not_run |  | 0 | 0 | 0 |  | agents_start_http_0 |
| ambiguous_important_action_asks | web | agents_api | failed | not_run |  | 0 | 0 | 0 |  | agents_start_http_0 |

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

