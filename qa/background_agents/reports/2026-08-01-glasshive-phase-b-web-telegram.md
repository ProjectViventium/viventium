# GlassHive Phase B Web and Telegram Acceptance — 2026-08-01

## Verdict

**PASS.** Phase B is active on the real local Viventium web and Telegram surfaces. When completed
cortices added concrete value, the originating Main produced exactly one additive continuation. When
they added no authorized value, the adjudicator recorded a terminal suppression and exposed neither
an extra response nor the internal `{NTA}` marker. A later user turn did not inherit stale cortex work.

This acceptance used public-safe synthetic prompts. Private account identifiers, raw conversation
text, local paths, and screenshots are intentionally excluded.

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

## Automated regression evidence

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
