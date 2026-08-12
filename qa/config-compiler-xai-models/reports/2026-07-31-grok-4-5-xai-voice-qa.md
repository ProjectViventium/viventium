# Grok 4.5 and xAI Voice QA — 2026-07-31

## Outcome

PASS for the requested live route. Viventium now uses the new restricted xAI credential for Grok
4.5 chat and xAI voice. The credential remains in macOS Keychain and is not recorded here.

## What Was Run

- Created one xAI team key restricted to Chat models and the Chat and Voice endpoints.
- Stored the credential under the existing Viventium Keychain references for xAI LLM and voice.
- Compiled the active runtime and verified both generated xAI values exactly match their Keychain
  sources without printing either value.
- Verified Grok 4.5 directly against xAI Chat Completions. The model rejected
  `reasoning_effort=none`; the supported `low` setting returned HTTP 200 with the expected synthetic
  response.
- Verified xAI TTS directly with synthetic text. The endpoint returned HTTP 200 and a valid 24 kHz
  mono MP3.
- Restarted the active local runtime and verified API, web, playground, and voice-gateway health.
- Ran a real headless-browser Modern Playground call with synthetic text. The page opened, the call
  started, the prompt sent, the assistant transcript became visible, and the answer persisted.
  Runtime evidence recorded `provider=xai` for both the assistant LLM turn and TTS; xAI TTS emitted
  67 characters, 3.76 seconds of audio, and completed without cancellation. Temporary session,
  message, conversation, and call records were removed by the harness.
- Ran the focused compiler/governance suites and the xAI standalone TTS suite.

## Results

| Check | Result |
| --- | --- |
| Restricted xAI Chat + Voice credential | PASS |
| Grok 4.5 with supported low reasoning | PASS |
| xAI voice primary, Sal voice, OpenAI fallback prepared | PASS |
| Compiler and governance tests | PASS — 157/157 |
| xAI standalone TTS tests | PASS — 6/6 |
| Real Playground transcript, persistence, and xAI audio | PASS |
| Main-chat signed-in model-picker selection | NOT RUN — the available local browser profile was not signed into Viventium |

The active browser harness's older semantic-word matcher did not recognize the returned wording,
although its concrete artifact gate passed: visible transcript, one persisted assistant message,
non-cancelled xAI TTS, and zero forbidden visible or persisted artifacts.

## Public-Safety Review

This report contains no credential, team/account identifier, raw call or conversation identifier,
private transcript, local absolute path, hostname, or personal email address.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
