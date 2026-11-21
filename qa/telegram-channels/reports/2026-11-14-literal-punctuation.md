# Telegram literal punctuation, 14 November 2026

## Summary

QA: blast-radius. Local development, not a release certificate. Requirement: TGFORMAT-001,
[Markdown formatting integrity](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md#markdown-formatting-integrity).

Telegram rewrote em dashes after Main generated its answer. That enforced the default prose preference by
changing exact quotations and explicit overrides. The reviewed private `main.voice_style` v2 applied that preference and its
exceptions. The public contract applies saved preferences without imposing an operator default. The adapter now preserves punctuation; citation, tool-transcript and voice-control cleanup
retain their existing contracts. The same sanitizer serves previews, scheduled text and later follow-ups.

## Scope Run

| Check | Actual result |
| --- | --- |
| Exact-punctuation regression, original adapter | Eight failures reproduced |
| Complete bridge regression bank | 537 passed |
| Retained exact-model outputs, configured primary and fallback, six cases each | 8/12 through the former adapter; 12/12 through the repaired text, preview and follow-up paths |
| Source to installed component | Canonical assembler built the repaired component with the existing dependency set. The active local checkout was restarted; its running source and assembled bridge bytes match. Identity is recorded privately |
| Native Telegram UI | BLOCKED: unavailable during this run; source, tests and runtime identity do not substitute for this gate |

The model comparisons reuse valid sanitized outputs from the earlier same-day prompt repair; no new model
score gain is claimed. The deterministic transport correction accounts for the changed literal-text result.
Raw prompts, responses, runtime paths and operator evidence remain private. User model, tools, effort,
accounts and saved preferences are protected. No commit, pin change or public release is claimed.


## Traceability

TGFORMAT-001 links the literal-source and explicit-override cases to the Telegram sanitizer, stream
preview and follow-up readers. The table records the historical transport result, not approval of
later public prompt bytes.

## Full-View Evidence Checklist

| Evidence surface | Actual evidence and limit |
| --- | --- |
| Owning docs and code | Markdown formatting owner above; punctuation rewrite removed from the shared sanitizer. |
| Tests, logs and artifact | Eight causal failures, complete bridge bank and captured component/source parity; raw proof private. |
| State and user path | Active component identity was checked; native Telegram UI was unavailable. No UI/reload result is inferred. |

## User-Grade Evidence

- Surface exercised: Telegram adapter and generated component; native Telegram UI unavailable.
- Real user path: Literal quote, current override, preview and follow-up text; actual native UI journey BLOCKED.
- Visible outcome: NOT RUN on the native UI; transport outputs retained exact punctuation in the supporting checks.
- Expanded/detail state: NOT RUN because native Telegram UI was unavailable.
- Persistence/reload result: Component/source parity checked; actual chat reload was NOT RUN.
- Backend/log/DB confirmation: Shared sanitizer regressions and captured running component identity; no private rows published.
- Final model/runtime wording check: Retained model outputs isolate the adapter correction; no new inference quality gain or changed public prompt acceptance claimed.
- Substitution check: Source, tests and runtime identity do not substitute for native Telegram UI, detail, reload or delivery evidence.

## Automated Evidence

The historical selected check counts and causal comparison appear in Scope Run. This publication
retains those results as supporting evidence for their original candidate only.

## Findings

The transport rewrite changed literal sources. Removing it corrected the selected deterministic
paths. Native Telegram UI acceptance remained blocked; later public communication policy needs its
own current model and user-path evidence.

## Public-Safety Review

- [x] No private prompts, model replies, conversations, account data or screenshots.
- [x] No credentials, private URLs, machine paths or runtime identifiers.
- [x] Sanitized historical outcomes and explicit current-candidate limits only.
