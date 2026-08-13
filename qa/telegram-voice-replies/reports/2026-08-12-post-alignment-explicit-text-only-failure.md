# Post-Alignment Telegram Explicit Text-Only QA Run - 2026-08-12

## Summary

- Result: FAIL
- Build/source under test: isolated clean parent candidate with merged LibreChat capability policy
- Runtime/artifact under test: installed local-prod immutable Telegram component
- Environment: real Telegram Desktop against local Viventium
- Tester: Codex using macOS desktop QA
- Related change: post-alignment Telegram regression verification

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TGVOICE-UC-007` | FAIL | visible Telegram result, Mongo final state, voice gate, prompt-frame telemetry | Text succeeded; forbidden audio was delivered. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: model-owned optional Telegram audio
- Requirement: explicit text-only/no-audio choice suppresses optional audio
- Use case: send one short text-only request while Smart voice is enabled
- QA case: `TGVOICE-UC-007`
- Expected result: one clean text answer and no audio attachment
- Actual evidence: one completed sentence plus one two-second audio attachment
- Remaining gap or fix: make explicit per-turn delivery choice reliable through structured policy without keyword routing

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | Telegram voice gate, shared delivery-control parser, and surface-prompt assembly reviewed. |
| Docs and nested docs/repos | Telegram bridge requirement and voice-reply case reviewed. |
| Scripts or harnesses | Desktop send/capture and sanitized Mongo turn query ran. |
| Local/external prerequisite state | API, Telegram bot, GlassHive, and xAI TTS were available. |
| Logs, DB/state/persistence | Message finalized cleanly; voice gate logged send with no model skip. |
| Generated/shipped artifact | Runtime prompt bundle and immutable Telegram component matched the candidate. |
| Real user path | Real Telegram Desktop send/receive and visible audio attachment. |
| Not run / blocked | Connected-account content and audible semantic scoring were not needed for this binary suppression case. |

Supporting evidence cannot replace required user-path evidence; the real Telegram Desktop path was run.

## User-Grade Evidence

- Surface exercised: Telegram Desktop, local Telegram bot, and Viventium Main
- Real user path: sent a synthetic one-sentence request with an explicit text-only/no-audio choice
- Visible outcome: correct short text arrived, followed by a forbidden two-second audio attachment
- Expanded/detail state: the open chat showed the text and audio as separate delivered items
- Persistence/reload result: Mongo stored one finished non-error assistant answer; a Telegram restart was not run for this case
- Local/external prerequisite state: aligned API and bot were healthy; TTS was available
- Backend/log/DB confirmation: always-voice was enabled, audio send occurred, and no skip control was requested
- Final model/runtime wording check: answer text was concise; delivery format contradicted the user's request
- Substitution check: logs, DB, prompt telemetry, and source support the visible failure; they do not replace it

## Automated Evidence

```bash
cd viventium_v0_4/telegram-viventium
uv run --project TelegramVivBot --with pytest python -m pytest tests/test_voice_preferences.py tests/test_bot_stream_preview.py -q
```

## Findings

- Defects: active model omitted the hidden skip control despite the current surface prompt.
- Regressions: explicit text-only acceptance is currently failing.
- Flakes: one real run is sufficient to reject the release claim; repeatability remains to be measured.
- Environment issues: none caused this result.
- Residual risks: runtime keyword matching or silently changing the saved voice preference would violate product architecture.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
