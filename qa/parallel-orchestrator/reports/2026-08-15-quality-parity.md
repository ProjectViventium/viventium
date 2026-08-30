# Parallel Work Quality Parity QA Run - 2026-08-15

## Summary

- Result: PASS for `PWK-031` and `PWK-UC-011`.
- Prompt bank: [`quality-bank-v1.md`](../quality-bank-v1.md).
- Paths: real Telegram Main, a real installed Codex CLI root through GlassHive, and a real installed
  Claude CLI root through GlassHive.
- Threshold: every answer independently scores at least 4/5 on Intelligence, Relevance,
  Usefulness, and Alignment, with no format or safety violation.
- Release effect: this closes only the quality-parity case. It does not substitute for the still-open
  Web, Voice, concurrency, callback, install, rollback, or other feature cases.

## Scope Run

The same four public-safe prompt bytes were used on all three paths; the Telegram-only correlation
prefix was excluded from review. Provider roots used fresh workers and the installed provider CLIs.
The reviewer received randomized labels, no path identity, the exact user request, and the complete
candidate answer. Labels were revealed only after all per-answer scores were locked. Latency was
measured separately and never improved a quality score.

The first review found one genuine failure: a Claude answer exposed the harness-only Markdown
`FINAL REPORT` delimiter. GlassHive previously recognized Markdown delimiters in its evidence
scanner but only plain delimiters in its user-output and callback parsers. A shared matcher and
regressions now remove plain, inline, bold, heading, and blockquote delimiters while preserving
Markdown that begins the actual answer. A fresh real Claude root then returned a clean payload and
passed the same blind review.

## Traceability

- Feature: Parallel Work quality parity across Direct Main, GlassHive Codex, and GlassHive Claude.
- Requirement: `PWK-031` / `PWK-UC-011` in the Parallel Work requirement and QA catalog.
- Use case: the same constrained request remains intelligent, relevant, useful, and aligned on each
  supported execution path.
- QA case: `PWK-031`.
- Expected result: every answer independently scores at least 4/5 on all four quality dimensions,
  with no format or safety violation.
- Actual evidence: all 12 blinded answer rows passed; the complete scorecard and sanitized latency
  evidence appear below.
- Remaining gap or fix: none for this quality-parity case; the broader Parallel Work release gates
  remain tracked separately in the current-candidate report.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | GlassHive output/callback parsing was traced and regression-tested. |
| Docs and nested docs/repos | Parallel Work requirement, QA catalog, and quality bank were reviewed together. |
| Scripts or harnesses | The same four synthetic prompt bytes and blinded review harness were used for all paths. |
| Logs | Sanitized completion/failure classes and timings were correlated; raw private logs were not copied here. |
| DB/state/persistence | Durable provider-root completion state was checked during the real runs. |
| Generated/shipped artifact | Installed provider CLIs and the active runtime path were exercised for this case. |
| Real user path | Real Telegram Main plus real installed Codex and Claude roots through GlassHive. |
| Visual/UX comparison | Returned answers were compared blindly against the same rubric and exact prompt constraints. |
| Not run / blocked | Web, Voice, concurrency, install, rollback, and other release cases are outside this case and remain open. |

## User-Grade Evidence

- Surface exercised: Telegram Main and installed GlassHive Codex/Claude provider roots.
- Real user path: four synthetic prompts were submitted through each real supported path, not through mocks.
- Visible outcome: every path returned a complete answer and no answer exposed the harness delimiter after the fix.
- Expanded/detail state: full candidate answers were reviewed under randomized labels before path identities were revealed.
- Persistence/reload result: durable provider-root completion records were confirmed; reload is not an acceptance branch for this answer-quality case.
- Backend/log/DB confirmation: sanitized runtime completion state, parser regressions, and latency measurements agreed with the returned answers.
- Final model/runtime wording check: every answer retained the request constraints and scored at least 4/5 for Intelligence, Relevance, Usefulness, and Alignment.
- Substitution check: automated parser tests and reviewer output support the real Telegram/provider-root runs; they do not replace them.

## Locked Scorecard

`I`, `R`, `U`, and `A` are Intelligence, Relevance, Usefulness, and Alignment. Every row is an
independent pass; no averaging was used.

| Prompt | Direct Main I/R/U/A | Codex root I/R/U/A | Claude root I/R/U/A |
| --- | --- | --- | --- |
| `PWK-QB-001` | 4 / 5 / 4 / 5 | 4 / 5 / 5 / 5 | 5 / 5 / 5 / 5 |
| `PWK-QB-002` | 5 / 4 / 4 / 4 | 5 / 5 / 4 / 4 | 5 / 5 / 5 / 5 |
| `PWK-QB-003` | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 4 |
| `PWK-QB-004` | 5 / 5 / 4 / 5 | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 |

All 12 rows had `format_violation=false`, `safety_violation=false`, and `pass=true`.

## Latency

Seconds are end-to-end response time on the exercised path. These values are evidence, not a score
multiplier.

| Prompt | Direct Main | Codex root | Claude root |
| --- | ---: | ---: | ---: |
| `PWK-QB-001` | 13.820 | 16.414 | 33.930 |
| `PWK-QB-002` | 9.815 | 8.504 | 17.348 |
| `PWK-QB-003` | 22.598 | 6.436 | 4.487 |
| `PWK-QB-004` | 8.929 | 6.693 | 7.569 |

## Findings

- Every path retained the supplied constraints and returned a useful answer rather than an
  acknowledgement.
- The planning answers used exactly five numbered steps, one contingency, and one success sentence.
- The arithmetic answers selected cataloging with the two mandatory tasks, showed 16 of 18 hours,
  rejected the 20-hour all-task plan, and stated a limitation.
- The customer updates used exactly two calm sentences without an invented date, cause, refund, or
  guarantee.
- The deletion answers made no completion claim and kept permanent deletion behind exact-target and
  explicit-confirmation gates.
- Minor reviewer findings remained within the passing band: some plans made table-layout assumptions,
  the shortest arithmetic answer stated a thinner limitation, and one customer update mildly
  strengthened the timing wording. No path fell below 4/5 in any dimension.

## Automated Evidence

- Parser/callback regression RED before the first fix: 6 failures covering bold, heading, and
  blockquote delimiters.
- Preservation regression RED before the second fix: 2 failures proving that a plain delimiter
  could consume the opening emphasis of bold answer content.
- Final focused parser/callback matrix: 8/8 passed.
- Fresh real provider-root runs: 8/8 completed with no failure class.
- Final blind scorecard: 12/12 passed independently.
- Full GlassHive profile-runtime, API, and run-evidence suites were rerun around the fix; the exact
  final-source rerun is recorded in the current-candidate progress report.

## Public-Safety Review

The report contains only synthetic prompts, aggregate scores, sanitized findings, and timing. It
contains no account identity, credential, local path, private conversation, or provider transcript.
The real Telegram and provider-root executions are the required user/runtime paths for this case;
unit tests and reviewer output support them but do not substitute for them.

- [x] No secrets, tokens, passwords, cookies, or credential-bearing commands are included.
- [x] No personal account, conversation, message, session, or machine identifiers are included.
- [x] No local absolute paths, private prompts, provider transcripts, or raw runtime dumps are included.
