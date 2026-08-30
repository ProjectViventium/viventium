# Main Continuity QA

This folder is the acceptance owner for cross-surface Main continuity.

Owning requirement: [`56_Main_Continuity_Kernel.md`](../../docs/requirements_and_learnings/56_Main_Continuity_Kernel.md).
Required environments and surfaces are the installed local runtime, Telegram Desktop, browser,
Prompt Workbench/scheduler, GlassHive, recall/RAG, persistence, restart, and delivery-chain checks.
The quality bar is one bounded cognitive Main that keeps the immediate referent, uses configured
Agent Builder authority, presents one useful answer, degrades truthfully, and never trades answer
quality for speed.

- `contract.v1.json` is the machine-readable requirement, ownership, and case registry.
- `generated-coverage.md` is generated from the registry. Do not edit it by hand.
- dated public-safe results belong under `reports/`.
- private prompts, chats, screenshots, task IDs, runtime data, and identities stay outside this
  repository.

Generate or check the view:

```bash
python3 scripts/viventium/main_continuity_contract.py generate
python3 scripts/viventium/main_continuity_contract.py check
```

Every case must record one canonical overall result—`PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or
`NOT RUN`—against the exact tested candidate. `PASS-LIVE` and `PASS-AUTOMATED` may appear only as
supporting-layer descriptions, never as the overall verdict.
Supporting code/log/DB evidence does not replace the named real user surface.

## Latest status — 2026-08-21

The exact final dirty source is activated. Final-source automation closes group or anonymous reply
attribution, StandardGraph ownership, and exact lost-terminal/404 regressions; a real Chrome
offline-FINAL/resume/refresh run closes the normal final-recovery slice without a phantom branch.
Overall acceptance remains `PARTIAL`: exact live lost-terminal/404 and provider abort/tombstone are
still unproved, and the exact natural Telegram reply passed on repaired pre-final source, not a new
final-source Telegram generation;
background delegation, degraded recall or fallback matrices, performance, a long real-surface soak,
and the clean pin, build, and install chain also remain open. See the latest report and coverage.
