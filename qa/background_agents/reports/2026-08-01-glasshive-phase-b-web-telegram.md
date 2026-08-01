# GlassHive Phase B Web and Telegram Acceptance — 2026-08-01

## Summary

**PASS.** Phase B is active on the real local Viventium web and Telegram surfaces. When completed
cortices added concrete value, the originating Main produced exactly one additive continuation. When
they added no authorized value, the adjudicator recorded a terminal suppression and exposed neither
an extra response nor the internal `{NTA}` marker. A later user turn did not inherit stale cortex work.

This acceptance used public-safe synthetic prompts. Private account identifiers, raw conversation
text, local paths, and screenshots are intentionally excluded.

- Result: PASS
- Build/source under test: final reviewed parent candidate with merged LibreChat and GlassHive trees
- Runtime/artifact under test: active installed local production runtime
- Environment: local macOS web and Telegram surfaces
- Tester: Codex with real-browser and Computer Use verification
- Related change: GlassHive provider routing for substantive cortices and same-session Phase B

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `ACT-34` | PASS | Visible Phase A plus one additive continuation or terminal suppression | No replay or exposed internal no-response marker |
| `ACT-35` | PASS | Agent Builder and persisted agent config matched GlassHive/Codex/LIFE/access/effort | Red Team used measured interactive `high` |
| `ACT-47` | PASS | Serialized host-busy retries and terminal capacity wake in live and automated evidence | One native authentication lane remained authoritative |
| `ACT-48` | PASS | Useful, suppressed, and moved-on web/Telegram cases | Novelty and stale-turn controls behaved as documented |

## Delivered runtime contract

- Phase A remains the separate fast direct classifier (`groq / qwen/qwen3.6-27b`) and does not run
  through GlassHive.
- All 11 built-in substantive cortices run as normal Agent provider selections through
  `glasshive-harness / codex-cli:gpt-5.6-sol`, canonical LIFE workspace, full access.
- Effort follows workload instead of using one expensive setting everywhere:

| Effort | Cortices |
| --- | --- |
| `low` | Emotional Resonance, Google, MS365, Viventium User Help |
| `medium` | Background Analysis, Confirmation Bias, Parietal Cortex, Pattern Recognition |
| `high` | Red Team, Strategic Planning |
| `xhigh` | Deep Research |

Red Team uses `high` on the interactive GlassHive route because a measured `xhigh` Red Team run
took 177 seconds before queue time. Its direct OpenAI fallback remains `xhigh`; Deep Research remains
GlassHive `xhigh`.

- Phase B uses the originating Main provider and, for GlassHive, the same native conversation
  session. It compares concrete facts, risks, decisions, and actions against the Phase A response.
- Specialist prompts do not inherit Main-only exact-output instructions and do not restate the user
  request or Phase A. Specialist output remains independent evidence; Main alone authors the user
  continuation.
- Feelings remains a Main speaking-path input exactly once and is not injected into specialists.
- The outer cortex execution guard is one hour, covering supported long runs plus serialized native
  CLI capacity. Host-busy work uses bounded retry plus immediate lane wake, without weakening the
  one-active-native-CLI authentication boundary.
- Disconnect recovery reattaches to the durable provider request; explicit cancellation remains
  irreversible, and terminal releases wake only the matching runtime lane.

## Real web acceptance

The browser harness used a real logged-in Viventium session, expanded the background-agent cards,
reloaded the conversation, and correlated the visible result with API and Mongo state.

| Case | Result | Evidence |
| --- | --- | --- |
| Useful additive continuation | **PASS** | Red Team and Confirmation Bias were visible and terminal; Phase A text remained visible before and after reload; two stored cortex parts; one structured Phase B child; decision `persisted/generated/llm_generated`; 137-character continuation; novelty ratio `0.875`; zero console, request, or critical HTTP errors. |
| No useful/authorized continuation | **PASS** | Both required cards were visible and terminal; Phase A remained visible after reload; decision `suppressed/nta/no_response_suppressed/no_response_tag`; zero Phase B children; `{NTA}` never appeared; zero browser/network errors. |
| User moved on | **PASS** | Setup work reached a terminal `suppressed/empty/moved_on_empty_followup` decision; the next turn returned its exact seven-character control answer once; zero scoped cortex parts and zero Phase B children before or after reload. |

