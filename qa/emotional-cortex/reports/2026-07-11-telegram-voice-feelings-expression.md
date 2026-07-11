# Telegram Feeling-Aware Voice Expression QA Run - 2026-07-11

## Summary

- Result: **PASS for Telegram text input + always-voice xAI; PARTIAL for all spoken surfaces**
- Build/source under test: current local public source working tree and nested LibreChat working tree
- Runtime/artifact under test: active local Viventium API and Telegram bot launched from that source;
  loopback Prompt Workbench source and saved eval run
- Environment: local macOS development runtime, Telegram Desktop, configured QA account, saved xAI
  TTS route
- Tester: Codex through the real Telegram and Prompt Workbench user paths
- Related change: capability-driven Feelings expression for voice-supported channels, registered
  Telegram provider prompts, provider-control telemetry, and happy/unhappy exact-model evals

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `EMO-036` | PASS | pre/post raw hashes and marker counts; real Telegram delivery | expressive capable route used one fitting control without an explicit request |
| `TGVOICE-004` | PASS/PARTIAL | real always-voice text turn plus automated text/voice-note payload coverage | post-change voice-note input/STT path was not rerun |
| `TGVOICE-005` | PASS | prompt frame, raw stored message, clean bubble, audio delivery, xAI telemetry | Telegram remained text mode with audio output |
| `PW-036` | PASS | Workbench run `20260711T162254Z`, code `0`, four model and four judge passes | exact state restoration and conversation cleanup passed |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `EMO-UC-026` | Send a natural message on an always-voice route without asking for emotional delivery | Telegram Desktop + xAI TTS | PASS | clean reply bubble and delivered 10-second voice note | one valid raw xAI wrapper; synthesis/delivery telemetry | none for this route |
| `TGVOICE-UC-005` | Confirm Telegram text mode still delivers audio | Telegram Desktop + Telegram bridge | PARTIAL | text plus voice note delivered | `voiceMode=false`, audio gate true; automated voice-note-input coverage | real post-change voice-note input not rerun |
| `TGVOICE-UC-006` | Make an expressive relational bid without naming voice, emotion, or markup | Telegram Desktop + xAI TTS | PASS | natural answer and voice note | raw marker count `1`; visible count `0`; TTS count `1` | none for xAI always-voice text |
| `PW-UC-012` | Inspect and run expressive, restrained, Feelings-off, and plain-TTS cases | Prompt Workbench Evals UI | PASS | selected prompt, four Telegram cases, successful run visible after reload | deterministic `1/0/0/0`; judges `4/4`; state restored; synthetic chats cleaned | none for these four cases |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Feelings-aware spoken expression on voice-capable Telegram replies
- Requirement: `01_Key_Principles.md` capability parity, `03_Telegram_Bridge.md` text-mode audio
  contract, and `54_Emotional_Cortex_And_Feeling_State.md` spoken expression contract
- Use case: a natural expressive Telegram turn should sound affected by the current Feelings state
  without requiring the user to ask for emotion or provider markup
- QA case: `EMO-036`, `TGVOICE-004`, `TGVOICE-005`, and `PW-036`
- Expected result: the model appraises expressive versus restrained delivery; an expressive xAI
  reply uses the smallest fitting documented control, restrained/Feelings-off xAI and plain TTS stay unmarked,
  display stays clean, and audio delivers
- Actual evidence: real Telegram result with one valid raw xAI control and delivered audio;
  Workbench happy/unhappy/boundary matrix passed `4/4`; focused automated suites passed
