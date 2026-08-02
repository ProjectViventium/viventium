# GlassHive Voice Call LLM QA Run — 2026-08-01

## Summary

- Result: `PARTIAL` while parent hosted and supported install/upgrade identity gates run.
- Build/source under test: merged LibreChat PR 90, modern-playground PR 10, GlassHive PR 48,
  parent Voice gateway changes, and exact merged component pins.
- Runtime/artifact under test: installed local source runtime using the same reviewed nested trees.
- Environment: local macOS runtime, real LiveKit room, Chrome through Computer Use, separate
  Playwright Chromium, synthetic non-personal prompts, and private raw evidence outside git.
- Tester: Codex plus independent review-only agents; requested Claude Opus 5 is quota-blocked.
- Related change: GlassHive is an optional text author in the existing LiveKit STT -> LLM -> TTS
  cascade. The lighter Voice Call LLM remains the default; native speech-to-speech is not claimed.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MPV-030` capability and validation | `PASS` | 13 schema/package, 17 client, and 16 runtime-override tests | Exact models/effort, LIFE/full defaults, and fail-closed resolution. |
| `MPV-030` endpoint | `PASS` | 69 focused provider tests plus live models/invalid-request probes | Both models declare cascaded voice and reject native realtime. |
| `MPV-030` real call | `PASS` | Audible synthetic turn; one provider run, saved answer, and TTS turn | No wrapper model or spoken activity/reasoning. |
| `MPV-030` refresh | `PASS` | Same call identity rejoined; replacement worker lease-rejected | Original stream completed once and delivered one answer. |
| `MPV-030` End Call | `PASS` | Long in-flight turn cancelled from the real UI | Native request/run cancelled with zero authored output and no TTS. |
| `MPV-030` unhappy paths | `PASS` | Live unknown-model, unsupported-effort, provider-timeout, recovery, and ended-session checks | Errors were bounded, accurate, and public-safe. |
| `MPV-030` browser QA | `PASS` | Computer Use happy path plus independent Playwright CLI degraded path | Visible labels, defaults, readiness, call UX, and stable failure copy. |
| `REL-003` nested/public identity | `PASS` | PRs 90/10/48 merged; merge trees equal reviewed heads | Parent and Native manifests pin exact public-main commits as `merged`. |
| `REL-003` fresh bootstrap | `PASS` | New temporary root cloned and strict-validated all three affected components | Public origins, exact pins, clean worktrees. |
| Parent hosted/install/upgrade closeout | `PARTIAL` | Nested hosted checks and local activation tree passed | Parent hosted and final supported upgrade identity remain. |
| Requested Claude Opus 5 review | `BLOCKED` | Service returned its explicit weekly-limit reset state | No older or weaker model substituted. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-030-A` | Select GlassHive Codex at low effort for Voice Call LLM and reload | Agent Builder in real Chrome | `PASS` | Friendly GlassHive/Codex labels, LIFE, Full, low effort, and ready state persisted | Agent API/Mongo round trip and generated capability config agreed | None |
| `MPV-030-B` | Speak a concise synthetic request | Modern Playground call | `PASS` | Requested answer was heard once | One LibreChat stream, one GlassHive request/run, one Mongo answer, one non-cancelled TTS turn | GlassHive terminal-text TTFT remains slower than the lighter default by design |
| `MPV-030-C` | Reload while a long answer is being authored | Modern Playground call and browser reload | `PASS` | Caller returned to the same call and heard the one completed answer | Same room/call identity; duplicate job lease-rejected; one run and one saved answer | None |
| `MPV-030-D` | Press End Call during a long authoring turn | Modern Playground End Call control | `PASS` | UI returned to Start Chat and no answer was heard | Exact request/run cancelled with zero authored output; no duplicate or TTS | None |
| `MPV-030-E` | Reuse an explicitly ended call | Separate Playwright Chromium | `PASS` | Stable retry guidance and `Call failed to start` toast | Protected connection endpoint returned public-safe 503; no provider detail leaked | None |
| `MPV-030-F` | Select or submit unsupported provider options | Live provider endpoint plus Agent Builder guardrails | `PASS` | Picker exposes exact declared choices only | Unknown model and effort returned precise HTTP 400 classifications | None |
| `MPV-030-G` | Encounter a temporarily unavailable provider | Installed provider process and health probe | `PASS` | Request timed out within the bound; no false success | Same scoped process resumed to authenticated models HTTP 200 with both models | None |
| `MPV-030-H` | Keep fluid default voice unless explicitly choosing GlassHive | Agent config and live call disclosures | `PASS` | Existing lighter Voice Call LLM remained unchanged | Capability split excludes GlassHive from native realtime while allowing cascaded voice | None |
| `MPV-030-I` | Install the affected public components from empty state | Supported component bootstrap in a new root | `PASS` | CLI reported exact public component clones | Strict pin/clean-worktree validation passed for all three | Final parent upgrade closeout remains |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: optional GlassHive Voice Call LLM.
- Requirement: `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`, the provider
  capability split in requirement 01, and the universal-endpoint decision.
