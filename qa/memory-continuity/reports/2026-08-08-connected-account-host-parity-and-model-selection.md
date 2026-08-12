# Connected-Account, `/host`, And Cognitive-Parity RCA — 2026-08-08

## Outcome

The active local runtime now passes the joined cognitive-integrity gate with zero blockers. The
main agent on browser and Telegram receives the governed saved-memory frame, an authorized recall
capability when enabled, privacy-safe read/write health evidence, and provider capabilities through
the same structural contracts. This is generic continuity evidence, not a rule for one remembered
entity.

The final model decision is Luna/medium for immediate memory writing and nightly hardening;
Sol/xHigh remains the independent deep-reflection and observer route. The full measured comparison
is in `../../memory-hardening/reports/2026-08-08-gpt-5.6-memory-model-eval-final.md`.

## `/host` Is Connected, But It Is Not A LibreChat Account

`/host` means GlassHive may run a local Codex or Claude worker with the machine operator's installed
CLI authorization. LibreChat connected accounts are per-user OAuth records used by that signed-in
LibreChat identity. They deliberately have different owners, scopes, revocation, billing, and audit
boundaries.

Therefore:

- a healthy `/host` worker does not prove a LibreChat user's OpenAI or Anthropic account is readable;
- connecting both LibreChat accounts does not authorize copying those credentials into a host
  worker or another user;
- parity means each path receives equivalent declared capabilities and truthful evidence, not that
  credentials are silently shared;
- connected-account status must decrypt/validate the selected user's record, rather than treating a
  database row as proof of readiness.

The reported mismatch came from an obsolete QA-account selector whose provider records were not
usable. The canonical selector now resolves exactly one non-admin QA identity with a usable OpenAI
route. The writer completes through that user's account; no owner/host credential fallback was
added. Anthropic remains independently health-classified and is not required for the selected
OpenAI/Luna memory route.

## Root Cause Map

The escaped continuity behavior was a joined-system failure, not a missing “who is this?” prompt:

1. The former saved-memory read ceiling could omit legitimate context.
2. GlassHive conversation providers could lose host-owned recall/tool capability at the provider
   boundary or mistake virtual evidence labels for filesystem paths.
3. Unavailable retrieval could be described like a healthy empty search.
4. Per-turn writer health, nightly state, account identity, prompt/config drift, and observer state
   had no single fail-closed view.
5. `/host` machine authorization was incorrectly assumed to imply per-user connected-account
   authorization.
6. Prompt Workbench's overall “latest run” let a later manual success hide a failed scheduled run.
7. A stale Workbench Python listener launched with a relative `--app-dir` could survive a stack
   restart. Its command line omitted the absolute checkout, so the scoped reclaimer refused to
   identify it and the browser could serve pre-fix code on the canonical port.
8. The failed unattended nightly itself lacked the Code Mode companion. The worker emitted an
   explicit prerequisite error, created neither required artifact, and GlassHive correctly failed
   the run's generic evidence contract.
9. Memory-hardening status compared requested and effective fields only inside the most recent
   receipt. After a model-route change, an internally consistent old receipt could therefore remain
   falsely healthy even though the configured tuple had never run.
10. The compiler selected Luna/medium, but the Node hardener's no-generated-env fallback still
    selected Sol/xHigh, creating another degraded-path route split.

## Structural Repair

- Saved-memory storage and read exposure are aligned at an 8,000-token global ceiling with per-key
  budgets, whole-entry selection, and model-visible omission boundaries.
- LibreChat resolves host capabilities structurally and transports them to GlassHive through a
  signed scoped broker. Capability-free turns continue honestly; declared-but-unavailable
  capabilities fail closed.
- Read and immediate-writer outcomes write separate privacy-safe receipts joined to the configured
  QA identity.
- The generic archivist prompt and model-routing config contain no entity, incident phrase, agent
  display name, or user-specific decision branch.
- Source/compiler/live runtime now select OpenAI / `gpt-5.6-luna` / `medium` for immediate writing
  and hardening. The direct hardener fallback now selects the same tuple.
- Scheduled hardening health compares current configured, requested, and effective tuples. A model
  change invalidates the old receipt until the installed schedule path executes the new tuple.
- Every Workbench run now persists `trigger_kind`. Manual execution writes `manual`; scheduler
  dispatch writes `scheduled`. Legacy daily/weekly rows are classified only from their stored due
  time and timezone. The UI labels the provenance and cognitive integrity evaluates the latest
  scheduled run separately from later manual recovery.
- The Workbench lifecycle owner now resolves a relative `--app-dir` against the listener process's
  actual working directory. It reclaims only the exact current-checkout Workbench and still refuses
  to kill another checkout or unrelated listener.
- The Code Mode companion is installed and preflighted as an explicit GlassHive host-worker
  prerequisite.
- The optional Codex nightly observer was updated through the supported automation API to Sol and
  truthful local-time semantics. It reads product receipts; it owns no product schedule or memory
  mutation.

## User-Level Proof

### Native Telegram