- Remaining gap or fix: LiveKit call audio, real Telegram voice-note input, other real TTS providers,
  clean-machine install, and full-release acceptance remain outside this pass

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `01_Key_Principles.md`, `03_Telegram_Bridge.md`, `54_Emotional_Cortex_And_Feeling_State.md`; `EMO-036`, `TGVOICE-005`, `PW-036` |
| Code owning path | Which code path owns the behavior? | LibreChat surface-prompt composition -> Telegram bridge -> raw assistant persistence -> Telegram display sanitizer/xAI TTS -> delivery telemetry |
| Docs and nested docs/repos | Which docs define expected behavior? | root requirements plus nested architecture/implementation indexes and registered prompt sources |
| Scripts or harnesses | Which suites exercised it? | exact-model runner, Prompt Workbench, LibreChat surface Jest, Telegram TTS/bridge pytest |
| Local/external prerequisite state | Which dependency was proven? | local API healthy; Telegram bot running from current source; saved xAI route synthesized and delivered audio |
| Logs | Which sanitized logs confirm the result? | audio gate true; xAI marker `0/1/1`; one chunk; synthesis and delivery timings recorded |
| DB/state/persistence | Which state confirms it? | three pre-fix raw hashes/counts and one post-fix raw hash/count; exact Feelings restoration; eval-conversation cleanup |
| Generated/shipped artifact | Which artifact was inspected? | executable registered-prompt/inline-fallback parity and source/live agent bundle comparison; clean-machine shipped artifact not claimed |
| Real user path | Which path was used like a user? | Telegram Desktop natural text turn and real voice-note delivery; headed Prompt Workbench preview/live result/reload |
| Visual/UX comparison | Does visible output match supporting evidence? | Telegram bubble showed no provider tags while raw/TTS evidence showed one; Workbench visibly showed the successful four-case run |
| Not run / blocked | Which surface was not run? | LiveKit audio, real voice-note input, real Cartesia/Chatterbox/plain delivery, clean-machine install; broader spoken parity remains PARTIAL |

## User-Grade Evidence

- Surface exercised: Telegram Desktop always-voice text route with xAI TTS; headed Prompt Workbench
- Real user path: sent a synthetic relational message with no request for voice, emotion, markup, or
  controls; inspected the clean text reply and delivered voice note; then searched, selected,
  filtered, previewed, ran, and reloaded the linked Workbench eval surface
- Visible outcome: same spoken words in a clean Telegram bubble plus a 10-second voice note;
  Workbench displayed the voice-expression prompt, four Telegram cases, and run code `0`
- Expanded/detail state: Workbench Flow/Prompt/Evals/dependents and saved result were inspected;
  Telegram text and audio attachments were both visible
- Persistence/reload result: raw assistant response remained stored before display sanitation;
  Workbench reload preserved the successful run and showed source/live synced
- Local/external prerequisite state: main API and Telegram bot healthy after the later stack restart;
  loopback Workbench restored directly after its watchdog failed to relaunch it
- Evidence retrieval classification, if applicable: successful retrieval from DB/log/state; no
  provider-health substitution was needed
- Fallback path, if applicable: not applicable to the successful xAI synthesis; other providers were
  not represented as real-delivery evidence
- Backend/log/DB confirmation: raw post-fix hash `7448833fbdfc5850`, 182 characters, one valid xAI
  wrapper; xAI telemetry inline `0`, wrapping `1`, total `1`; 162,432 audio bytes; synthesis
  3,847.7 ms; delivery 6,599.5 ms; zero tool calls
- Final model/runtime wording check: the answer embodied the relational state without reciting band
  names, values, prompt mechanics, or voice-provider mechanics
- Substitution check: logs, DB rows, API responses, source inspection, model completions, unit tests,
  and Claude review are supporting evidence; the Telegram delivery and headed Workbench paths were
  run directly and were not replaced by those supporting artifacts

## Automated Evidence

```bash
cd viventium_v0_4/LibreChat
npx jest api/server/services/viventium/__tests__/surfacePrompts.spec.js --runInBand

cd viventium_v0_4/telegram-viventium
PYTHONPATH=TelegramVivBot TelegramVivBot/.venv/bin/python -m pytest \
  tests/test_tts.py tests/test_bot_stream_preview.py \
  tests/test_librechat_bridge.py tests/test_voice_preferences.py -q

PYTHONPATH=. uv run --with pytest --with pyyaml --with jsonschema \
  --with pydantic --with croniter python -m pytest \
  tests/release/test_prompt_architecture_eval_harness.py \
  tests/release/test_prompt_registry.py tests/release/test_prompt_workbench.py \
  tests/release/test_feelings_contract.py -q \
  -k 'feelings_voice_eval_cases or voice_marker_validation or \
  local_jwt_refuses_owner or preserves_truth_invariant or \
  public_prompt_registry_validates_and_compiles or \
  runtime_surface_prompt_fallbacks_match_registry_rendering or \
  live_eval_runner_uses_prompt_bank_equals_flag'

PYTHONPATH=. uv run --with pytest python -m pytest \
  tests/release/test_background_agent_browser_qa_harness.py::\
test_background_browser_harnesses_share_fail_closed_owner_guard_and_cleanup -q

node --check qa/prompt-architecture/evals/run-exact-model-evals.cjs
git diff --check
```

