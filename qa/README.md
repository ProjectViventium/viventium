# QA

This folder is the public-safe QA operating system for Viventium. It is the place where expected
behavior, test cases, user-grade evidence, and regression history stay organized as the product
changes.

## Operating Contract

- Quality is owned by every developer and AI agent touching the product, not by a later cleanup pass.
- Keep one living QA source of truth per feature or flow under `qa/<feature>/`.
- Before a non-trivial feature, bug fix, runtime change, installer change, or release claim:
  1. read the relevant `qa/<feature>/README.md` and `qa/<feature>/cases.md` when they exist
  2. add or update the cases for the behavior being changed
  3. run the smallest relevant automated tests
  4. run user-grade QA for every affected user-visible surface
  5. save a public-safe result report under the feature folder
- A bug is not fully fixed until the production miss is promoted into a reusable synthetic regression
  case, with expected outcome and rerun instructions.
- Existing QA scope must be revisited when touched code can affect that feature. Do not create a new
  isolated report and leave the living feature cases stale.

## Feature Folder Standard

New or actively touched feature QA folders should converge on this shape:

- `qa/<feature>/README.md` - scope, owning docs, surfaces, environments, quality bar, and latest status
- `qa/<feature>/cases.md` - durable test case catalog with case IDs, expected outcomes, automation, and
  last-result pointers
- `qa/<feature>/coverage.md` - optional coverage matrix for case-heavy features that need
  requirement/agent/surface-to-case traceability
- `qa/<feature>/reports/YYYY-MM-DD-<short-topic>.md` - dated execution evidence and residual risks
- `qa/<feature>/artifacts/` - optional public-safe screenshots, traces, or sanitized snippets

Legacy folders may still have a flat `report.md`. When touching them, keep existing links working and
add missing `cases.md` or `reports/` structure instead of scattering another standalone note. Track
remaining legacy gaps in [`_migration.md`](_migration.md).

Use the templates in [`_templates/`](_templates/) when creating or refreshing a QA area.

## Required Case Metadata

Each case should make these fields obvious:

- `Case ID`: stable, feature-prefixed, and reusable in code comments or test names
- `Requirement`: link to the owning requirements doc or feature section
- `User Outcome`: what the user must see, receive, hear, or be able to do
- `Surfaces`: Web UI, Telegram, Voice, Scheduler, installer, MCP, CLI, or API
- `Preconditions`: account state, connected services, fixtures, flags, and runtime assumptions
- `Steps`: human-repeatable steps, plus automation command when available
- `Expected Result`: visible pass criteria, persistence criteria, and any forbidden output
- `Evidence`: where to find sanitized reports, logs, screenshots, traces, hashes, or DB counts
- `Last Run`: date, result, environment, and report link

## User-Grade QA Bar

Mocked or unit-only checks are not enough for user-facing behavior. For browser-visible flows, use
Playwright CLI or an equivalent real-browser harness. The acceptance loop is:

`real browser prompt/action -> visible UI outcome -> inspect expanded/detail states -> refresh or
persistence check when relevant -> backend/log/DB confirmation -> final model/runtime wording does
not contradict the visible state`

Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.
Skipping the visible browser step is not acceptable for browser-visible behavior even when backend
evidence says the operation succeeded.

For example, background-agent cards are not accepted just because logs say Phase B ran. QA must prove
the browser shows named cards, expanded cards contain the expected result/status, persistence survives
reload when required, stored message parts match the visible surface, and the main answer does not
claim the background work has not run.

For non-browser surfaces, use the closest real user loop:

- Telegram: send/receive through the bot path, then verify delivery ledger and stored message parts.
- Voice or LiveKit: run the actual call/playground path, then verify transcript, latency, interruption,
  and final spoken/text state.
- Scheduler: create or trigger the schedule through the product path, then verify execution, delivery,
  ledger, and catch-up behavior.
- Installer or CLI: run the public command, then verify the installed/running artifact rather than only
  source code.
- MCP/tool flows: verify the model-visible tool contract, auth state, tool result, final answer, and
  failure copy.

## Regression Selection

For every change, run impacted scopes by tracing:

- `trigger -> config/compiler -> runtime -> persistence -> user-visible output`
- changed files to owning feature docs and QA folders
- affected surfaces: Web UI, Telegram, Voice, Scheduler, MCP, installer, CLI, and API
- affected delivery surfaces: source, nested component, compiled artifact, shipped bundle, live runtime

If uncertainty remains, run the broader feature suite and record the residual risk. Do not downgrade a
user-visible failure to "logs looked good."

Rerun cadence:

- rerun impacted feature cases on every change to that feature's owning code, config, prompts, runtime
  wiring, generated artifacts, or delivery surface
- rerun the full feature suite before any release-readiness or production-signoff claim
- refresh `Last Run` whenever a case is rerun; stale pass results are evidence history, not current
  acceptance

## Public-Safe Evidence

QA artifacts in this repo must be public-safe:

- no secrets, tokens, passwords, cookies, or credential-bearing command lines
- no private prompts, private chats, customer data, personal emails, attachments, screenshots with
  private content, or raw transcripts
- no account identifiers, conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo
  `_id` values, or raw provider request/response IDs
- no local absolute home paths, hostnames, machine names, stack traces with private paths, database
  exports, App Support state, live runtime dumps, or raw runtime dumps
- use synthetic non-personal prompts and placeholders such as `/path/to/viventium`,
  `~/Library/Application Support/...`, `<qa-user>`, and `example.com`
- keep private/raw evidence only in the approved private location and summarize it here with sanitized
  counts, hashes, timestamps, pass/fail results, and conclusions

## External Practices Folded In

This QA contract intentionally follows current public guidance:

- [Playwright](https://playwright.dev/docs/best-practices) recommends testing user-visible behavior,
  controlling data, and using web-first assertions.
- [OpenAI eval guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
  emphasizes continuous evaluation on every change and growing eval sets over time.
- [Anthropic eval guidance](https://platform.claude.com/docs/en/test-and-evaluate/eval-tool) emphasizes
  rerunning full eval suites after prompt changes, comparing versions, and grading quality.
- [Anthropic's agent-evals guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  emphasizes explicit success criteria, regression suites, production monitoring, and transcript review.
- [GitLab's quality model](https://handbook.gitlab.com/handbook/engineering/testing/) treats testing as
  everyone's responsibility, integrated throughout development, with risk-focused end-to-end coverage.
- [Regression-testing practice](https://istqb-glossary.page/regression-testing/) requires rerunning
  previously passing behavior after changes to detect defects introduced in unchanged areas.
