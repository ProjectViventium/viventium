# Natural Multi-Account Draft Journey — 2026-08-19

## Summary

- Result: **PASS for the requested local journey**. A natural compound Telegram request became two durable review-only draft objectives while Main stayed available. The final state contained one coherent unsent draft for each target and no new sent mail.
- Build/source under test: the current public checkout and its nested LibreChat, GlassHive, and Google Workspace MCP working trees.
- Runtime/artifact under test: installed local production activated twice from the current checkout, including one restart after the final provider-write verification change.
- Environment: local production with real owner-authorized connected accounts; private account identities and mailbox content remain outside this report.
- Tester: Codex using real Telegram Desktop, authenticated Chrome, Apple Mail, runtime logs, and durable GlassHive state.
- Related changes: compact broker discovery, continuation-guidance preservation, duplicate-write discipline, stable multi-account OAuth slots, complete account-slot tool projection, and post-write Gmail draft metadata verification.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-047` | PASS | Real Telegram launch/retry/completion plus a quick unrelated answer while work ran | This is the exact natural compound-draft journey, not a maximum-load claim |
| `GH-MCP-BROKER-017` | PASS | Host handed off the targets and constraints; workers selected connected-account tools | No provider/tool magic words were used |
| `GH-MCP-BROKER-018` | PARTIAL | The initial worker warning contradicted the real saved metadata; the write tool now reads back metadata and compares the exact composed reply subject | A second live external-write replay was intentionally avoided to prevent another draft |
| `GH-MCP-BROKER-028` | PASS | Both Google account slots connected in headed Chrome, persisted across restart, appeared in worker discovery, and one supplied the target thread | Credentials were never copied to worker files or public evidence |
| `GH-MCP-BROKER-029` | PASS | Disabled-provider pruning, real FastMCP effect annotations, and broker escalation were reproduced RED before their fixes | Content-read grants cannot send or mutate Gmail |
| `EXT-UC-003` | PASS for explicit provider-draft branch; overall PARTIAL | Exactly two requested provider drafts remained unsent and reviewable | Chat-only preview followed by a later separate approval remains a separate branch |
| `EXT-UC-005/006` | PASS core | Main answered a quick unrelated question while the draft mission ran | Maximum-load/fairness remains separate |
| `EXT-UC-011` | PASS for negotiation-draft branch; overall PARTIAL | One target received a natural negotiation draft for review | Broader decision/Red-Team parity remains |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Viventium Parallel Work with brokered connected-account actions.
- Requirement: `docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md`.
- Use case: ask naturally for two independent email drafts; Main delegates or reuses each objective, remains conversationally available, and later delivers truthful completion.
- QA cases: `PWK-047`, `GH-MCP-BROKER-017`, `GH-MCP-BROKER-018`, `GH-MCP-BROKER-028`, and `GH-MCP-BROKER-029`.
- Expected result: one review-only unsent draft per target, no send, no duplicate current draft, no provider guessing by the host, and persistent account/tool state after restart.
- Actual evidence: Telegram receipt/completion, quick Main response, two terminal durable objectives, broker discovery of both Google slots plus Microsoft mail, one current matching draft per target in Mail, unchanged Sent state, and connected-slot persistence after restart.
- Remaining gap: post-write metadata verification is automated and active in the restarted runtime, but a second live external write was not made merely to re-prove its improved wording. Broader release gates remain tracked separately.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Requirement and use case | Requirement 55 and the five cases above own the natural delegation, connected-account, write, and wording contracts |
| Code owning path | LibreChat source config/schema/OAuth route and broker; GlassHive continuation/runtime; Google Workspace Gmail draft tool |
| Generated/runtime config | Compiled runtime contains two independently named Google account slots sharing one reviewed provider OAuth endpoint |
| Real user path | Telegram Desktop prompt and quick follow-up; headed Chrome account connection/reload; Apple Mail draft/thread inspection |
| Visual/detail state | Mail showed correct recipient, reply subject, thread, and complete body for the second target; the first target retained one current coherent draft |
| Persistence/restart | API, Web, and playground returned healthy after restart; both Google slots remained Connected; both drafts remained in Drafts |
| Logs | Provider log recorded the requested subject; worker discovery listed both Google slots and Microsoft mail; no send operation occurred |
| DB/state | Separate durable work records reached terminal completion; the quick Main turn completed independently |
| Cleanup | Obsolete test-only drafts were moved to recoverable Trash; no unrelated mail was deleted |
| Not run | No additional external draft was created solely to test new confirmation wording; clean-install/pin/rollback and maximum-load gates remain outside this journey |

If a required real user path was not run, it remains `PARTIAL` or is named above. Logs, state, source, and automated checks support but do not replace the real Telegram/Chrome/Mail path.

## User-Grade Evidence

- Surface exercised: Telegram Desktop, authenticated Viventium Control Panel in Chrome, Apple Mail, local runtime health, and durable GlassHive work state.
- Real user path: sent the natural compound request and a quick unrelated follow-up in Telegram Desktop, completed the missing second-account connection in authenticated Chrome, then inspected the resulting drafts directly in Apple Mail.
- Visible outcome: Main remained responsive while two durable objectives ran, both completion paths returned to Telegram, and Mail contained exactly one current coherent unsent draft per requested target with no new sent mail.
- Expanded/detail state: the second draft was opened in its existing Mail thread and visibly showed the intended recipient, reply subject, and complete requested questions; the first target retained one current negotiation draft.
- Persistence/reload result: after activation and restart, local API, Web, and playground were healthy, both account slots remained Connected in the real Control Panel, and both drafts remained in Drafts.
- Backend/log/DB confirmation: broker discovery exposed both Google slots plus Microsoft mail; separate durable work records reached terminal completion; provider logs recorded the draft write; no send operation occurred.
- Final model/runtime wording check: the live completion initially underreported saved metadata because the provider returned only a draft ID. Mail disproved the warning; the restarted provider now reads persisted unsent metadata back and its no-duplicate failure behavior is covered by automated regression. No additional external draft was created merely to retest wording.
- Substitution check: the result uses real Telegram, Chrome, and Mail surfaces; supporting tests, logs, and durable state corroborate rather than replace those surfaces.

## Automated Evidence

- LibreChat MCP route: **85 passed**.
- LibreChat MCP schema: **6 passed**.
- LibreChat broker/source-selection/adjudication/Active Work: **105 passed**; the final focused broker rerun was **76 passed**.
- Root config compiler: **193 passed**.
- GlassHive account API plus profile runtime: **443 passed**.
- Google Workspace MCP: **6 passed**, including exact composed-reply metadata, post-write verification-failure no-duplicate behavior, and real registered Gmail effect annotations.
- Formatting/static gates: Prettier, Ruff, Python compile/import paths, and scoped `git diff --check` passed.

## Findings

- Root cause: the active compiled capability surface had only the first Google account server even though the user-facing agent still referenced a second slot. The worker therefore searched the wrong connected accounts and could not see the target thread.
- Structural fix: represent account slots explicitly in trusted MCP config, share only the stable provider OAuth endpoint, preserve slot identity through flow state/token storage/tool names, project all slots to Connected Accounts and GlassHive, and require all-account requests to inspect every available slot.
- Escaped wording issue: the draft provider accepted subject/recipient/thread correctly, but returned only the draft ID. The worker interpreted missing verification fields as missing saved fields. The provider now reads the draft metadata back and returns verified unsent state; a failed read preserves the created ID and forbids automatic replacement.
- Independent review findings: Claude reproduced three general blockers after the first live pass: a disabled Google provider left the second server slot behind, reply verification compared the saved `Re:` subject to the pre-composed argument, and unannotated Gmail mutations inherited content-read policy. All three were captured RED before production edits and are now closed by provider-owned slot pruning, exact composed-subject verification, and truthful registered Gmail effect annotations. The final checkout was activated and both configured account slots remained connected after restart.
- No prompt-specific branch, company-specific rule, provider-name routing heuristic, or host-desktop privilege was added.

## Public-Safety Review

- [x] No personal email addresses, private mailbox text, private screenshots, contact names, phone numbers, tokens, cookies, or OAuth codes.
- [x] No raw conversation, message, worker, run, draft, or thread IDs.
- [x] No local usernames, absolute home paths, machine names, DB exports, or credential-bearing commands.
- [x] Account and mailbox evidence is summarized only as non-identifying counts and conclusions.
- [x] Test fixtures use synthetic `example.com` identities and non-personal content.
