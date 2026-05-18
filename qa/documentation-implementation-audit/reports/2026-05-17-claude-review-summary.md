<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Claude Second-Opinion Summary - 2026-05-17

## Scope

Claude was run in structured review-only mode against the local Viventium checkout, with the initial
audit report and key docs/files supplied as context. Claude was instructed not to edit files and to keep
findings evidence-based and public-safe.

The raw Claude JSON output was not committed because it includes local execution metadata. This summary
captures the public-safe conclusions that Codex accepted after review.

## Accepted Additions

### Prompt registry failure is a P0 companion to background-agent drift

Claude found a third failing release suite:

```bash
uv run --with pytest --with pyyaml python -m pytest tests/release/test_prompt_registry.py -q
```

Codex reproduced the result: **1 failed, 20 passed**.

The failure shows resolved main-agent instructions missing the expected runtime-card guardrail text.
Claude's explanation is accepted: source markdown includes the guardrail block, but the JS sync resolver
does not preserve the `includes:` frontmatter content into resolved instructions. This should be fixed
with the background-agent YAML/governance reconciliation, not after it.

### Vendored/shipped component provenance is underdocumented

Claude identified project-like in-tree surfaces that are not nested git repos and are not represented in
`components.lock.json`:

- `viventium_v0_4/LibreChat/viventium/services/librecodeinterpreter/`
- `viventium_v0_4/MCPs/openclaw-bridge/`
- `viventium_v0_4/MCPs/power-agents-beta/`

These need explicit status, provenance/pin policy, docs, and QA ownership if they are shipped surfaces.

### Broken-link count was conservative

The initial audit counted strict markdown links. Claude noted that this repo often cites files in
backticks, which exposes many more missing references. The accepted follow-up is to repair high-impact
links first and then add a release-grade checker that treats backtick-cited file paths as references.

### Telegram tool guard finding was strengthened

Claude confirmed the Telegram keyword/tool-intent guard is read by runtime JS and not emitted by the
compiler, declared in schema, or owned by source-of-truth docs. This strengthens the finding that the
guard is either an undocumented exception or a violation of the no-runtime-NLU rule.

### Additional underdocumented surfaces

Claude identified extra coverage gaps worth carrying forward:

- Telegram Codex `private_chat_only` privacy gate.
- Voice-gateway provider matrix drift.
- GlassHive workflow CLI signature contract.
- MCP OAuth default scope sets.
- Code interpreter service requirements and QA.

## Accepted Repair Order Adjustment

1. Fix prompt-registry `includes:` resolution and background-agent YAML/governance drift together.
2. Reconcile config schema/examples/wizard/compiler/docs.
3. Repair high-impact broken links, including always-loaded operator context, then add a broader link
   checker.
4. Document or pin vendored shipped components.
5. Rebuild the v0.4 systems/architecture/implementation maps.
6. Decide and test the Telegram tool guard behavior.
7. Add missing QA owners and regression tests for the underdocumented surfaces.

## Negative Findings Recorded

- The macOS helper prebuilt/source hash was not identified as a mismatch in this pass.
- Listed `components.lock.json` entries mapped to real nested component repos in this pass.
- Prompt Workbench already has live-drift refusal coverage in release tests, although broader live
  exact-model eval status remains a documented QA limitation.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines included.
- [x] No raw logs, DB rows, private prompts, private account identifiers, or runtime IDs included.
- [x] No local absolute paths, hostnames, machine names, or raw Claude execution metadata included.