Agent Builder was also inspected through the real UI. Red Team showed **GlassHive**, **Codex / GPT-5.6
Sol**, **Viventium LIFE**, **Full access**, **high**, and an authenticated/ready status.

## Real Telegram acceptance

Telegram Desktop was exercised as a user with one synthetic positive turn and one later-turn negative
control. No raw chat content or account identity is retained in this report.

- The positive turn visibly delivered one initial response and one later additive continuation.
- Mongo stored a 372-character Phase A parent with exactly two `complete` cortex parts:
  Confirmation Bias (649 characters) and Red Team (183 characters).
- Phase B stored exactly one 152-character child with
  `persisted/generated/llm_generated` decision metadata. There was no duplicate authoring child.
- GlassHive recorded exactly four correlated completed runs: Main Phase A `9.2s`, Red Team `31.7s`
  after two capacity retries, Confirmation Bias `11.1s` after five capacity retries, and Main Phase B
  `6.3s`.
- Telegram delivery logs show the model skipped voice for the 372-character initial response
  (`send=0`, `voice_decision=skipped_model`) and delivered the proactive continuation once
  (`send=1`, one segment, no message breaks). This also proves the restored per-response voice-skip
  control survives the Phase B path.
- The next synthetic user turn returned the exact 17-character control answer, stored zero cortex
  parts and zero Phase B children, and recorded `skipped/skipped/no_usable_phase_b_output`. No stale
  continuation arrived.

## Configuration, persistence, and drift evidence

- Live Mongo contains all 11 cortices on the exact GlassHive/Codex/LIFE/full-access matrix above.
- Generated runtime and service environment both set
  `VIVENTIUM_CORTEX_EXECUTION_TIMEOUT_MS=3600000`.
- The generated agent bundle contains Red Team `high`, LIFE, and full access. The prompt bundle
  contains the Phase B original-user-request input and the independent-specialist output contract.
- Supported compile/start preserved the existing LIFE folder additively (`0` files added, `73`
  preserved). The legacy source folder was not touched.
- A/B/C comparison covered 13 built-in agents and found one proposed tracked model delta versus
  HEAD: Red Team `xhigh -> high`. Live already matches that value. Three unrelated user-managed
  drifts remain protected and were not synchronized: Connected Accounts provider/fallback fields,
  Main fallback/background-cortex fields, and Red Team instructions. Adjacent LibreChat config has
  zero live/source or worktree/HEAD drift.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: conditionally activated Background Cortices and Phase B continuation.
- Requirement: `docs/requirements_and_learnings/02_Background_Agents.md`.
- Use case: Main receives useful completed cortex evidence, adds one non-repetitive continuation, or
  remains silent when evidence is not valuable or the user has moved on.
- QA case: `ACT-34`, `ACT-35`, `ACT-47`, and `ACT-48`.
- Expected result: one provider-authored continuation at most, durable cards/state, no stale or
  duplicate response, and no specialist appropriation of Main-only Feelings or wording constraints.
- Actual evidence: real web and Telegram acceptance, persisted message/cortex/decision counts,
  correlated completed GlassHive runs, generated config, and the automated matrix below.
- Remaining gap or fix: Claude review was unavailable because the signed-in plan quota was exhausted;
  this did not replace or weaken the real user-path gate.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Background Agents requirement plus `ACT-34/35/47/48` |
| Code owning path | Which code owns it? | LibreChat activation/execution/follow-up services and GlassHive conversation runtime |
| Docs and nested docs/repos | Where is expected behavior defined? | Background Agents requirement, living cases, LibreChat and GlassHive merged source |
| Scripts or harnesses | What exercised it? | Browser harness, Computer Use, focused and broader automated suites |
| Local/external prerequisite state | Were dependencies healthy? | Web/API, GlassHive, Telegram bridge, and native harness auth were healthy |
| Logs | What corroborated delivery? | Sanitized Phase B decisions, capacity retries, delivery controls, and terminal run events |
| DB/state/persistence | What persisted? | Sanitized parent/child/cortex-part counts and decision metadata |
| Generated/shipped artifact | What runtime artifact was checked? | Generated agent/config bundles and active installed checkout |
| Real user path | Which user surfaces ran? | Logged-in browser via Computer Use and Telegram Desktop |
| Visual/UX comparison | Did visible behavior match? | Cards, initial response, continuation/silence, and reload all matched |
| Not run / blocked | What remained unavailable? | Requested Claude second opinion only; real product acceptance was run |

