# Telegram Smart Delivery Controls QA Run - 2026-07-22

## Summary

- Result: **PASS for the active local Telegram main-turn experience; PARTIAL for proactive real-surface and future-channel parity**
- Build/source under test: current public source checkout plus the active nested LibreChat checkout
- Runtime/artifact under test: installed local-prod runtime activated from the current checkout
- Environment: local macOS product runtime with Telegram Desktop, Prompt Workbench, LibreChat API/UI, and the configured TTS route running
- Tester: Codex automation plus Computer Use and Playwright CLI
- Related change: model-authored `{SKIP_VOICE}` and `{MSG_BREAK}` delivery controls

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TGVOICE-006` | PASS/PARTIAL | Real Telegram Desktop delivery, sanitized voice-decision logs, clean persistence, 345 Telegram tests, prompt bundle with zero drift | Main-turn skip/conversation/explicit-speech behavior passed. Proactive behavior passed automation but was not triggered through a real schedule/callback. |
| `TGVOICE-007` | PASS/PARTIAL | Real two-bubble Telegram delivery, one final audio attachment, one clean stored assistant turn, grammar/persistence tests | Main-turn natural split passed. No Slack or WhatsApp adapter exists to exercise runtime parity. |
| `TGVOICE-UC-007` | PASS | Three synthetic real-user turns in Telegram Desktop | Copy-ready email stayed text-only; ordinary conversation and explicit read-aloud each received one audio attachment. |
| `TGVOICE-UC-008` | PASS/PARTIAL | Two clean visible bubbles, one final audio attachment, reopened Telegram history, one clean DB turn | Conversational split passed. Copy-ready artifact remained one intact bubble in the email case. Proactive split remains automation-only. |

## Natural User Use Case Checklist Run

| Use case | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Read-first artifact | Ask for a polished, copy-ready synthetic email while text audio is enabled | Telegram Desktop through Computer Use | PASS | Full email arrived as one clean text message with no audio or raw control, both before and after the final runtime restart | Initial gate avoided 161 TTS characters; the post-restart gate recorded requested/effective model skip and avoided 117 characters, with no TTS-start event; one clean assistant turn persisted | None for the main turn |
| Ordinary conversation | Ask for a warm conversational explanation with the same preference enabled | Telegram Desktop through Computer Use | PASS | Clean text plus exactly one delivered 24-second audio attachment | One send decision, one TTS start, one audio-send event | Audio delivery was verified; playback was not manually started |
| Natural two-beat reply | Ask for two complete conversational beats | Telegram Desktop through Computer Use | PASS | Exactly two complete answer bubbles followed by one 13-second audio attachment; no control text appeared | Log recorded one semantic break, two segments, no merge; DB retained one assistant turn containing both beats and no controls | None for the main turn |
| Explicit spoken override | Explicitly ask for a short reminder to be read aloud | Telegram Desktop through Computer Use | PASS | Clean text plus exactly one delivered 2-second audio attachment | Gate sent audio; one TTS start and one audio-send event | None |
| Reopen/persistence | Reopen the bot chat after the split delivery | Telegram Desktop through Computer Use | PASS | The same two clean bubbles and single audio attachment remained visible | Correlated persistence remained one clean logical assistant turn | None |
| Prompt inspection | Inspect the new prompt layers and eval family, then run a no-live preview | Prompt Workbench through Computer Use and Playwright CLI | PASS | Workbench visibly listed Messaging Optional Audio, Messaging Bubble Boundaries, and Telegram Smart Delivery with five cases; the preview completed with code 0 | Active bundle contained 76 prompts with exact source/runtime hash match and zero prompt drift | The existing unrelated live-agent merge state was intentionally not pushed or changed |
| Preference wording | Open the Telegram information card and inspect the Preferences entrypoint | Telegram Desktop through Computer Use | PARTIAL | Preferences entrypoint was visible | Source and regression test verify the label `Smart voice for text` | Telegram's custom UI did not expose the inline button to accessibility automation, so the nested Preferences screen was not opened during this run |
| Proactive callback | Deliver a scheduled/background answer containing either control | Automated callback harness only | PARTIAL | Not exercised through a real scheduled Telegram delivery | Callback tests prove clean split/skip behavior and audio only on the final callback | Run a synthetic scheduled callback on the real Telegram surface before a release-wide claim |
| Future channels | Exercise identical behavior on Slack and WhatsApp | Product inventory/status inspection | BLOCKED | No applicable product surface exists | Shared contract is adapter-neutral; product status reports no first-class WhatsApp integration, and no Slack adapter exists in this repo | Implement an adapter consumer before claiming runtime parity |
| Missing/degraded TTS | Force the optional TTS provider to fail after a non-skip answer | Existing broader voice regression suite only | PARTIAL | Not deliberately broken in the real user run | Existing Telegram fallback tests stayed green; skip path avoids invoking TTS entirely | A real provider-outage run is outside this surgical feature acceptance |
| Public/shipped artifact | Verify a release-pinned nested commit and published artifact | Source/runtime inspection | PARTIAL | Active local runtime used the changed checkout successfully | Nested repo and parent pin were already dirty/drifted; no release commit, pin, or public artifact was created | Required before calling this publicly shipped or release-ready |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Smart messaging delivery controls
- Requirement: [Telegram Bridge — Smart Messaging Delivery Controls](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md)
- Use cases: read-first artifact, ordinary conversation, explicit read-aloud, natural two-beat reply, reopen/history
- QA cases: `TGVOICE-006`, `TGVOICE-007`, `TGVOICE-UC-007`, `TGVOICE-UC-008`
- Expected result: the Main Agent makes the semantic decision; adapters structurally consume bounded controls; users see complete clean text, useful audio only, natural bubble boundaries, and one clean logical history turn
- Actual evidence: all four real Telegram main-turn scenarios matched the contract; a final post-restart email turn reconfirmed the loaded runtime skip path; logs and persistence agreed with the visible result
- Remaining gap: real proactive delivery and future channel adapters were not available for full user-surface parity; no release pin/artifact was produced

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Owning behavior is documented in the Telegram Bridge requirement and cases `TGVOICE-006/007`. |
| Code owning path | Main Agent prompt overlays -> LibreChat request/persistence sanitizer -> shared delivery grammar -> Telegram direct/proactive transport -> TTS gate. |
| Docs and nested docs/repos | Parent Telegram/prompt-architecture docs and nested expected-behavior/prompt sources were inspected and updated. |
| Scripts or harnesses | Telegram, LibreChat, release-contract, Prompt Workbench, prompt compiler, Computer Use, and Playwright CLI paths were exercised. |
| Local/external prerequisite state | Telegram bridge, LibreChat API/UI, Prompt Workbench, and the selected TTS route were proven operational by real requests. An unrelated memory-hardening status remained unhealthy. |
| Logs | Sanitized gate/TTS/audio counts matched all four visible outcomes; the skipped artifact had no TTS start. |
| DB/state/persistence | Synthetic turns persisted without delivery controls; the split answer remained one assistant turn containing both beats. |
| Generated/shipped artifact | Prompt source and active runtime registry matched exactly at 76 prompts. The active local runtime ran the changed checkout. No release pin or published artifact was created. |
| Real user path | Telegram Desktop was used for all four main-turn scenarios; Prompt Workbench was inspected in a real browser. |
| Visual/UX comparison | No control leaked. The email remained copyable text, conversational audio stayed available, the split was bounded and complete, and explicit speech overrode skipping. |
| Not run / blocked | Real proactive callback, Slack/WhatsApp runtime parity, nested Preferences detail, deliberate provider outage, and public release artifact verification. |

## User-Grade Evidence

- Surface exercised: Telegram Desktop bot chat and Prompt Workbench in Chrome
- Real user path: send synthetic prompts, observe text/bubble/audio delivery, reopen chat, inspect Workbench prompt/eval inventory, and run a Workbench preview
- Visible outcome: expected clean text, zero or one audio attachment as appropriate, and exactly two bubbles for the semantic split
- Expanded/detail state: Workbench graph exposed both new prompt layers and the linked five-case eval family; Telegram information card exposed the Preferences entrypoint
- Persistence/reload result: reopened Telegram history stayed clean; DB correlation remained one logical assistant turn per request
- Local/external prerequisite state: active local-prod runtime and Telegram/TTS path were running; unrelated runtime warnings were not treated as feature failures
- Backend/log/DB confirmation: voice decision, segment count, TTS count, audio-send count, and clean persistence agreed with the visible UI
- Final model/runtime wording check: the model used controls without mentioning them; runtime removed them before display and persistence
- Substitution check: logs/DB/tests support but do not replace the completed Telegram Desktop and browser paths
- Evidence handling: screenshots were inspected live but intentionally not saved because the existing chat/browser surfaces contained unrelated private content

## Automated Evidence

```bash
uv run --project TelegramVivBot --with pytest python -m pytest -q
# 346 passed

