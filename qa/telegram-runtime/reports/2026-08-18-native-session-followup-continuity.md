# Native-Session Terse Follow-Up Continuity QA Run - 2026-08-18

## Summary

- Result: **PARTIAL** for `TR-020` and `TELEGRAM-UC-014`: current-checkout automation and a real
  headed isolated local-browser parity path passed, but a real Telegram Desktop turn was not added
  to the owner's account.
- Build/source under test: current checkout with provider-capability ordering, invocation-local time
  delivery, and visible-message usage accounting repairs.
- Runtime/artifact under test: rebuilt `@librechat/api` artifact plus local production rebound to the
  current checkout and restarted.
- Environment: isolated non-admin local browser with public-safe synthetic Alpha/Beta labels; no
  connected-account or external mutation.
- Tester: Codex through a real headed browser plus supporting source, artifact, provider, and
  persistence checks.
- Related change: keep volatile time outside durable native-session authority and avoid assigning
  native-session aggregate provider usage to one visible LibreChat message.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-020` | PARTIAL | Headed browser terse approval correctly resolved the immediately preceding two-label question and survived reload | Real Telegram Desktop send remains unrun |
| `TELEGRAM-UC-014` | PARTIAL | One durable native worker completed both turns; visible user token count remained local and bounded | Telegram owner path remains required |
| Built API artifact | PASS | Timestamp block present by default and absent from durable authority for native-session delivery | Current time remained available in the per-turn header |
| External actions | PASS safety branch | Zero tools or external actions ran | No recipient/account behavior was inferred |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-014-A` | Answer a two-item assistant question with a terse approval | Headed isolated local-browser parity path | PASS for parity path | Assistant resolved both synthetic labels without asking what the approval meant | One native worker completed both turns; visible user count was 27 tokens | Repeat through real Telegram Desktop |
| `TELEGRAM-UC-014-B` | Reload and inspect continuity | Headed isolated local-browser parity path | PASS | Coherent answer remained visible after reload | Canonical visible history and worker identity stayed consistent | Repeat through bot persistence/reopen |
| `TELEGRAM-UC-014-C` | Ensure no accidental external effect | Browser and supporting action trace | PASS | No external confirmation or send appeared | Zero tools and zero external actions recorded | None for this safety branch |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive-backed Telegram/native-conversation terse follow-up continuity.
- Requirement: [Telegram Bridge native conversation continuity](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md) keeps the immediate assistant referent, sends volatile time per turn rather
  than in durable authority, and prunes from local visible usage rather than aggregate native usage.
- Use case: approve or correct an immediately preceding assistant question with a short reply and
  continue the exact task instead of reviving an unrelated older thread.
- QA case: `TR-020` and `TELEGRAM-UC-014`.
- Expected result: the immediate assistant question remains model-visible, time advancement does not
  replace the native worker, local visible-message accounting does not prune the referent, and the
  answer remains coherent after reload.
- Actual evidence: headed browser parity run resolved both synthetic labels, retained a 27-token
  local user message, reused one worker across two runs, and survived reload with zero external tools.
- Remaining gap or fix: run one natural owner-initiated Telegram Desktop turn before promoting the
  Telegram case from `PARTIAL`.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Telegram native continuity, `TR-020`, and `TELEGRAM-UC-014` |
| Code owning path | Which code path owns the behavior? | Provider capability resolution, tool initialization, time-context delivery, built API package, visible-message pruning, and conversation provider |
| Docs and nested docs/repos | Which docs define expected behavior? | Telegram Bridge, Prompt Architecture/token efficiency, and Telegram runtime cases |
| Scripts or harnesses | Which suites exercised it? | AgentClient, endpoint initialization, ToolService, provider-capability, Web-search context, Telegram route, and GlassHive conversation-provider suites |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Local API/Web/playground/GlassHive API/MCP were reachable; real Telegram owner-path execution was intentionally not used |
| Logs | Which sanitized logs confirm or contradict the result? | Worker/session trace showed one native worker and two completed runs with no external actions |
| DB/state/persistence | Which persisted state confirms it? | Canonical parent chain and locally counted visible user message were retained; answer survived reload |
| Generated/shipped artifact | Which generated or shipped artifact was inspected? | Rebuilt `@librechat/api` directly verified and active local production rebound to current checkout; no clean-install claim |
| Real user path | Which real surface was used? | Headed isolated browser sent the setup and terse approval, inspected the response, and reloaded the conversation |
| Visual/UX comparison | Did visible state match supporting evidence? | Yes for browser parity: both labels were handled, no clarification drift occurred, and reload matched worker/persistence state |
| Not run / blocked | Which required surface was not run? | Real Telegram Desktop send/receive and bot reopen were not run |

Supporting evidence cannot replace required user-path evidence. Browser parity, logs, persisted state,
and automated suites support the repair but do not replace the missing real Telegram Desktop path.

## User-Grade Evidence

- Surface exercised: real headed isolated local browser against the current checkout.
- Real user path: established an assistant question about two synthetic reply labels, sent a terse
  approval, inspected the complete answer and locally counted message, then reloaded the conversation.
- Visible outcome: the assistant prepared both requested synthetic labels without asking what the
  approval meant or substituting an older unrelated topic.
- Expanded/detail state: the full visible message chain showed the immediate assistant question,
  terse user approval, and coherent two-label response; no tool/action card appeared.
- Persistence/reload result: the answer remained visible and coherent after reload; the same durable
  native worker had completed both turns.
- Local/external prerequisite state: rebuilt API artifact and local production listeners were
  healthy; real Telegram owner-path evidence was not created.
- Evidence retrieval classification, if applicable: not applicable; this was conversation-context
  continuity, not external evidence retrieval.
- Fallback path, if applicable: not applicable; no provider fallback was required.
- Backend/log/DB confirmation: local visible user usage was 27 tokens, one worker completed two runs,
  canonical history remained linked, and zero tools/external actions ran.
- Final model/runtime wording check: the answer acted on the immediate two-label question and did not
  mention an unrelated PDF/thread or request recipient clarification.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- TDD ordering regression failed before the capability-ordering repair and passed after it.
- Built `@librechat/api` source/artifact regression: **2 passed**.
- Affected LibreChat structural suites: **299 passed**.
- Telegram route suite: **51 passed**.
- GlassHive conversation-provider suite: **133 passed**.

## Findings

- Defects: volatile Web-search time in durable authority replaced the native worker every turn;
  aggregate native-session usage assigned to one visible message pruned the immediate referent.
- Regressions: structured provider capability now decides time delivery, and declared native-session
  bindings use locally counted visible messages for pruning without prompt/recipient/name rules.
- Flakes: none observed in the final affected runs.
- Environment issues: none for browser parity; real Telegram Desktop evidence was intentionally not
  added to the owner's account.
- Residual risks: bot send/receive and reopen continuity remain required for full Telegram acceptance.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