## User-Grade Evidence

- Surface exercised: logged-in Viventium browser, Agent Builder, and Telegram Desktop.
- Real user path: sent synthetic prompts, expanded cortex cards, observed initial and follow-up
  delivery, reloaded the browser, and sent a later-turn Telegram control.
- Visible outcome: useful evidence produced exactly one additive continuation; non-useful and moved-on
  cases stayed silent without exposing the internal no-response marker.
- Expanded/detail state: named terminal cortex cards and their public-safe status/result detail were
  visible in the browser.
- Persistence/reload result: Phase A, cortex cards, decision metadata, and the continuation/suppression
  state survived reload without replay.
- Local/external prerequisite state: LibreChat, GlassHive, Telegram bridge, native CLI auth, and the
  active runtime were healthy; an unrelated Scheduler status issue was excluded from this result.
- Backend/log/DB confirmation: sanitized logs, Mongo counts, GlassHive run totals, generated config,
  and Telegram delivery controls matched each visible turn.
- Final model/runtime wording check: the Main authored the continuation in its existing session and
  never claimed that completed background work was unavailable.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

| Surface | Result |
| --- | --- |
| Root compiler/governance/browser-harness/upgrade/prompt registry | **382 passed** |
| LibreChat Phase B, cortex service, specialist surface prompts, runtime model normalization | **252 passed** |
| GlassHive provider/API and conversation endpoint | **256 passed** |
| Telegram bridge, `{NTA}`, stream preview, and delivery controls | **186 passed** |
| Broader root release matrix from the same candidate | **435 passed, 24 skipped**; dependency-complete Prompt Workbench rerun **130 passed** |
| Clean install/upgrade acceptance from the same candidate | **444 focused tests passed** plus fresh install, upgrade, LIFE preservation, direct provider API, Playwright, and Computer Use |

The only test warning is the existing Starlette TestClient/httpx deprecation notice. It does not
change runtime behavior.

## Happy and unhappy-path coverage

Automated and live coverage includes useful continuation, NTA suppression, user-moved-on
suppression, latest-turn non-activation, provider/model persistence, provider-native fallback bags,
invalid/unavailable provider handling, outer timeout, busy native lane retries, immediate capacity
wake, worker failure, pause, interrupt, cancel, termination, process recovery, browser refresh,
transport disconnect/reconciliation, duplicate prevention, specialist ownership, and Phase B
persistence/reload.

The global status command reported the web/API, GlassHive, Telegram bridge, Telegram Codex, recall,
web-search, and connected-account MCP services running. It separately reported an unrelated existing
scheduler delivery-status issue; that scheduler issue was not used as Phase B evidence and is outside
this acceptance scope.

## Acceptance mapping

- `ACT-34`: Phase A remains durable; one additive continuation or terminal suppression; no replay.
- `ACT-35`: live Provider/Model/LIFE/access/effort settings and fallback-family normalization.
- `ACT-44`: specialist independence from Feelings; Main-only synthesis.
- `ACT-46`: specialists do not inherit Main-only wording/shape constraints.
- `ACT-47`: serialized GlassHive lane retries and terminal capacity wake.
- `ACT-48`: concrete novelty, consent, generated continuation, `{NTA}`, and moved-on controls.

## Findings

- Defects: the original Phase B loss/replay and provider-routing gaps are fixed.
- Regressions: none observed in web, Telegram, persistence, or automated acceptance.
- Flakes: none remained in the final affected suites.
- Environment issues: requested Claude review was blocked by external plan quota; the unrelated
  Scheduler status noted during this earlier run was later diagnosed and repaired separately.
- Residual risks: real LiveKit remained governed by its separate voice acceptance and was not used as
  evidence for this text/Telegram Phase B result.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
