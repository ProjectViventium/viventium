# Post-Alignment Telegram Explicit Text-Only QA — 2026-08-12

## Outcome

FAIL for explicit per-turn audio suppression; PASS for aligned Main initialization, text delivery,
and persistence. This is a current behavior gap, not stale-source drift.

## Real User Path And Evidence

- Sent one synthetic Telegram text request for exactly one short confirmation sentence and
  explicitly requested text only with no audio.
- Telegram visibly received one short completed sentence in about 16 seconds. Mongo recorded one
  assistant response with `error=false` and `unfinished=false`.
- Telegram also visibly received one two-second audio attachment, which violates the request.
- The voice gate recorded always-voice enabled, `send=1`, and no model-requested skip. Prompt-frame
  telemetry confirmed the current Telegram optional-audio surface prompt was present, and that
  prompt explicitly requires the hidden skip control for text-only/no-audio requests.
- Runtime provenance, exact merged LibreChat pin, generated provider capability policy, and the
  immutable Telegram component were current for the test.

## Judgment

The active model followed the answer-length requirement but omitted its hidden transport control.
Do not repair this with runtime keyword matching or by silently changing the saved voice
preference. The next product fix should preserve model-owned semantic delivery while making the
explicit per-turn delivery choice reliable through structured policy or an equivalent general
mechanism.

No account identifiers, chat IDs, credentials, private prompts, personal content, or local paths
are included in this report.