A generic synthetic color/code fact was sent through the real Telegram Desktop bot. The immediate
writer receipt recorded OpenAI/Luna completion. After `/reset`, the follow-up conversation had zero
prior messages and recovered both exact fields from saved memory. The write/read receipts, new
conversation id, backend zero-history log, and database value agreed. Exact synthetic conversations,
GlassHive records, and memory changes were removed/restored; the visible chat bubbles were left in
the user's Telegram history because deleting external messages was not required for product cleanup.

### Browser Saved Memory

The real non-admin Test Account stored a generic synthetic preference with conversation recall off,
showed the memory-panel state, recovered it in a fresh conversation, and preserved the result after
reload. Both the earlier Sol control and the final Luna route passed; the final receipt selected
Luna. The fixture was cleaned exactly.

### Prompt Workbench And Scheduler

The live browser first showed why the old health report was wrong: a completed 11:46 manual run sat
above failed 03:00 scheduled runs. After activation, the UI labels those rows `manual run` and
`scheduled run`, preserves both labels after refresh, and cognitive integrity blocked on the latest
scheduled failure.

The failed run's private audit showed the actual cause without exposing private content: the Code
Mode host executable was unavailable, then the generic completion check rejected missing Markdown
and JSON artifacts. A synthetic scheduled-path smoke was created through the UI, fired from the
real scheduler, persisted `trigger_kind=scheduled`, completed six command executions with zero error
items, and produced both required non-empty artifacts. Its schedule and artifacts were removed.

Finally, the original `Subconscious Deep Thought` definition itself was temporarily scheduled for a
real acceptance fire. It completed through Scheduler -> GlassHive host -> Codex -> artifact/evidence
validation. The definition was restored and verified as exactly one active daily 03:00
America/Toronto schedule. The UI still shows the historical failed row, plus the new successful
scheduled row; cognitive integrity now reports the lane healthy instead of erasing history.

## Final Live Integrity Snapshot

- status: `ok`; blocking checks: zero;
- prompt drift: 0 across 76 live/source prompts;
- runtime config drift: zero;
- saved-memory storage/read ceiling: 8,000 tokens;
- QA identity: exactly one configured non-admin account;
- immediate writer: OpenAI / GPT-5.6 Luna / completed;
- saved-memory read: context loaded;
- provider transport: signed broker MCP with host `file_search`;
- GlassHive host: Code Mode enabled and companion ready;
- memory hardening: schedule healthy, latest run success, no execution mismatch;
- Workbench: exactly one active definition, latest scheduled run completed;
- Codex automation: observer only.

## Automated Evidence

- Final joined parent regression set: 385 passed across memory-hardening contract, config compiler,
  memory-model harness, Prompt Workbench, and scheduled-GlassHive tests.
- Nested Scheduling Cortex: 114 passed plus 6 passing subtests.
- Prompt architecture/registry: 83 passed; no-runtime-NLU contract: 4 passed.
- Public QA-result/bootstrap safety: 9 passed; focused private-identifier/incident-literal scan:
  zero report matches.
- Final prohibited-incident-literal scan across runtime source, prompts, Workbench, docs, and QA:
  zero matches for the reported entity/nicknames; the regression bank remains generic.
- Post-restart API, LibreChat, and Workbench health endpoints returned HTTP 200; the joined
  cognitive-integrity rerun remained `ok` with zero blockers.
- Prompt Workbench plus scheduled-GlassHive suite: 152 passed, 5 skipped.
- Scheduled/manual failure-first subset: 3 initial failures before implementation; focused repair
  subset passed, followed by 11 provenance/integrity cases passing.
- Workbench production build: passed.
- Workbench lifecycle relative-path ownership tests: 4 passed in the focused boundary set.
- Model bank: Sol medium 30/30; Terra high 29/30 and disqualified; Luna medium 30/30; Luna low 30/30
  but worse p95/cost; Luna medium 450k-character probe passed.
- Prior carried-forward continuity gates: GlassHive recall 9/9, direct xAI 4/4, browser recall
  enabled/disabled pair passed, focused LibreChat provider/broker suite 101/101, prompt provenance
  suite 52/52, and GlassHive profile set 186/186.
- Installed memory-hardening LaunchAgent: current OpenAI/Luna/medium tuple completed; one applied QA
  mutation was restored by exact run id with one full restore and zero conflicts. The prior natural
  03:00 receipt remains the separate wall-clock cadence proof.

## Truthful Limits And Remaining Release Boundary

This proves the current installed local runtime for the tested identities, paths, and categories. It
does not make Viventium omniscient. Evidence that was never recorded, deleted, unauthorized, not yet
indexed, outside the visible memory budget, or behind an unavailable provider can still be unknown;
the UI and agent must say which condition occurred.

One protected Agent Builder source/live merge remains review-required. No blind agent sync was
performed. The parent and nested component worktrees are dirty and their commits, pins, compiled
delivery artifacts, fresh-clone install, public push, and release are not part of this local proof.
No cloud write, commit, push, or provider credential copy was performed.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
