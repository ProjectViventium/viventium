# Direct Queen action handoff — local acceptance

## Summary

QA: critical-path. Status: functional configuration accepted; fast-response goal not met.

## Delivered configuration

The existing xPerfect Direct Grok 4.7 / High option is selected for this installation's Voice
Queen. Main remains Codex GPT 6.1 Sol / High; action workers remain Codex / High with configured
Opus 5.5 / High fallback. Preparation remains off. This is a local configuration choice, not a
new global default. Direct uses the provider API and metered billing.

The existing host-worker default workspace is set to the installation's Life folder. Explicit
roots and previously admitted workspaces keep priority. The normal agent API, canonical config,
compiler and supported runtime restart loaded these changes. No new routing code or prompt patch
was added. Existing user and agent source changes were preserved.

## Scope Run

| Requirement / case | Expected | Observed | Result |
|---|---|---|---|
| `PW-050`, `plain-action-native-execution` | Ordinary action gets a real effect or worker receipt | Original native browser request promised but did not act; a retry used a wrong legacy graph edge. An explicit worker request in the call also produced no action. The configured Codex Chat route performed the same browser action. These are distinct outcomes. | Original native failure retained |
| Native role-policy comparison | A small wording correction makes native Queen delegate small actions | Original delegated 0 of 2 file requests; phrase-only candidate delegated 1 of 2. All four files were created correctly, either by native tools or a worker. | Candidate rejected as insufficient |
| `PW-050`, `PW-052`, `direct-queen-independent-action-handoff` | Plain actions use configured independent workers | Direct High performed five real delegated objectives before promotion: browser success/failure, files, and spoken independent browser + HTML work. Distinct action workers overlapped for about 28 seconds; the following conversational turn was admitted about 3 seconds before the last worker completed. | PASS for tested cases |
| Speech and result delivery | Speech is transcribed; each useful result returns once | Real RTC speech input and received PCM; separate worker results; linked Chat persistence; UI download matched the worker artifact. No raw mission-status speech. | PASS; not hardware-microphone or glitch-free proof |
| Authority / cognition carriers | Preserve configured authority, memory, Feelings and tools | Fourteen Main sections, saved-memory/Feelings content and 23 broker schemas preserved. Worker memory already uses the existing authorized bootstrap. | Carrier checks PASS; no universal cognitive-parity claim |
| Saved configuration after load | Real UI and active execution use the saved choice | Voice settings visibly showed Direct Grok 4.7 High and Opus High backup; actual Queen execution binding matched. Main and worker settings remained unchanged. | PASS |
| New worker workspace | Default placement uses Life | A newly accepted omitted-root Codex High worker's durable runtime admission recorded Life. | PASS |
| Stop / continued work | Stop the Queen without cancelling accepted independent work | Queen run became cancelled while its exact worker continued. The cancelled turn did not answer its pending arithmetic question, as expected for Stop. A fresh conversational turn answered correctly. The completed file was presented once after the worker's queued continuation. | PASS; physical speech barge-in not retested |
| Final actual call | File result persists and can be downloaded | One sent completion, one completed Voice presentation, one linked Chat message, matching downloaded file bytes; test call ended normally. | PASS |

The postload call briefly captured ambient speech before the microphone was muted. That unintended
turn was cancelled. The two cancelled replies remain as unfinished records with stopped UI state;
they are not successful conversational answers. The postload action test used typed input in Call;
the separate earlier RTC test provides the speech-input evidence.

## Timing observations

These are single local observations, not a stable ranking. The Low comparison used disposable
agents; the saved Voice effort remains High.

| Configuration / input | Measured interval | Time |
|---|---|---:|
| Direct High, spoken independent actions | End of injected speech to first received active PCM | 89.657 s |
| Direct High, following spoken arithmetic | End of injected speech to first received active PCM | 37.419 s |
| Direct Low, same spoken action prompt | End of injected speech to first received active PCM | 25.749 s |
| Direct Low, following spoken arithmetic | End of injected speech to first received active PCM | 15.462 s |
| Saved Direct High after restart, typed file action | Gateway dispatch to first TTS byte | 53.055 s |
| Saved Direct High after Stop, typed arithmetic | Gateway dispatch to first TTS byte | 18.468 s |

