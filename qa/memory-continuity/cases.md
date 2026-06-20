# Memory Continuity QA Cases

## Case ID Convention

Use stable `MEMCONT-NNN` IDs for memory continuity cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMCONT-001` | Saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth. | User-visible behavior matches source, docs, persisted state, and logs | browser chat, memory state, restore/continuity checks | `tests/release/test_continuity_audit.py` plus user-grade QA when visible | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); current dedupe dry-run found zero duplicate groups/docs/deletes, focused continuity tests passed, and fresh continuity capture was not run because it writes App Support state |
| `MEMCONT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); public report keeps raw runtime, DB, browser, transcript, memory, token, and account evidence out of the repo |
| `MEMCONT-003` | Chat-time saved-memory reads are bounded, writer work is detached, and OpenAI-first provider routing is honored when OpenAI auth exists. | Turning on memory does not inject the full store, wait on writer maintenance/auth failures, route the main chat through stale Anthropic config, or show a red retrieval-tail/finalization error after a valid answer. | browser chat, generated runtime config, live built-in agent state, deep timing logs, memory DB state, CLI migration | API/unit tests, compiler/source audits, browser QA, log timing review, `bin/viventium memory-dedupe --dry-run` | PASS (2026-05-20: read path, detach tests, OpenAI-first route, scoped retrieval-tail and post-stream finalization suppression, browser QA, restart, and dry-run PASS) |

## `MEMCONT-001` - Core User Flow

- Requirement: Saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_continuity_audit.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS/PARTIAL 2026-06-05
  ([nightly review](../memory-hardening/reports/2026-06-05-nightly-routines-health-review.md));
  continuity audit completed, focused release tests passed, and memory dedupe dry-run found no
  duplicate groups in the overnight review. This supports restore/continuity health, but
  user-facing recall behavior still requires separate browser/chat recall QA, and today's scheduled
  hardener skipped on battery before fresh continuity updates.

## `MEMCONT-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-05-27
  ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)); the public
  report uses sanitized counts, timestamps, statuses, and feature identifiers only.

## `MEMCONT-003` - Use Memory Latency And Writer Detach

- Requirement: chat-time saved-memory reads are bounded by `memory.readProfile`, deduped by key,
  do not initialize or await the memory writer on the main response path, and compile the main
  chat plus memory writer onto OpenAI-first provider routing when OpenAI auth exists.
- Risk covered: the `Use memory` toggle makes TTFT or post-text finalization slow because the app
  injects the full memory store, runs maintenance, retries a broken writer on every chat, leaves
  the live main agent on stale Anthropic provider config, or appends a local-retrieval timeout as a
  model-provider error after a valid assistant answer.
- Preconditions: local runtime with memory enabled and synthetic/public-safe saved-memory rows.
- Steps:
  1. Verify source/runtime config exposes `memory.readProfile` with a global read budget, key order,
     per-key caps, and cache TTL.
  2. Run API tests proving the read path uses `getAllUserMemories`, dedupes duplicates, applies the
     budget, and does not call formatted-memory or maintenance helpers.
  3. Run agent-client tests proving `useMemory()` only reads and `runMemory()` initializes the
     writer lazily after the main response path.
  4. Verify generated runtime config and the live built-in main agent both use the expected
     OpenAI-first provider/model when OpenAI auth is available.
  5. Exercise a real browser chat with memory enabled and compare visible response behavior with
     deep timing/log evidence for `build_messages_use_memory`, `chat_completion_done`, and
     `memory_writer_*`.
  6. Run `bin/viventium memory-dedupe --dry-run --json` and confirm it reports duplicate counts
     without applying changes or printing private identifiers.
- Expected result: the user receives the main answer without waiting for memory writer work; memory
  read prompt content is bounded, duplicate-safe, and public-safe QA records only counts/statuses.
- Forbidden result: a memory-enabled chat injects every saved-memory row, runs deterministic
  maintenance before the main model, awaits the writer during finalization, repeats provider 401
  writer attempts every chat with no degraded state, or shows an Anthropic connected-account
  failure, late local-retrieval timeout, or post-stream finalization failure as a model-provider
  error on a mixed install where OpenAI auth is available.
- Evidence to capture: sanitized test output, visible browser result or limitation, deep timing/log
  phase summary, dedupe dry-run counts, and public-safety scan result.
- Automation: targeted API/client/data-provider/script tests plus real browser QA when an
  authenticated local surface is available.
- Last run: PASS (2026-05-20; read path, detached-writer scheduling, OpenAI-first provider routing,
  and browser-visible scoped retrieval-tail/post-stream-finalization suppression passed).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Memory Continuity. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMCONT-UC-001` | On browser chat, memory state, restore/continuity checks, verify that saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth. | owning requirement for `MEMCONT-001` / `MEMCONT-001` | browser chat, memory state, restore/continuity checks | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); dedupe dry-run and focused continuity tests passed, while fresh continuity capture was not run to preserve read-only audit posture |
| `MEMCONT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MEMCONT-002` / `MEMCONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-002. | The user sees an honest setup, retry, or degraded-state result for MEMCONT-002; no fake success is accepted. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMCONT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `MEMCONT-002` / `MEMCONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-002. | MEMCONT-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMCONT-UC-004` | Turn on memory and send a normal browser chat message with existing saved memories present. | owning requirement for `MEMCONT-003` / `MEMCONT-003` | browser chat, generated runtime config, live built-in agent state, deep timing logs, memory DB state | Source, runtime config, live agent model/provider, logs, tests, saved-memory row counts, and dedupe dry-run output. | Main response is visible on the OpenAI-first route without waiting on memory writer work or showing a post-answer provider error; logs/state show bounded read timing and detached writer timing. | PASS (2026-05-20: QA account browser run returned and persisted a `gpt-5.4` answer with no red local-retrieval tail or post-stream finalization error after wait or reload) |
| `MEMCONT-UC-005` | Run saved-memory/provider-key dedupe as dry-run before enabling unique indexes. | owning requirement for `MEMCONT-003` / `MEMCONT-003` | `bin/viventium memory-dedupe --dry-run --json` | CLI output, DB duplicate counts, public-safety scan | Dry-run reports counts only, applies no writes, and does not print private identifiers. | PASS 2026-06-07 ([repair follow-up](../memory-hardening/reports/2026-06-07-nightly-repair-follow-up.md)); dry-run reported zero duplicate groups/docs/deletes and applied no writes |
