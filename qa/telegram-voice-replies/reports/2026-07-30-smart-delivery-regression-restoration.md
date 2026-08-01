# Telegram Smart Delivery Regression Restoration - 2026-07-30

## Summary

PASS for the local installed direct Telegram output path. The Main Agent can again choose whether a
text-mode answer should omit optional audio with `{SKIP_VOICE}` and can divide one logical answer
into bounded Telegram bubbles with `{MSG_BREAK}`. Controls are not shown, spoken, or persisted.
Proactive callback delivery and clean structured persistence pass automation but remain PARTIAL
until a fresh real callback is observed after this restoration.

Current-candidate note (2026-07-31): the prior live evidence below remains historical. The release
candidate replaces source-prefix rotation with post-render, tag-balanced UTF-16 chunking. Its full
Telegram suite passes `378/378`; the changed installed path remains `PARTIAL` until the dated
post-activation Telegram Desktop pass is appended.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TGVOICE-006`, `TGVOICE-UC-007` | PASS direct; PARTIAL proactive | Real Telegram Desktop skip and explicit-audio turns, logs, stored state, plus direct/proactive automation | Voice-note input/STT and a fresh proactive callback were not rerun |
| `TGVOICE-007`, `TGVOICE-UC-008` | PASS direct; PARTIAL proactive | Real two-bubble turn, one audio attachment, conversation reopen, stored state, and split-stream/callback regressions | LiveKit, other TTS providers, and a fresh proactive callback are outside the completed live pass |

## Traceability

- Feature: model-owned Telegram optional audio and natural message boundaries.
- Owning docs: `docs/requirements_and_learnings/03_Telegram_Bridge.md` and
  `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`.
- QA cases: `TGVOICE-006`, `TGVOICE-007`, `TGVOICE-UC-007`, and `TGVOICE-UC-008`.
- Expected result: read/copy/edit-first artifacts can remain text-only; ordinary or explicitly
  spoken replies can retain one audio attachment; conversational answers can use at most three
  complete bubbles while remaining one persisted assistant turn.
- Forbidden result: runtime intent heuristics, control leakage, missing text, fragmented bubbles,
  duplicate turns, repeated audio, or a control being removed before Telegram can act on it.

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`
is satisfied by the owning docs, the four cases above, real Telegram output, correlated GlassHive,
log and DB/state evidence, and the explicitly bounded scope.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Requirement and use case | Owning Telegram and prompt-architecture docs align with `TGVOICE-006` and `TGVOICE-007` |
| Code and nested component | Shared grammar, LibreChat prompt/transport/persistence, Telegram bridge/bot/TTS, and proactive callback paths inspected |
| Docs and nested docs | Root requirements, systems map, nested expected behavior, and Telegram README updated |
| Tests and harnesses | Full Telegram, affected LibreChat, release contracts, compiler checks, and headed Prompt Workbench preview passed |
| Generated or shipped artifact | Generated runtime prompts contained both registered smart-delivery prompt IDs after activation |
| Real user path | Telegram Desktop skip, split, explicit-audio, and reopen flows passed |
| Logs, DB/state/persistence | One assistant row per turn, zero stored controls, and structural voice/break logs agreed with visible output |
| Remaining gap | A fresh proactive callback, voice-note input/STT, LiveKit, and every TTS-provider route were not run and are not claimed |

## Findings

### Root Cause And Fix

The July 22 implementation was not present in the active component history. The live branch
therefore omitted the prompt sources, shared parser,
persistence sanitizer, Telegram transport handling, TTS guard, and regression tests.

During restoration, live QA exposed a second boundary defect: the GlassHive-authored response
contained `{SKIP_VOICE}`, but LibreChat sanitized it before the authenticated Telegram final event.
The streaming extractor also removed complete or chunk-split controls before Telegram received
them. The surgical fix now:

1. keeps the controls in the authenticated Telegram transport stream only;
2. continues to sanitize the persisted assistant message;
3. preserves partial controls across streamed chunks until the Telegram bridge assembles them;
4. parses both controls through one equivalent JS/Python grammar;
5. bounds semantic delivery to three complete bubbles, performs mandatory transport splitting only
   after rendering, and sends audio only once after the final physical message;
6. stores proactive Phase B text without reserved controls, preserves its decisions as structured
   metadata for Telegram transport, and strips controls before TTS.

No prompt-text or keyword classifier was added. The agent owns the semantic choice; runtime only
validates and executes the structural controls.

### Independent Review And Hardening

A review-only Claude Opus 5 Max pass challenged the restored boundaries after the first live run.
It found three P1 gaps, all fixed before final acceptance:

1. proactive follow-ups persisted raw controls even though Telegram display looked clean;
2. interrupted/error snapshots used a voice-only sanitizer and could persist Telegram controls;
3. a non-formatting edit failure on bubble one could abort bubble two and its final audio.

The repaired contract now saves clean proactive text plus control-free structured delivery metadata,
sanitizes every Telegram snapshot, requires the authenticated Telegram route flag before controls
can leave LibreChat, retries the first final edit safely, and fails closed before later delivery or
audio after an unrecoverable Telegram error. Equivalent invalid-limit coercion is also enforced in
JavaScript and Python.

## User-Grade Evidence

The active local runtime was rebuilt, restarted from the current checkout, and exercised through
Telegram Desktop using synthetic, public-safe prompts. No screenshots or private transcript text
are stored in this public report.

- Surface exercised: Telegram Desktop, the installed local Telegram Bridge, GlassHive, and the
  headed Prompt Workbench browser UI.
