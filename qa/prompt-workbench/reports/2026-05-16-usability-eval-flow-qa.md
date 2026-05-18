<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Workbench Usability And Eval Flow QA - 2026-05-16

## Scope

Validated the Prompt Workbench user flow for prompt draft review, eval visibility, eval case
creation, eval preview, push dry-run, and Prompt Traces. This pass was local-only: no reviewed live
push, no cloud push, and no live model eval call.

## Expected Behavior Checked

- Prompt and eval edits create reviewed drafts before source files change.
- Pending drafts block eval preview and push dry-run because those actions use applied source only.
- Stale already-applied drafts can be resolved without rewriting source.
- Formatting-only eval drafts are refused.
- Evals default to all cases linked to the selected prompt.
- New eval cases are saved as `eval-edit` drafts and can be discarded without changing the eval
  bank.
- No-live eval previews are clearly labeled as selection previews, not scored model performance.
- Push dry-run surfaces a visible outcome and unlocks reviewed push without performing the reviewed
  push.
- Prompt Traces explains that it is local prompt-run metadata, not raw prompt text or eval
  performance.

## Browser QA

Tooling:

- Real Google Chrome through Playwright `channel=chrome`, headed browser.
- Public-safe screenshots were captured to a temporary local evidence folder outside the repo.

Scenarios:

1. Selected `main.voice_style` from the Prompt Atlas.
2. Opened `Evals` and confirmed the default table shows all five linked Voice Style cases across
   families/surfaces.
3. Created a synthetic non-private eval case draft from the UI.
4. Confirmed the new draft was `eval-edit`, then discarded it.
5. Confirmed active drafts returned to `0`.
6. Ran `Run eval preview` for `main.voice_style`.
7. Confirmed latest run `20260516T181321Z` is `synthetic-no-live-preview`, prompt id
   `main.voice_style`, one selected case, no model score.
8. Confirmed the latest run is visible in the Eval Results list for Voice Style.
9. Clicked `Push dry-run` and confirmed the visible outcome:
   `Dry run finished. Reviewed push is unlocked after you inspect the diff.`
10. Opened `Prompt Traces` and confirmed explanatory copy is visible.

Observed and fixed during this pass:

- The `New eval case` action could visually appear clickable while a trusted browser click froze
  during the create-mode transition. The UI now defers that transition by one tick so the browser
  completes the click/focus cycle first.
- New eval-case create fields froze on real keyboard/fill input when controlled through React
  state. Create-mode fields are now uncontrolled and read on save, while existing eval edits remain
  controlled.
- A review-only Claude pass found that the exact-model eval adapter passed `--prompt-bank` in the
  wrong argv shape for the canonical runner. The adapter now uses `--prompt-bank=<path>` and has a
  regression test.

## Automated Checks

- `npm run build` in the Prompt Workbench app: passed.
- `python -m pytest tests/release/test_prompt_workbench.py -q`: passed, 39 tests.

## Safety

- No reviewed live push was run.
- No live exact-model eval was run.
- The synthetic eval draft was discarded.
- Active workbench drafts ended at `0`.
- Public QA evidence does not include raw private prompts, transcripts, local home-directory paths,
  or temp screenshot paths.
