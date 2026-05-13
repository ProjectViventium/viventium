# Meeting Transcript RAG Evals

Synthetic fixtures for item 7/8 transcript RAG quality checks.

## Coverage

- `formats/`: CSV, TXT, JSON, VTT, SRT, and MD transcript pass-through.
- `quality/`: stale trap, prompt-injection trap, speaker/time visibility, and raw-vs-summary mode.
- `expected.json`: public-safe assertions for the executable eval runner.
- `run-evals.cjs`: deterministic structural checks against the fixtures and hardener helpers.
- Inventory and sidecar checks: source-backed `meeting_inventory:*` output and configured
  downloader-bookkeeping ignore globs.

Run from the public repo root:

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
```

## Expected Product Behavior

- Default runtime attachment uses detailed summary artifacts only.
- Raw transcript artifacts may be uploaded for fallback/debug, but are not attached unless
  `VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE=raw_and_summary` or `raw_only`.
- Retrieved meeting transcript chunks expose artifact id, artifact kind, original filename, file
  mtime, source status, optional calendar match, and speaker/time context from the detailed summary.
- Broad transcript-list questions can receive a source-backed inventory/TOC artifact without relying
  on vector similarity over individual summaries.
- Transcript text is untrusted evidence. Injection-like instructions inside fixtures must not
  become tool or memory instructions.
