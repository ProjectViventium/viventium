<!-- qa-evidence-exempt: Sanitized A/B/C summary; raw pull artifacts, identities, prompts, tool names, and local paths remain outside the repository. -->

# Agent Builder A/B/C review — 2026-08-09

## Decision status

- Result: REVIEW REQUIRED; no live Agent sync was applied.
- A: current live non-admin user Agent configuration.
- B: tracked local source-of-truth Agent bundle.
- C: current source-of-truth and adjacent scaffold changes versus repository `HEAD`.
- Runtime prompt bundle and compiled scaffold currently have zero active drift; this report concerns
  protected user-level Agent records and proposed tracked edits.

## A versus B

The compare found differences on all 13 managed Agents:

- the main Agent has the same 11 cortex identities but different activation fallback ordering;
- Connected Accounts differs in instructions, tool inventory (52 live versus 36 tracked), primary
  provider/model, and model/voice parameter bags;
- several background Agents retain live full-workspace GlassHive options that the tracked bundle
  would remove;
- several background Agents retain live Anthropic fallback assignments while the tracked bundle
  proposes GlassHive/Opus fallback assignments;
- some specialist instructions differ between live and tracked text.

These are not safe to collapse into a broad push. In particular, a whole-bundle source win would
remove live tools/workspace fields and move Connected Accounts onto the currently disconnected Test
Account Anthropic route. A whole-bundle live win would discard intended source fallback/model work.

## C versus current repository base

- The tracked bundle proposes changes on 13 Agents.
- The adjacent LibreChat scaffold proposes two conscious-route field changes: direct OpenAI/Sol to
  GlassHive-hosted Codex/Sol.
- Live scaffold versus tracked scaffold is currently aligned; the two adjacent changes are proposed
  changes versus `HEAD`, not active runtime drift.

## Recommended reconciliation

Use an explicit field-level merge, not a default sync:

1. preserve live Connected Accounts tools and its currently usable provider until Anthropic is
   reconnected and separately proven;
2. preserve live workspace/access fields unless the user intentionally removes them;
3. review the source-owned GlassHive/Opus fallback migration per specialist;
4. reconcile activation fallback ordering against real provider health;
5. dry-run the narrowest `--agent-ids` plus prompt/model/activation-specific operation;
6. apply only after explicit review, then pull/compare again and rerun the affected browser paths.

No user-managed Agent field was overwritten during this work.