- Use case: a user may choose GlassHive Codex or Claude for a call while retaining the lighter
  default, then speak, refresh, interrupt, end, recover, reload, and upgrade without duplicate work.
- QA case: `MPV-030` and `REL-003`.
- Expected result: exact selectable/persistent provider and effort, one universal OpenAI-compatible
  authoring run, inaudible reasoning/activity, durable refresh, explicit cancellation, and clean
  public install identity.
- Actual evidence: all real call, cancellation, reconnect, browser, provider, nested merge, and fresh
  component-bootstrap rows above pass.
- Remaining gap or fix: parent hosted and supported upgrade identity closeout; requested Opus 5
  second opinion remains externally quota-blocked until reset.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and case define acceptance? | Requirements 01/34 and `MPV-030`; release pin case `REL-003`. |
| Code owning path | Which path owns behavior? | Agent capability/validation/UI, LibreChat Voice routes, Voice gateway, playground call routes, and GlassHive provider core. |
| Docs and nested docs/repos | Do docs and nested repositories agree? | Requirement 34 documents the cascaded/native split, cancellation, stable identity, 60-second reconnect, and raw-text resume contract; all nested merge trees match reviewed heads. |
| Scripts or harnesses | What exercised it? | Component bootstrap/validator, local-runtime activation, Computer Use, Playwright CLI, provider probes, and focused/full test suites. |
| Local/external prerequisite state | Were required services healthy or degraded? | LiveKit, STT, TTS, LibreChat, GlassHive, Mongo, and browser surfaces were healthy; provider pause/recovery was exercised; Claude Opus quota was unavailable. |
| Logs | What confirmed the result? | Sanitized counts showed one original worker, one lease-rejected replacement, one completed refresh turn, and one explicit cancelled turn. |
| DB/state/persistence | What persisted? | Agent voice settings survived reload; refresh produced one answer; End Call produced no authored assistant content; provider state recorded one completed and one cancelled run. |
| Generated/shipped artifact | Did built/generated identity match? | Local and hosted LibreChat builds, modern-playground production build, generated capabilities, merged pins, and fresh public clones agree; signed Native distribution is outside this feature claim. |
| Real user path | Which real surfaces ran? | Agent Builder, live Modern Playground with delivered audio, browser refresh, End Call, separate Playwright Chromium, provider recovery, and supported component bootstrap. |
| Visual/UX comparison | Did visible behavior match? | Friendly provider/model/default/readiness labels, audible result, Start Chat after End Call, and stable degraded-session copy matched supporting evidence. |
| Not run / blocked | What remains? | Parent hosted/upgrade closeout remains `PARTIAL`; exact requested Claude Opus 5 review is `BLOCKED` by service quota. |

Supporting evidence does not replace the real user paths above.

## User-Grade Evidence

- Surface exercised: real Agent Builder, Modern Playground call, Chrome refresh, explicit End Call,
  and separate Playwright Chromium.
- Real user path: configured a synthetic agent, spoke through the actual STT path, heard TTS,
  refreshed during authoring, cancelled a separate authoring turn, and inspected retry UX.
- Visible outcome: friendly GlassHive/Codex selection persisted; one concise answer and one long
  refreshed answer were delivered; cancelled output was not delivered; ended-session failure was clear.
