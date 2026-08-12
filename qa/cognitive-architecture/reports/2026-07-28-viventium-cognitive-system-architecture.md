# Viventium Cognitive System Architecture — QA Run

**Date:** 2026-07-28

**Status:** superseded by `qa/cognitive-architecture/v0.5/`; retained as historical evidence for the
earlier Draw.io attempt.

**Scope:** Proposed future-architecture document, rendered SVG, and editable Draw.io source.

**Overall:** PASS for design-review readiness and rendered-diagram quality. PARTIAL only for a live
Draw.io-editor import.

## Results

| Case | Status | Actual evidence | Remaining gap |
|---|---|---|---|
| VCA-001 | PASS | Diagram and document connect sources/current stores, federated Life, the minimal Cognitive Control Plane, agent bodies, experience surfaces, and Sleep Growth | None for documentation scope |
| VCA-002 | PASS | Life covers cross-domain canon, bounded-store authority, privacy, provenance, history, projects, people, communications, decisions, views, correction, forgetting, and selective chat-time access | Exact schemas and onboarding remain intentionally unapproved |
| VCA-003 | PASS | Existing GlassHive events, callbacks, artifacts, evidence, steering, and continuation are credited; new scope is cross-turn mission identity, lineage, a sanitized Evidence Digest, an exceptional question event, and receipt deltas/risks | Runtime contract is future work |
| VCA-004 | PASS | Vocabulary matches canonical Activation Detection, Phase A, cortex execution, and Phase B. Every cortex is Feeling-free and peer-independent until its first pass is sealed; the Main Agent remains the adjudicator | Post-independence deliberation access control is a future gated design |
| VCA-005 | PASS | Agent bodies retain native models, auth, tools, browsers, computers, sandboxes, and connectors | None for documentation scope |
| VCA-006 | PASS | Header disclaims authority; components are labelled CURRENT, PROPOSED, or MIXED; plane colors are explicitly functional. Mission Envelope is proposed/dashed while the existing return leg is current/solid | None |
| VCA-007 | PASS | Both diagram artifacts are well-formed XML and contain matching core status/architecture labels | None |
| VCA-008 | PASS | The revised SVG was rendered in real Chromium at 1800×1120. Full-canvas visual inspection found all panels, labels, arrows, status markings, stores, and the Sleep Growth sequence visible without clipping | Smaller direct-SVG viewports require browser zoom or responsive host-page scaling |
| VCA-009 | PARTIAL | Draw.io source contains editable mxGraph cells, geometry, styles, and edges and passes XML validation | Draw.io Desktop is not installed; the online editor's native file picker could not be retained by the headless automation, so a successful editor import remains unproven |
| VCA-010 | PASS | Automated and manual scans found no personal corpus content, credentials, email, home-directory path, localhost URL, or machine identity in public deliverables | Repeat before a public commit |
| VCA-011 | PASS | All repo-relative document and asset links resolve after the vision rename | External publishers may move official links later |
| VCA-012 | PASS | Life is authoritative only for accepted Life artifacts; chat, saved memory, recall, App Support, Workbench/Periphery, and GlassHive retain bounded authority and are visible in the diagram | Final projection schemas are future work |
| VCA-013 | PASS | The Control Plane may own only policy/state that must survive both an agent-body and an experience-surface change; host-ownable work remains host-owned | Apply this test to every proposed implementation slice |

## Independent challenge and correction loop

An independent Claude Opus 5 Extra review first returned **PROMISING BUT NEEDS REVISION**. It found
four material errors: Phase A/B had been relabelled incorrectly, the all-cortex Feeling-independence
rule had been weakened, the blackboard did not preserve first-pass epistemic independence, and the
diagram's implementation-status legend was misleading. It also showed that the first GlassHive
draft understated substantial current return-leg capability.

The proposal and both diagram artifacts were corrected. The same reviewer then read the live files,
reported **APPROVE FOR PRODUCT-OWNER REVIEW**, found no remaining blocking issues, and confirmed that its
P0 findings and requested corrections were resolved or explicitly bounded. It made no file changes.
Residual choices such as the physical `Life/` location, post-independence deliberation mechanism,
first native cortex host, “Operating System” positioning, and Mind Pack naming remain correctly
deferred to the product owner.

## What was actually run

- XML well-formedness validation for Draw.io and SVG.
- Required-label parity across Draw.io and SVG.
- Repo-relative target existence checks.
- Public-safety and text-hygiene scans across all public deliverables.
- Real Chromium rendering at the diagram's native 1800×1120 size.
- Full visual inspection after the adversarial corrections.
- Two-pass independent review: initial challenge, correction, and live-file approval recheck.
- Official external design references independently rechecked on 2026-07-28.

## What was not run

- No runtime or implementation QA was run because this is a proposed target architecture, not a
  shipped feature.
- A successful live Draw.io-editor import was not proven and remains PARTIAL.
- No private Life content was copied, rendered, or placed in public evidence.

## Acceptance wording

The proposal and rendered architecture are ready for product-owner design review. The editable source is
structurally valid Draw.io XML, but editor import must not be described as proven until it is opened
in a supported Draw.io surface.
