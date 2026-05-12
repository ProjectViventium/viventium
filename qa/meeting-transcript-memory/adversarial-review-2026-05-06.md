# Meeting Transcript Memory Adversarial Review - 2026-05-06

## Scope

Review-only audit of the meeting-transcript memory/RAG implementation against:

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/20_Memory_System.md`
- `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `AGENTS.md`

Inputs were sanitized before second-opinion review. No credentials, raw transcript text, personal
emails, local home paths, or private folder names are included here.

## Verdict

Not release-ready yet.

The implementation is structurally closer to the intended design than the prior pass: transcript
content is not parsed deterministically for people, intent, commitments, or topics; transcript RAG
attachment is vector-runtime gated; transcript artifacts are source-folder-hash scoped; and the
mixed recall/transcript ranking no longer contains a blanket transcript-first override.

The review still found blockers and residual risks.

## Confirmed Strengths

- Transcript files are passed through as untrusted evidence envelopes.
- Default RAG mode stores detailed summaries, not raw transcript dumps.
- Transcript-derived stable memory writes require corroboration gates.
- Runtime attachment checks current source-folder hash and vector runtime health.
- Public QA/docs/tests scanned clean for the searched private identifiers.

## Findings

1. **Blocker: nested component is not shipped.**

   `components.lock.json` still points at the current nested LibreChat `HEAD`, but the transcript
   implementation is dirty/untracked inside the nested LibreChat repo. A clean checkout from the
   parent pin will not reproduce the feature. This violates the shipped-artifact and component-pin
   discipline in the key principles.

   Required proof: commit the nested LibreChat changes, update the parent component pin, rebuild
   shipped artifacts, and prove a fresh install/upgrade runs the transcript path.

2. **Fixed during this review: oversized transcript handling contradicted the docs.**

   The docs promised explicit truncation, but the scanner previously terminally skipped text files
   over the byte guardrail. The scanner now bounded-reads oversized text inputs, preserves head/tail
   evidence with explicit truncation markers, and skips only non-text/binary inputs.

   Regression proof: backend hardener tests now assert oversized text is fed to the model with a
   truncation marker.

3. **Residual risk: assistant no-access/no-memory downranking is text-pattern based.**

   This is not transcript-content parsing and not a tool-activation gate, but it is still brittle
   because paraphrased assistant disclaimers can miss the downranker. Longer-term fix should prefer
   stronger structural corpus filtering or a better low-information classifier with broad fixtures.

4. **Residual risk: natural recall is proven locally, but fresh-install release proof is not.**

   A browser QA run with a normal user question attached both conversation recall and meeting
   transcript summary sources and answered from the transcript summary without stable-identity
   promotion. That proves the local running path. It does not prove a clean install from the pinned
   component ref.

5. **Residual risk: transcript folder sidecars.**

   Text operational sidecars inside the configured transcript folder are treated as transcript
   candidates by design. That is aligned with pass-through ingestion but operationally risky.
   Downloader state should live outside the transcript folder, or the product should add explicit
   configurable ignore rules for known operational sidecars.

## Evidence Matrix

Proven locally:

- Backend transcript/recall tests passed.
- Package API meeting-transcript tests passed.
- Release/helper contract tests passed.
- Eval harness passed.
- Package API `dist` was rebuilt locally and contains the transcript runtime hooks.
- Browser QA attached a meeting summary source for a normal transcript recall question.

Partially proven:

- Status-bar helper menu behavior. Source/binary/string checks and prior native QA exist, but the
  latest post-review state does not include a durable screenshot artifact in this public QA folder.
- Natural recall behavior. Proven locally after synthetic QA ingestion, but not through a clean
  install from the parent component pin.

Contradicted:

- Release readiness from the current parent `components.lock.json` pin.

## Required Before Release

1. Commit and pin the nested LibreChat component changes.
2. Rebuild shipped artifacts from that pinned component.
3. Run clean install/upgrade QA from public entrypoints.
4. Add or run a release gate proving the pinned LibreChat tree contains the transcript runtime files.
5. Decide whether transcript-folder sidecar ignore rules are needed or document the folder as
   transcript-artifacts-only.