- Expanded/detail state: readiness, LIFE/full workspace, effort selector, listening/speaking
  providers, Start Chat, and failure toast/detail were inspected.
- Persistence/reload result: exact voice settings survived Agent Builder reload; the active call
  survived browser reload without a duplicate run; the saved refreshed answer remained singular.
- Local/external prerequisite state: all call/provider services were proven healthy, then provider
  timeout and recovery were exercised. Claude Opus 5 was unavailable due explicit service quota.
- Evidence retrieval classification, if applicable: successful provider models, unsupported
  configuration, bounded provider timeout, and successful recovery were distinguished.
- Fallback path, if applicable: the lighter Voice Call LLM remains the explicit default; no silent
  model fallback or provider remap occurred in GlassHive tests.
- Backend/log/DB confirmation: one happy request/run, one refreshed request/run, one cancelled
  request/run, exact saved settings, one refreshed assistant answer, and zero cancelled authored text.
- Final model/runtime wording check: UI and docs say GlassHive supports the cascaded Voice Call LLM
  and does not claim native realtime audio or native incremental answer tokens.
- Substitution check: automated tests, API responses, logs, DB/state, and independent reviews support
  the browser/audio evidence; they do not replace the real call, refresh, cancellation, or UI paths.

## Automated Evidence

```bash
# From the parent repository root: Voice gateway and dispatch contracts
(cd viventium_v0_4/voice-gateway && python3 -m pytest tests -q)
python3 -m pytest tests/release/test_voice_playground_dispatch_contract.py -q

# From the parent repository root: exact LibreChat package suite and production builds
(cd viventium_v0_4/LibreChat/packages/api && npm run test:ci -- --runInBand)
(cd viventium_v0_4/LibreChat && npm run build:api)
(cd viventium_v0_4/LibreChat && npm run build:client)
(cd viventium_v0_4/agent-starter-react && npm run build)
(cd viventium_v0_4/agent-starter-react && npx tsc --noEmit)

# Hosted nested-repository checks
gh pr checks 90 --repo ProjectViventium/viventium-librechat
gh pr checks 10 --repo ProjectViventium/agent-starter-react

# From the parent repository root: dependency-complete release suite
PYTHONPATH=. uv run --with pytest --with pyyaml --with pydantic --with croniter \
  --with fastapi --with httpx pytest tests/release/ -q

# Fresh public-component bootstrap: FRESH_ROOT was a newly created empty temporary directory,
# CANDIDATE_ROOT was the parent repository root, and the synthetic config enabled local modern
# Voice and GlassHive only. The first command cloned; the second strictly validated the result.
python3 scripts/viventium/bootstrap_components.py \
  --repo-root "$FRESH_ROOT" \
  --lock-file "$CANDIDATE_ROOT/components.lock.json" \
  --config "$FRESH_ROOT/config.yaml"
python3 scripts/viventium/bootstrap_components.py \
  --repo-root "$FRESH_ROOT" \
  --lock-file "$CANDIDATE_ROOT/components.lock.json" \
  --config "$FRESH_ROOT/config.yaml" \
  --validate-only --strict-pinned
```

Evidence totals include: Voice gateway 352 passed plus 48 subprocess subtests; parent dispatch 36
passed; LibreChat Voice route 32 passed; LibreChat package 3,104 passed and 2 skipped; focused
manifest/preflight/CI 131 passed. The dependency-complete full parent release suite passed 2,219
tests with 12 intentional skips in 11 minutes 2 seconds.

## Findings

- Defects: the first live End Call exposed continued native work; scoped cancellation fixed it. A
  hosted provider-native test fixture omitted its required `main_chat` capability; the fixture now
  exercises the fail-closed contract and the complete hosted matrix passes.
- Regressions: no remaining functional regression found in the exercised Voice surfaces.
- Flakes: none accepted. Hosted failure was reproduced and fixed; reconnect replacement dispatch is
  deterministically rejected by the active lease.
- Environment issues: Claude Opus 5 weekly quota blocks the requested final second opinion until
  the service reset. No weaker model was substituted.
- Residual risks: GlassHive terminal authored text has higher TTFT than the lighter default; it is
  intentionally opt-in. Parent hosted and supported upgrade identity closeout remains.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
