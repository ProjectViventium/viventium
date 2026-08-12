# Nested Telegram Markdown Placeholder Rendering QA

**Date:** 2026-07-27

**Case:** `TR-010`, `TELEGRAM-UC-009`

**Overall result:** PASS for the fixed source, shared delivery paths, Telegram Bot API acceptance,
and native Telegram rendering. PARTIAL for the installed-runtime path because transactional
activation stopped at its free-disk doctor gate before replacing or restarting the running bridge.

## Requirement And User Outcome

A main answer or follow-up can contain supported Markdown emphasis inside a block quote. Telegram
must display the original words with the intended emphasis. Internal renderer placeholders such as
`PH0`, `PH2`, or NUL-delimited variants must never become user-visible text.

## Root Cause And Fix

The shared Markdown-to-Telegram-HTML renderer protects converted fragments with internal
placeholders. Emphasis was stored first, then the surrounding block quote was stored as a later
placeholder containing the earlier token. Restoration ran in insertion order, so it attempted to
restore the inner token before the outer quote had reintroduced that token. Telegram then received
the residual placeholder and displayed its readable `PH<number>` portion.

The renderer now restores placeholders in reverse insertion order. This expands the later outer
wrapper first and then resolves the earlier inner fragments. The change is shared by main streamed
answers and proactive/background follow-ups; it does not branch on prompt text, agent names,
provider labels, or user identity. HTML escaping and parse-mode fallback behavior are unchanged.
The renderer performs the same number of placeholder replacements with the same asymptotic cost;
reversing the dictionary view adds no extra rendering pass or external dependency.

## Evidence

| Check | Actual result | Status |
| --- | --- | --- |
| Test-first reproduction | The new pure-renderer regression failed before the fix with NUL-delimited `PH0` and `PH1` inside the quote. | PASS |
| Focused formatter and delivery regressions | Pure renderer, main streamed reply, and follow-up path: `3 passed`. | PASS |
| Affected Telegram test files | `154 passed`. | PASS |
| Full Telegram bridge suite | `349 passed`. | PASS |
| Relevant parent release contracts | `18 passed`. | PASS |
| Browser visual QA | A headed Playwright run showed bold text inside a Telegram-style quote, the expected source words, no placeholder, and no console error. | PASS |
| Real Bot API delivery | A synthetic fixed-source payload was accepted by the real Telegram Bot API; the rendered payload contained no placeholder. | PASS |
| Native Telegram Desktop inspection | The delivered bubble visibly showed its title and quote emphasis, with the full source words and no `PH<number>` or raw HTML. | PASS |
| Quality and performance review | Source words, emphasis, and shared-path alignment are preserved; replacement count, complexity, and dependency footprint are unchanged. | PASS |
| Installed-runtime source alignment | The identical fix was applied and locally verified in the supported active checkout. Its source hash matches the fixed development source. | PASS |
| Transactional activation | The supported validated restart stopped safely because the target volume had 4.2 GiB free while the doctor requires at least 6.0 GiB. It reported that binding, live runtime, helper, and running state were unchanged. | BLOCKED |
| Running artifact alignment | Post-attempt status shows the Telegram bridge still running, but its content-addressed artifact does not yet match the fixed source, as expected after the pre-restart refusal. | PARTIAL |
| Claude review-only pass | Claude Desktop reported no remaining usage credits, so the requested review-only second opinion was unavailable and was not substituted with another model. | BLOCKED |

The native Telegram screenshot was not retained in this public repository because the surrounding
desktop view contained unrelated private conversation context. The inspected acceptance result
above uses only synthetic, non-personal message content.

## Natural User Use Cases

| Use case | Result | Evidence or boundary |
| --- | --- | --- |
| Main answer contains bold text inside a quote | PASS | Main streamed-reply regression plus real Telegram delivery and native visual inspection |
| Background/proactive follow-up contains nested emphasis | PASS | Shared follow-up regression verifies Telegram HTML parse mode, the source words, and no placeholder |
| Multiple emphasized fragments precede and occur inside a quote | PASS | Pure-renderer regression and screenshot-shaped main-path fixture |
| Visible UI detail state | PASS | Telegram Desktop showed the formatted quote bubble; no raw tag or placeholder was visible |
| Browser visual parity | PASS | Headed Playwright inspection with the real expected renderer output |
| Refresh or persistence | N/A | Message formatting is resolved before send; the delivered Telegram message remained visible in native history |
| Missing auth or degraded Bot API | N/A | The renderer is local and stateless; the configured real API accepted this synthetic acceptance message |
| Retry, interruption, or cancellation | N/A | The defect is deterministic text conversion and does not change delivery lifecycle controls |
| Installed bridge receives a normal generated turn after deployment | PARTIAL | Not run because the transactional activation failed safely at the free-disk doctor gate before restart |

## Commands Run

```text
python -m pytest tests/test_telegram_html.py::test_markdown_to_html_resolves_nested_formatting_inside_blockquotes -q
python -m pytest tests/test_telegram_html.py::test_markdown_to_html_resolves_nested_formatting_inside_blockquotes tests/test_bot_stream_preview.py::test_get_viventium_response_resolves_nested_blockquote_formatting tests/test_librechat_bridge.py::test_followup_text_resolves_nested_blockquote_formatting -q
python -m pytest tests/test_telegram_html.py tests/test_bot_stream_preview.py tests/test_librechat_bridge.py -q
python -m pytest -q
python -m pytest tests/release/test_telegram_codex_runtime_paths.py tests/release/test_telegram_lazy_startup_contract.py tests/release/test_delivery_controls_contract.py tests/release/test_telegram_media_prereqs.py tests/release/test_telegram_transcription_error_contract.py tests/release/test_qa_results_public_safety.py -q
```

The first focused invocation was the intentional red test before implementation. Post-fix runs
produced the passing counts recorded above.

## Remaining Installed-Runtime Gate

To close the installed-runtime result, free at least 1.8 GiB so the machine meets the 6.0 GiB doctor
minimum, then rerun the supported local activation:

```text
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder --allow-dirty-local-testing
```

After restart, verify the running source hash and send a normal synthetic prompt whose generated
answer contains emphasis inside a block quote. Confirm the delivered bubble, bridge logs, and active
artifact agree. Until that gate passes, this report does not claim that the currently running bridge
contains the fix.
