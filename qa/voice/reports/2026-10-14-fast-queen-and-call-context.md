# Fast Queen and optional Call context — local candidate

<!-- qa-evidence-exempt: Historical experiment and benchmark record, with explicit failed and unrun boundaries; it is not a current full acceptance report. Current Voice cases own completion. -->

QA: blast-radius. Development evidence only; no publication claim.

Requirements: [VOICE-PREP-001](../../../docs/requirements_and_learnings/06_Voice_Calls.md#optional-preparation-for-fast-conversation), CORE-005, CC-049, CORE-015.
Journey: `optional-call-context-preparation` in [Voice cases](../cases.yaml).

## Delivered contract and evidence

| Requested behavior | Actual evidence | Limit |
| --- | --- | --- |
| Explicit GPT-6.1 Sol Low / Fast option | Native per-turn priority projection, capability-based Speed control, browser selection/save, three attempted real RTC turns per Sol setting | Serving tier NOT OBSERVED; Fast Low had one correct answer and two rate failures |
| Stream eligible speech before final completion | Native Codex final-answer deltas use the existing public envelope parser; focused producer/consumer checks and real RTC speech | Commentary, unknown phase, skipped audio and incomplete control envelopes do not speak |
| Call starts normal Main preparation in the same thread | Existing scheduler admission, registered Workbench v1 prompt, canonical conversation binding; existing-thread and new-thread real Call cases | Native scheduler and Voice session lanes remain distinct; no provider cache transfer claim |
| Visible report and progress, silent audio | Real Chrome displayed Waking up - gathering context, a saved report; no active received PCM during report-only preparation | This is the existing activity surface, not a new front end |
| Early input and normal Voice route | Correct early answer once, then a correct following answer in both existing and new conversations | First answer includes preparation wait; not a speed win |
| Exact Stop, Listen-Only and deadline recovery | Real Chrome showed confirmed cancellation; a real new-call deadline preserved its reason, exact release receipt and subsequent correct Voice answer | Crash between native abort and failed receipt persistence stays fail-closed; End/new Call recovers |
| Keep all normal tools/cognition and defaults | Source and admitted native lineage retain Main tools, files, memory, Feelings and cortex paths; final configuration matches original Main/Voice fields | This is not full semantic parity or arbitrary-action acceptance |
| Settings persist without losing history | Normal Chrome Medium → High Save, reload and full Version view; all 502 prior version hashes preserved and 504 versions visible | Old-version restore was tested with real synthetic Mongo, not performed on the owner's historical configuration |

## Actual useful speech measurements

Seconds from physical end of synthetic input to first received active response PCM. Error narration
does not count as a useful reply. Native effort was confirmed. Small samples are not p95 or reliability proof.

| Voice setting | Correct answers / attempts | Seconds |
| --- | --- | --- |
| Grok 4.7 Fast High, baseline | 1 / 1 | 13.882 |
| Grok 4.7 Fast High, final loaded fresh call | 1 / 1 | 24.025 |
| GPT-6.1 Sol Low Fast | 1 / 3 | 10.550 |
| GPT-6.1 Sol High Fast | 1 / 3 | 14.107 |
| GPT-6.1 Sol Low Standard | 3 / 3 | 12.326, 8.136, 10.756 |
| GPT-6.1 Sol High Standard | 1 / 3 | 14.026 |
| Grok 4.7 Fast Low, arithmetic | 3 / 3 | 11.405, 8.720, 6.135 |

Six Sol turns failed with native HTTP 429. Configured Opus fallback could not execute because CLI
authentication was unavailable. Native usage allowed ordinary requests; the precise rate-limit
cause is not established. Supported alternatives stay selectable; OpenCode is unchanged.

The fastest useful Low turn still spent 2.693 seconds before its native prompt and 0.622 seconds
from first raw answer to received speech. Its native TTFT was 1.721 seconds, which includes reasoning.
Cache hits and conversation size changed across turns. The final High call spent 3.791 seconds
before its prompt, 19.801 seconds until its first raw answer and 0.433 seconds to received speech.
**Sub-two-second speech is not achieved.**

Low's first worker-action case promised a launch but made no native tool call. A repeat did return
an accepted worker receipt, but STT changed the requested shape to shade. A requested High control
remained Low because a settings save failed at the Mongo document limit; that run is excluded from
High comparisons. Low remains an explicit experiment, not an approved replacement default.

Preparation saved a correct file-context report in 35.955 seconds. An early answer took 53.010
seconds including the wait; the next took 14.728 seconds. A fresh-thread early answer took 68.668
seconds, then 13.916 seconds. Preparation is a context-quality option, OFF by default, not a proved
latency optimization. An OFF run used standard Grok rather than Fast and is excluded from a paired comparison.

## Verification and review

Focused native streaming/tier/parser, typed 429, stage observability, preparation producer/consumer,
gateway, compiler and UI checks passed. History capacity repair has 21 focused checks, including
six real synthetic Mongo replica-set checks for overflow, full hash preservation, subsequent save,
indexed revert, rollback, transaction unavailability and stale publication. No historical snapshot
was pruned. Data-provider, data-schemas, API and front end builds passed; unrelated existing API
type diagnostics remain, so a clean whole-project type check is not claimed.

Existing Opus 5.5 review challenged source, controlling requirements and actual receipts. Material
findings on input lifetime, admission budget, cancellation/deadline truth, durable exact release and
archived deletion consumers were repaired and checked. The current-laptop supported runtime loaded
the candidate. Source and compiled preparation prompt hashes match; generated Core/native config
agree on OFF and 120 seconds. Final native Voice ran Grok 4.7 Fast High and ended normally.


### Paired preparation-source evaluation

The canonical Workbench bank links three positive, negative and adjacent cases to
`voice.prebuild_context`. Exact frozen provisional and revised prompt sources ran on the same
three sanitized inputs through the existing scheduler Main HTTP/SSE owner: six saved completions,
all GPT-6.1 Sol High with no fallback. The provisional draft had a trailing compatibility marker;
the final prompt uses structural silence. Opus reviewed the outputs against the rubrics: verified
facts stayed separate from pending work, missing facts were not invented, and conflicting notes
had no fabricated winner. The final outputs removed the visible marker. This is no regression
plus a removed defect, not proof of increased intelligence or reliability.

These are paired registered-source replays, not a Workbench EvalResults UI run. The Workbench
no-live selection preview resolved all three linked cases and is not counted as model execution.
The cases limit their synthetic reports to 100 words and supplied scenario evidence; production
preparation has no such word limit. Broad awareness gathered from real memory, work state,
computer/browser sessions and workers remains unevaluated. The real gathering case read one
fictional file. Preparation retains those capabilities, but retained access is not proof of their
quality across all use cases. Compare speed options against the observed default High spread
of 13.882–24.025 seconds across the two checks, not one chosen baseline.

## Remaining evidence gates

- NOT RUN: full always-on acceptance, real Telegram call launch, arbitrary approval and reconnect
  combinations, listening through every output for perceptual glitches, and full original feature parity.
- NOT RUN: alternate local STT/TTS or direct-LLM latency comparisons; neither is required to prove
  the two opt-in options above.
- BLOCKED: actual Opus fallback execution until its configured CLI authentication works. Desktop
  review uses a separate signed-in connection.
- NOT OBSERVED: actual served Fast tier. Ultrafast is not advertised by the installed native catalog.
- Follow-up optimization hypotheses: native per-call readiness and measured Core admission. These
  require lifecycle/identity proof and an isolated experiment; neither is delivered or claimed here.

Raw owner prompts, screenshots, stable IDs, logs, audio and source hash manifests remain private.
