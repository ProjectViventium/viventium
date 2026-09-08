# Prompt Workbench

## User promise

Every runtime prompt has one visible authoring owner, deterministic composition, exact compiled and
live lineage, useful evaluation, and a recoverable rollout path.

## Requirements

### Lineage

- **GOV-001:** Workbench shows source, owner, order, composition, compiled and live state, version,
  duplication or drift, and evaluation evidence.

### Canonical source

- **GOV-003:** Every runtime prompt has visible Workbench lineage. Hidden inline fallback text cannot
  alter model behavior.
- **GOV-025:** Only clean tracked authoring sources can own prompt truth. Generated files, installed
  outputs, and path aliases cannot become compiler inputs.

### Operations

- **CC-027:** Workbench is the operational view for prompt composition, schedule prompt/model/effort,
  dependencies, history, channel results, latency, cost, and disposition; do not add a duplicate
  continuity dashboard.

### Authentication

- **HARD-020:** Workbench credentials never enter URLs, browser history, referrers, logs, or
  persistent local storage.

## Change contract

1. Edit the registered authoring source.
2. Resolve includes, variables, placeholders, and order through the shared resolver contract.
3. Compare source, compiled, and live bytes.
4. For semantic behavior, evaluate sanitized positive, negative, and adjacent cases on the exact
   configured models.
5. Use the installed headed browser to inspect, edit, evaluate, publish or roll back as applicable.

Sync proves byte movement, not model quality. Model review supports but never replaces exact-model
evaluation or installed user QA.

## Owners and QA

- Architecture: [Prompt Workbench](../../architecture/prompt-workbench.md)
- Registry and sources: nested LibreChat `viventium/source_of_truth/prompts/`
- Compiler: `scripts/viventium/config_compiler.py`
- Workbench CLI: `scripts/viventium/prompt_workbench.py`
- Workbench service package: `viventium_v0_4/prompt-workbench/backend/prompt_workbench/`
- QA: `qa/prompt-architecture/` and `qa/prompt-workbench/`

## Detailed contracts

- [Prompt Architecture and Token Efficiency](../49_Prompt_Architecture_and_Token_Efficiency.md)