- Real user path: requested a copy-ready artifact, a two-beat conversational answer, and an explicit
  spoken answer; reopened the conversation; then repeated the copy-ready path after the independent
  review fixes and again after the pushed commits, matching component pin, and final runtime restart.
- Visible outcome: complete text-only artifact, two complete bubbles with one final audio, and clean
  explicit text plus one audio; no control was visible.
- Expanded/detail state: Prompt Workbench showed both prompt objects and all five
  `telegram_smart_delivery` cases.
- Persistence/reload result: reopening Telegram preserved the clean turns; the database held one
  assistant row per each of five synthetic turns with zero controls.
- Backend/log/DB confirmation: GlassHive raw output contained the skip decision; Telegram logs
  recorded the effective skip or break counts; stored state matched the UI.
- Final model/runtime wording check: GlassHive authored the semantic decision, while runtime only
  validated the structural controls; no intent heuristics or provider-specific branching was added.
- Substitution check: tests, logs, raw worker output, generated config, and DB rows support but do not
  replace the required Telegram Desktop and headed browser evidence, both of which were run.

| Natural user path | Visible result | Supporting evidence | Result |
| --- | --- | --- | --- |
| Request a copy-ready synthetic email, then repeat after review and committed-runtime restarts | All three complete emails appeared as text; no audio or control text appeared | GlassHive/Telegram recorded model-selected audio suppression and one segment on all runs | PASS |
| Request a friendly two-beat answer | Exactly two complete bubbles appeared; one audio attachment followed the logical answer | Telegram logged one message break, two segments, and one audio delivery | PASS |
| Explicitly request a spoken answer | Clean text plus one audio attachment appeared | Telegram logged no effective skip and one audio delivery | PASS |
| Reopen the Telegram conversation | Bubbles and audio remained visible with no controls | Reloaded UI matched persisted conversation state | PASS |
| Inspect stored assistant turns | One assistant row existed per synthetic turn; no controls were stored | Database summary: five turns, one assistant row each, zero control leaks | PASS |
| Inspect Prompt Workbench | Both prompt objects and the five-case smart-delivery family were visible | Headed Playwright selected `telegram_smart_delivery`; five-case preview completed with code 0 | PASS |

The successful skip run also proved the actual authoring route: the live GlassHive worker received
the smart-delivery prompt, authored the control, and Telegram acted on that same output.

## Automated Evidence

```bash
cd viventium_v0_4/telegram-viventium
uv run --project TelegramVivBot --with pytest --with pytest-asyncio pytest -q tests

cd viventium_v0_4/LibreChat/api
npx jest \
  server/services/viventium/__tests__/deliveryControls.spec.js \
  server/services/viventium/__tests__/surfacePrompts.spec.js \
  server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js \
  server/controllers/agents/__tests__/requestPersistence.spec.js \
  test/services/viventium/backgroundCortexFollowUpService.test.js \
  test/services/viventium/cortexMessageState.test.js \
  --runInBand

uv run --with pytest --with pyyaml python -m pytest -q \
  tests/release/test_delivery_controls_contract.py \
  tests/release/test_prompt_registry.py \
  tests/release/test_no_runtime_nlu.py
```

- Historical restoration Telegram suite: **338 passed**.
- Current post-render chunking candidate: **378 passed**.
- Affected LibreChat suites: **239 passed** across six suites.
- Cross-layer release contracts: **31 passed**.
- JavaScript syntax checks and Python compilation checks: **PASS**.
- Prompt Workbench headed browser preview: **5/5 cases selected**, code **0**.

Automated unhappy-path coverage includes controls split across stream chunks, incomplete controls in
previews and interrupted streams, controls inside literal/code content, excess break controls, TTS
sanitation, proactive callback chunking, visible partial-delivery interruption, formatting fallback
recovery, explicit-audio override, and persistence without control leakage.

## Runtime And Delivery Evidence

- The installed local runtime was activated from the current checkout and restarted successfully.
- Core web, Telegram Bridge, GlassHive, and Prompt Workbench were running during user QA.
- Generated prompt output contained both registered smart-delivery prompt IDs.
- One Telegram bot process owned the live polling route during final acceptance.
- Logs, raw worker output, generated config, UI, and database state agreed on the final decisions.

An unrelated Conversation Recall health warning remained present in the local stack. It did not
participate in this Telegram output path and is not represented as fixed here.

## Scope And Residual Risk

- This pass changes Telegram answer delivery, not Telegram voice-note input/STT. Voice-note-originated
  answers share the optional-audio output prompt and pass automation, but that real input/output path
  was not rerun. Existing `TGVOICE-004` evidence remains the owner for the separate input path.
- Direct Telegram delivery is user-verified. Proactive callback delivery and clean structured
  persistence pass focused automation but remain PARTIAL for a fresh real callback.
- The three-bubble bound applies to semantic controls. Mandatory post-render splitting may create
  additional tag-balanced physical messages for a very long answer; it does not alter the semantic
  controls or persisted logical turn.
- It does not claim broader LiveKit or every TTS-provider acceptance.
- The five-case Workbench run in this report was a structural preview; the five real Telegram
  turns used the live GlassHive authoring model and provided the exact-model behavioral evidence.
- One broad QA operating-contract test still fails on unrelated pre-existing template debt across
  older reports; the focused feature gates above pass.

## Public-Safety Review

- [x] No secrets, tokens, private chats, attachments, or screenshots are included.
- [x] No local absolute paths, usernames, hostnames, raw IDs, or private runtime dumps are included.
- [x] Evidence is summarized with synthetic prompts, counts, statuses, and structural conclusions.