- LibreChat surface-prompt Jest: **78/78 passed**.
- Telegram TTS/bridge/preview/preferences: **200/200 passed**; focused TTS subset **43/43**.
- Focused cross-layer release checks: **7/7 passed** after fail-closed marker hardening, prompt-source
  parity, the Feelings-off negative, stable case-ID restoration, and runner guard wiring.
- Shared non-owner selector and QA-cleanup executable regression: **1/1 passed**.
- Prompt Workbench live exact-model run `20260711T162254Z`: **4/4 turns**, **4/4 independent
  semantic judges**, code `0`, deterministic marker expectations **1/0/0/0**.
- Hardened saved-response recheck: marker counts **1/0/0/0**, malformed wrapper counts **0/0/0/0**, no
  deterministic failures.
- Broader combined release slice: **132 passed, 21 skipped, 7 unrelated dirty-worktree failures**.

## Findings

### Defects

- Pre-fix raw stored replies had xAI control counts `0`, `0`, then `3` only after the user explicitly
  requested full emotional delivery. Their sanitized hashes were `040f5271f28003dd`,
  `33fc3c8c4a6f4ea2`, and `9bb5df1ae325c0d7`.
- The old Telegram xAI fallback explicitly told the model to use controls when the user explicitly
  asked for more emotion or markers. The runtime already supplied Telegram audio intent, selected
  xAI capabilities, and the Feelings capsule, so generation ownership was the defect; sanitizer and
  TTS transport were working.
- xAI marker telemetry was absent from the normal Telegram path.
- The exact-model validator initially accepted an opening xAI wrapper without a closing tag and
  double-counted overlapping inline tokens across dialects; it now requires a complete pair, fails
  malformed wrappers, and deduplicates the all-provider absence count.
- Independent ClaudeViv review confirmed the RCA and core design, then found four drift risks now
  closed here: non-owner local-JWT selection, inline/source prompt parity, the Feelings-off xAI
  negative, and restoration of the stable `EMO-009` truth-invariant case ID.

### Surgical fix

- Keep Feelings as private cause; do not recite its capsule, labels, or values.
- On a structurally voice-capable reply, let the model appraise expressive versus restrained
  delivery from the state and moment.
- If expressive delivery fits and the selected provider supports a fitting control, require the
  smallest fitting documented control without waiting for an explicit request.
- If restraint fits, no control is correct. Plain TTS remains markup-free.
- Runtime supplies capability vocabularies, preserves supported controls for TTS, sanitizes display,
  and emits counts. It does not map numeric bands, user phrases, or keywords to tags.
- The local JWT fallback resolves an admin account from structured user metadata and refuses that
  account before signing; a missing QA selector fails before any model call.
- The inline shared rule must exactly equal its registered prompt source in the Jest suite.

### Regressions

- No feature regression found in the 78 LibreChat and 200 Telegram affected tests.
- The broader release slice has seven pre-existing failures in main-agent expectations,
  Scheduling/GlassHive parity, and unrelated background-activation browser contracts; they remain
  release blockers for their owners.

### Flakes

- Initial Workbench live attempts encountered API-restart and missing-QA-selector failures. After
  the non-owner guard was added, run `20260711T161929Z` failed closed with
  `qa_user_not_found_for_local_jwt` before any model call because the restarted sidecar had lost its
  QA selector. The final explicitly selected QA run completed cleanly and retained an inspectable
  result.

### Environment issues

- A later local stack restart restored the main API and Telegram bot but its watchdog could not
  invoke the CLI from the launch context to relaunch Workbench. Workbench was restored directly;
  a fresh browser reload and eval/draft/sync API checks passed. Watchdog auto-relaunch remains an
  operational follow-up outside this voice-expression change.

### Residual risks

- LiveKit call audio, Telegram voice-note input, real Cartesia/Chatterbox/plain-TTS delivery,
  clean-machine installation, and full-release acceptance were not run here.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
