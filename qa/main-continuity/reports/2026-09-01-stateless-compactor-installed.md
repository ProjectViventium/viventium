<!-- qa-evidence-exempt: Focused partial-path receipt; it does not claim full L1 acceptance, and retrofitting uncaptured template fields would invent evidence. -->

# Installed stateless compactor QA

Date: 2026-09-01

## Result

`PARTIAL` overall; the repaired installed path passes.

## Passed

- The supported activation path validated and restarted the current dirty candidate.
- API, Web, Playground, Scheduling, GlassHive, Prompt Workbench, Voice, and RAG health checks
  returned HTTP 200.
- Four exact Main replies remained correct after restart and browser reload while compaction ran in
  the background.
- Two semantic compactions reused one broker session, project, and worker but started distinct fresh
  native model sessions. The worker's persistent native session file remained byte-identical.
- Both durable provider decisions recorded trusted typed stateless mode. Request text cannot opt in.
- The relevant LibreChat suite passed 163/163. GlassHive stateless checks passed 11/11, with 42/42
  adjacent provider and recovery checks.
- Independent review scored the final source 9/10 with no material source defect before install.

## Still open

- Installed compactions took about 134 and 104 seconds. Main stayed responsive, but long-horizon
  latency is not closed.
- The real 100-plus-turn soak, 96 KiB boundary, reboot recovery, and forced live transient-failure
  path are not complete.
- Historical pending/degraded continuity state and old non-terminal request labels need supported
  reconciliation. No history was deleted or rewritten for this QA pass.
- The candidate is installed but dirty and unshipped.

Private prompts, runtime identifiers, state extracts, and screenshots stay in the private evidence
pack.
