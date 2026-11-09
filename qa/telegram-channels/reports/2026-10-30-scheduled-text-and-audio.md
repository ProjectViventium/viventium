# Scheduled text and optional audio — local verification

## Summary

QA mode: **blast-radius**. Candidate: active dirty developer checkout and its locally rebuilt
scheduler/proxy artifacts. No commits, component pins, publication, model remapping, preference
changes, or schedule consolidation were performed. This is local development proof, not a release.

## Scope Run

| Contract and case | Result | Evidence |
| --- | --- | --- |
| Telegram text-first delivery; `scheduled-text-with-optional-audio` | PASS | A paused synthetic Main schedule produced the requested short answer. Telegram Desktop visibly showed readable text followed by one five-second audio attachment. Two separate receipts were confirmed; the presentation acknowledgement retained both. |
| Workbench persistence | PASS | After browser reload, the saved QA schedule showed completed, delivered, and successful LibreChat/Telegram outcomes. The fixture remains paused and cannot recur. |
| Delivery recovery and controls | PASS, automated | Real temporary SQLite receipts covered interruption before audio, replay, unknown audio outcome, missing receipt, explicit rejection, unavailable synthesis, master OFF, model skip, semantic breaks, legacy receipts, a later voice-preference change, and legacy chunk-boundary changes. |
| Native context in Docker | PASS | An isolated Docker client listed tools, listed context, and read a synthetic source through the rebuilt scoped broker and real native context API. The deployed broker matched source. Missing authority returned 403; unrelated paths returned 404. Exact QA containers and networks were removed. |
| Typed model-access diagnosis | PASS, deterministic | Both retained native failure outputs now classify as structured, non-retryable `model_configuration_required`. Synthetic positive, malformed, and non-provider cases passed. Existing failover eligibility stayed unchanged. Historical DB failures were not relabeled. |
| Full nightly completion | BLOCKED | Provider account restrictions, a required reconnect, and exact model access remain separate gates. New GlassHive Workbench QA creation also encounters a pre-existing fallback-effort validation gate; no model or effort was substituted to bypass it. |

## Automated Evidence

Focused checks passed:

- Scheduler dispatch, additive delivery, and storage: **223 passed**, **101 subtests passed**;
  one optional local-MLX dependency test skipped. Live speech used the saved working provider.
- Native worker configuration, provider error classification, context transport, and native
  scheduling: **125 passed**.
- Scoped proxy: **12 passed**. **24** selected Docker boundary/attestation checks also passed.
- The new delivery and encoded-error regressions failed against saved pre-change code.
- One separate context-inheritance test failed identically against the saved baseline; it was not
  changed or counted as passed.

The three voice values survived restart unchanged. Both original continuity schedules remained
active with their retained cadence and conversation policy. Source/installed scheduler equality,
active process ownership, scoped reloads, and rebuilt proxy identity were checked. Raw captures,
IDs, provider details, file hashes, and before/after evidence remain private.

## Findings

An existing Workbench selection issue after creating a schedule required a clean browser reload;
the saved record and completed run then opened normally. No unrelated UI change was made.

The proxy deployment initially selected a stale worker network. The configured base network was
restored before final acceptance, with no active worker jobs. Final boundary attestation reported
an internal network and healthy provider/broker proxies. Parallel Work and Redis remained enabled.
The new runtime transport configuration is client-neutral, and the launcher exports the runtime
port so an offset development instance keeps its own native endpoint.

## Traceability

The [Telegram bridge owner](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md) and [Telegram cases](../cases.yaml) own scheduled-text-with-optional-audio; scheduled and provider-access limits stay explicit.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Telegram Desktop, Workbench in a browser and isolated native Docker context transport.
- Real user path: A paused synthetic schedule delivered readable text and one audio attachment; the saved completed schedule reopened after reload.
- Visible outcome: Telegram showed text before the five-second audio, and Workbench showed delivered outcomes.
- Expanded/detail state: Two presentation receipts, encoded provider failures and scoped context denials were checked; the selection issue required a clean reload.
- Persistence/reload result: The completed schedule remained visible after browser reload, its fixture stayed paused and saved voice values survived restart.
- Backend/log/DB confirmation: SQLite receipts, source/installed scheduler identity and scoped broker transport support the result.
- Final model/runtime wording check: Text/audio delivery passed for the selected occurrence; full nightly completion remained blocked by the recorded access and validation gates.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.