npx jest --config jest.config.js \
  server/services/viventium/__tests__/deliveryControls.spec.js \
  server/services/viventium/__tests__/surfacePrompts.spec.js \
  server/controllers/agents/__tests__/requestPersistence.spec.js \
  server/routes/viventium/__tests__/telegram.spec.js --runInBand
# 131 passed

uv run --with pytest --with pyyaml python -m pytest -q \
  tests/release/test_delivery_controls_contract.py \
  tests/release/test_no_runtime_nlu.py \
  tests/release/test_prompt_registry.py
# 33 passed

uv run --with pytest --with pyyaml python -m pytest -q \
  tests/release/test_qa_operating_contract.py \
  tests/release/test_qa_results_public_safety.py
# 24 passed

npx jest --config jest.config.js \
  server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js \
  --runInBand -t 'teaches smart optional audio'
# 1 passed, 58 unrelated tests skipped by the selector
```

Additional focused Prompt Workbench/release checks produced 136 passes and 22 environment skips after the only missing-dependency case was rerun with its dependency and passed. JavaScript syntax checks, Python compilation, prompt compilation/drift inspection, and diff whitespace checks also passed.

The proactive/background follow-up prompt regression test passed independently. Its broader owning
suite currently has four unrelated pre-existing Feelings expectation failures in the dirty nested
checkout; the new proactive smart-audio test itself passes, and those unrelated assertions were not
rewritten as part of this feature.

## Outcome Metric

- Quality — intelligence/relevance/usefulness/alignment: PASS. The Main Agent retained the semantic decision, explicit spoken intent won, copy-ready material stayed intact, and the split answer remained coherent.
- Performance — fast/smooth/reliable: PASS for exercised paths. The email avoided an unnecessary synthesis call, normal replies retained one audio call, and the split added no duplicate synthesis.
- Parity: PASS at the shared contract and Telegram direct/proactive implementation layers; PARTIAL at real product surfaces because other messaging adapters do not yet exist.

## Findings

- Defects: independent review found that proactive Telegram callbacks honored `{SKIP_VOICE}` at
  delivery but were not taught the optional-audio prompt. The follow-up prompt now uses the original
  structured `telegramAudioRequested` and `voiceProvider` request metadata to include the same rules,
  with no content inference; its targeted regression test passes.
- Regressions: none in the relevant automated suites.
- Flakes: none observed.
- Environment issues: a first dependency-free test invocation could not collect the Telegram suite; rerunning through its declared project environment passed all 345 tests. The active runtime also reported unrelated memory-hardening and account-setup warnings despite the live configured Telegram/model path succeeding.
- Residual risks: proactive behavior is automation-only; attachments combined with semantic splits
  were not exercised and currently place an attachment between the first and later semantic bubbles;
  split-tail transport failure is not retried/collapsed; release pin/artifact state remains outside
  this local-working claim.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
