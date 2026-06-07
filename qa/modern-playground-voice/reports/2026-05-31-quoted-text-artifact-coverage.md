<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Quoted Text Artifact Coverage

## Scope

This pass hardens the cumulative-delta artifact fix against a false-positive class: meaningful
repetition inside quoted, blockquoted, or code-formatted text.

Public-safe note: recent generated text was sampled only as aggregate shape statistics. No raw
message text, user ids, conversation ids, call ids, account identifiers, local paths, or secrets are
copied here.

## Sanitized 30-Day Shape Sample

The local message store was sampled for assistant-generated messages from the last 30 days using
counts only.

```text
assistant_messages_checked=1089
quote_like_messages=176
straight_double_quote_messages=124
curly_double_quote_messages=19
curly_single_quote_messages=44
markdown_blockquote_messages=6
markdown_code_messages=39
multi_line_messages=656
internal_no_response_marker_shape=38
adjacent_duplicate_word_shape=13
adjacent_duplicate_inside_double_quotes=0
adjacent_duplicate_outside_double_quotes=13
joined_duplicate_word_shape=6
long_quoted_span_messages=9
```

Interpretation: quote-like generated text is common enough that duplicate-artifact checks must not
blindly collapse repeated words inside protected quote/code spans. The observed duplicate-word shapes
in this sample were outside double quotes, which matches the escaped stream-artifact class.

## Changes

- Historical voice read repair now counts and rewrites duplicate artifacts only outside protected
  spans:
  - straight double quotes
  - curly double quotes
  - curly single quotes
  - markdown blockquotes
  - inline code
  - fenced code
- The browser artifact harness now uses the same protected-span idea for adjacent duplicate-word
  detection, so a synthetic or real answer that quotes repeated words does not fail QA merely for
  preserving the quote.
- Added a reusable text-level harness regression script for protected-span artifact detection.
- Added cumulative stream tests where quoted repetition arrives as growing snapshots.

## Verification

```text
node -c qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs
node -c qa/modern-playground-voice/scripts/tts_artifact_text_regression.cjs
node qa/modern-playground-voice/scripts/tts_artifact_text_regression.cjs
node -c viventium_v0_4/LibreChat/api/server/services/viventium/historicalVoiceTextRepair.js
cd viventium_v0_4/LibreChat && npm run test:api -- --runTestsByPath api/server/services/viventium/__tests__/historicalVoiceTextRepair.spec.js api/server/services/viventium/__tests__/voiceDeltaAggregation.spec.js
cd viventium_v0_4/voice-gateway && .venv/bin/python -m pytest tests/test_librechat_llm.py -q
```

Result:

- Text artifact harness regression: PASS
- LibreChat quote/cumulative suites: PASS, 19 tests
- Voice gateway stream tests: PASS, 59 tests

## Remaining Boundaries

- Exact internal no-response markers such as `{NTA}` are still forbidden user-visible artifacts even
  near prose. This pass does not make internal control tags safe to display.
- Single-quote ASCII spans are not treated as protected quote ranges because apostrophes in ordinary
  English contractions make that ambiguous. Curly single quotes are protected.
- Historical read repair remains a read-side safety net; it does not mutate old Mongo rows.