On the spoken High action turn, the provider first returned text at about 51.8 s; both workers
were accepted at about 56.8 s. The subsequent provider response ended around 88 s. Prompt-cache
hits were already present. These clocks do not isolate provider reasoning from prefill or queue
time. They establish that changing broker wiring or enabling another cache is not a demonstrated
solution to the dominant wait. Sub-two-second response is not achieved.

## Findings

Independent source review and Opus review supported use of the existing Direct option as a
functional handoff remedy and rejected the unproved prompt patch. Direct background context uses
the existing durable Main follow-up when live interjection is unavailable. Native Grok's original
behavior is not repaired by selecting Direct. Configured fallback was preserved, not forced in
this batch. Telegram, unrelated integrations, endurance and hardware audio were not retested.

Life placement uses the existing host-native worker contract: user files go into a task workspace;
per-run harness evidence remains in `glasshive-run/`, which existing artifact discovery excludes.
This directory is internal state, not personal knowledge. The batch does not introduce a new
context indexer or claim that arbitrary recursive Life readers filter it.

Following this repair, the operator reported that the system worked well in actual use. This is
user acceptance of the observed behavior, not a new timing measurement or proof of untested cases.

Raw prompts, identities, runtime paths, screenshots, logs and joined receipts remain private.
This report does not claim full product readiness or universal model reliability.

## Traceability

Voice action handoff → PW-050/PW-052 and CORE-005 → plain browser/file requests and independent
spoken actions → `plain-action-native-execution` and `direct-queen-independent-action-handoff`
in [Voice cases](../cases.yaml) → actual configured workers and once-only useful results → the
observations above. Fast response and unexercised fallback remain open.

## Full-View Evidence Checklist

| Owner / evidence | Observed result |
|---|---|
| Owning docs | Voice capability and parallel-work contracts preserve one Queen, native xPerfect ownership and configured action workers. |
| Code and nested runtime | Existing Direct tool binding, native worker admission, authorized context bootstrap and durable callback path were inspected; no new implementation was needed. |
| Scripts and prerequisites | Existing owner-authenticated call driver injected PCM through the official LiveKit SDK. Configured provider and worker connections executed real requests. |
| Logs, database and state | Exact Queen calls joined to distinct accepted work, worker execution and callback delivery; one sent completion after the postload worker continuation. |
| Generated / active configuration | Narrow agent API update plus canonical workspace setting compiled and loaded through the normal restart. Actual UI selection and execution binding agreed. |
| Real surfaces | Chrome Call and linked Chat displayed the result; normal UI download bytes matched the worker artifact. |
| Limits | Hardware audio, physical barge-in, fallback execution and Telegram were NOT RUN in this batch. |

## User-Grade Evidence

- Surface exercised: Chrome Voice Call, linked Chat, real worker-controlled browser and RTC speech path.
- Real user path: ask for an ordinary action, continue talking while independent work runs, stop an unfinished reply, then receive the completed file.
- Visible outcome: browser action and real files; one useful callback instead of raw mission status.
- Expanded/detail state: saved Voice settings showed Direct Grok High and the configured backup; Chat exposed the downloadable file.
- Persistence/reload result: normal restart retained the saved selection; Call and linked Chat retained the worker result and the call ended normally.
- Backend/log/DB confirmation: distinct accepted work and exact native run bindings joined to durable completion receipts and completed audio presentation.
- Final model/runtime wording check: reported completed work had actual effect or artifact evidence; original false promises remain failed evidence.
- Substitution check: model review and internal receipts support the real surface and RTC observations; they do not replace hardware-audio or untested fallback evidence.

## Automated Evidence

The existing authenticated RTC driver supplied speech and captured received PCM. Read-only joins
checked execution bindings, worker overlap, exact cancellation and callback settlement. Downloaded
bytes were compared with the worker artifact. Compilation and supported runtime startup succeeded.
No new runtime code was added; unrelated suites were not rerun for this configuration repair.
Documentation publication validates the affected case schema, evidence format and links separately.

## Public-Safety Review

- [x] No credentials, private prompts, customer information or personal identities.
- [x] No runtime IDs, raw logs, screenshots, private URLs or absolute machine paths.
- [x] Public evidence contains sanitized observations and measured intervals only; raw joins remain private.
