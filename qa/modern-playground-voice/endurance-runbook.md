# World-Class Call Endurance Runbook

This is the execution contract for MPV-032 through MPV-056. The harness drives an already-running,
already-built Viventium call; it never starts, restarts, upgrades, or modifies the runtime.

## Safety Boundary

- Put the runtime manifest, call URLs, audio fixtures, raw events, logs, screenshots, and process
  samples in a private directory outside this public repository.
- Every browser call URL must use the signed `/call-bootstrap` route. Its 32-byte base64url
  capability stays only in the URL fragment until bootstrap stores it under the exact call-session
  key, then bootstrap must remove the fragment and leave the bootstrap route before any screenshot,
  raw-event entry, result, console summary, or browser capture is recorded.
- Never print or copy a capability or fragment-bearing URL into a result, log, screenshot name, or
  public/private evidence metadata. Persist only its SHA-256 hash, expiry, version `1`, and scope
  `call_browser_v1` in the synthetic call-session record.
- The harness refuses a manifest or output root inside the public checkout.
- Commit only the compact sanitized result schema from `result-template.v1.json`, after reviewing it
  for private data. The raw `raw-events.ndjson` stays private.
- Use only synthetic, non-personal speech. Do not point the fault actions at production or a remote
  customer system.

## Frozen Profiles

| Profile | What it proves | Exact gate |
| --- | --- | --- |
| `switches` | UI button -> authoritative state -> same LiveKit connection | 100 atomic mode switches |
| `reconnects` | real page/LiveKit reconnection -> authoritative replay | 50 reconnect cycles |
| `audible` | delivered audio plus the complete adversarial call scenario | 65-minute audible call |
| `soak` | process survival, RSS, tasks, segments, and results | 120-minute synthetic soak |

Run the four profiles separately. In particular, the audible profile ends with a clean hangup, so
the 120-minute soak must use a fresh signed session; an ended session is intentionally terminal and
cannot be reused.

Each reconnect compares the exact task and speaker replay before and after the browser rejoins. It
rejects lost IDs, duplicate IDs/results, lower sequence/revision, a terminal task returning to an
active state, or content changing without a sequence/revision change.

The structured latency trace extractor reads content-free `[VoiceHop]` JSON events and reports only
counts and p50/p95/max durations for:

`utterance end -> gateway dispatch -> agent start -> optional tool start/end -> first model token ->
TTS first byte -> audio output`

The machine-readable source of truth for environment ports, prerequisites, fresh-session slots,
exact argv, expected counters, and MPV-to-gate traceability is
`acceptance-manifest.template.v1.json`. Copy it only into the private R&D tree for execution; never
put signed session values into the public template.

## MPV-032 Through MPV-056 Audit

| Cases | Primary proof | Fail-closed evidence |
| --- | --- | --- |
| MPV-032–033 | one-click and 65-minute audible profiles | click/listening, acknowledgement, substantive audio, silence, linked-chat parity |
| MPV-034–036 | multi-speaker audio plus independent diarization evaluation | clean accuracy, noisy DER, separate-track attribution, owner abstention, revision, Unknown and identity audit |
| MPV-037–038 | 100 switches and adversarial audible actions | unchanged RTC connection, authority audit, interruption, cancellation variants, suppression barrier |
| MPV-039–040 | authoritative task/source events plus distinct session failure runs | trace completeness, DOM visibility, needs-input/retry, auth/signature/route/gateway recovery |
| MPV-041–044 | 50 reconnects, fault actions, and 120-minute soak | exact replay, classified failures, three clocks, no duplicate execution, crash, leak, or growth breach |
| MPV-045 | post-call persistence/retention inspection | zero raw audio, expired speaker map, deletion/export, memory hardening, no unauthorized side effect |
| MPV-046–048 | browser-capability, task-pressure, and hung-owner cancellation probes | raw identifier rejected, barrier survives 1,001 later tasks, non-blocking truthful cancel acknowledgement |
| MPV-049–051 | malformed snapshot, API restart, and 4,200-segment history probes | fail-visible recovery, durable barrier/replay, complete on-demand speaker traversal |
| MPV-052–053 | real Telegram call link plus web/Telegram Agent permission matrix | one-time exchange/replay denial, one-click call, canonical Agent ACL, revocation, decoy rejection, Listen-Only bypass |
| MPV-054 | accepted/candidate LiveKit dependency sets | identical suites and calls, QoE delta, warning diff, build/install/clean parity; no recency-only promotion |
| MPV-055–056 | stable/false interruption plus presentation/durable-work probes | no stale resumed speech, playback commit truth, durable work survives ordinary barge-in, explicit cancellation remains authoritative |

The harness does not claim that one long browser tab itself proves every adversarial path. The
external evidence file aggregates the separately measured browser, network, diarization, database,
and authority checks. Every required Boolean and numeric field is mandatory for the audible
profile; a missing value fails its named gate.

## Private Manifest

Create a private JSON file outside the public checkout. Values below are placeholders; use a newly
signed synthetic session and synthetic fixtures in the real file.

```json
{
  "environment": "dev",
  "callUrl": "http://localhost:<playground-port>/call-bootstrap?callSessionId=<synthetic-session>&autoConnect=1#viventiumCallCapability=<private-ephemeral-capability>",
  "audioFile": "/private/path/to/65-minute-synthetic-multispeaker.wav",
  "logs": ["/private/path/to/voice-gateway.log"],
  "processes": [
    { "name": "api", "pid": 10001 },
    { "name": "playground", "pid": 10002 },
    { "name": "voice_gateway", "pid": 10003 }
  ],
  "snapshotIntervalMs": 10000,
  "reconnectOfflineMs": 750,
  "warmupMinutes": 10,
  "externalEvidenceFile": "/private/path/to/external-evidence.v1.json",
  "actions": [
    { "profile": "audible", "kind": "mode", "mode": "wing", "atSeconds": 300 },
    { "profile": "audible", "kind": "participant_join", "name": "guest", "callUrl": "<signed-guest-url>", "audioFile": "/private/path/to/guest.wav", "atSeconds": 420 },
    { "profile": "audible", "kind": "participant_leave", "name": "guest", "atSeconds": 540 },
    { "profile": "audible", "kind": "barge_in", "name": "barge", "callUrl": "<signed-barge-url>", "audioFile": "/private/path/to/barge.wav", "atSeconds": 720 },
    { "profile": "audible", "kind": "cancel", "atSeconds": 1080 },
    { "profile": "audible", "kind": "network_loss", "durationMs": 1500, "atSeconds": 1440 },
    { "profile": "audible", "kind": "provider_degrade", "executable": "/private/path/to/fault-control", "args": ["degrade", "stt"], "atSeconds": 1800 },
    { "profile": "audible", "kind": "provider_recover", "executable": "/private/path/to/fault-control", "args": ["recover", "stt"], "atSeconds": 1860 },
    { "profile": "audible", "kind": "refresh", "atSeconds": 2400 },
    { "profile": "audible", "kind": "mode", "mode": "listen_only", "atSeconds": 2700 },
    { "profile": "audible", "kind": "mode", "mode": "call", "atSeconds": 2820 },
    { "profile": "audible", "kind": "hangup", "atSeconds": 3890 }
  ]
}
```

The audio timeline must naturally ask for a real lookup and sources, include at least two speakers,
and put the barge-in clip during expected assistant speech. Fault commands are disabled unless the
operator explicitly adds `--allow-command-actions`; they must be reversible, local-only, and narrowly
target the synthetic runtime.

Start the private external evidence file from `external-evidence-template.v1.json`. Populate it only
from measured browser/network/diarization evidence: actual Call-click to listening, task/source DOM
visibility, cancellation barrier/state, acknowledgement/audio/barge-in latency, maximum explained
active-work silence, cloud audio egress bytes under local-only policy, clean attributed-word
accuracy, noisy-bank DER, false verified-owner assignments, and diarization-added caption latency.
Also populate every named behavior path from a real browser/persistence/action-authority run. Missing
values fail their gates; the harness never treats an absent measurement as zero or a declared
scenario as executed.

For task recovery, traverse every compound-cursor task page, receive `synchronized` only after
complete durable replay, and observe an isolated API process's new task on the existing stream
without reconnecting. Capture `taskOwnerCapabilityInventory` from the authenticated task snapshot;
do not hand-author it. When that authoritative runtime registry advertises an input-capable owner,
the needs-input gate requires one exact accept-and-resume round trip. When it truthfully advertises
zero input-capable owners, the gate is explicitly `NOT_APPLICABLE` (never `PASS`); missing or malformed
inventory is `FAIL`. An owner without an input adapter must still fail visibly as
`task_input_unsupported` with no dead input control. Telegram exchange, Agent ACL, and
dependency-comparison evidence may run as separate deterministic profiles and enter public results
only through content-free fields.

## Escaped Regression Bank

Run these deterministic probes independently and aggregate only their public-safe Boolean outcomes
under `escapedRegressions` in the private external-evidence file. Keep raw request values, event
payloads, browser captures, process logs, persistence records, and segment content private. A `true`
value is valid only when every listed proof is present; absence or partial coverage is `FAIL`.

| Field | Required private proof before `true` | Exact failure condition |
| --- | --- | --- |
| `rawSessionIdWithoutBrowserCapabilityRejected` | capable-browser positive control plus capability-free negative requests for task get/list/cancel/input/retry, speaker history/snapshot, and event subscription | any read, mutation, or subscription succeeds from the raw session identifier alone |
| `suppressionBarrierPreservedAfter1001Tasks` | cancel/barrier an early delayed task, finish at least 1,001 later task IDs, inject its late result, then audit every suppression plane and replay | barrier disappears, any late output escapes, fewer than 1,001 later task IDs are exercised, or unrelated replay is lost |
| `hungOwnerCancelAckWithin250Ms` | cancellation owner never resolves; browser/network timing proves accepted/cancelling <=250 ms and barrier <=1 s; late result is injected | response waits for the owner, either budget is missed, terminal copy is false, or late output escapes |
| `malformedTaskSnapshotFailsVisible` | unsupported version, missing field, invalid state, duplicate sequence, truncated JSON, and wrong content type; each preserves known-good state and exposes retry | any malformed variant looks successful, is partially applied, is silently discarded, or retry duplicates work/result |
| `apiRestartPreservesBarrierAndReplay` | pre/post controlled API restart diff for running/completed/cancelled tasks, result, speakers, and barrier; late cancelled result injected after restart | state or barrier is in-memory-only, replay changes, or post-restart late output escapes |
| `speakerHistoryBeyond4096Accessible` | generate at least 4,200 deterministic segments; after refresh/reconnect traverse the complete supported history and verify earliest/middle/latest | only the live window is checked, any older record is unreachable, or traversal loses/duplicates/regresses data |
| `telegramOneTimeCallLaunch` | real `/call`, pre-exchange fragment strip, same-idempotency lost-response retry, different-value and second-browser replay, no-store/referrer/log audit, and successful call | a consumed link/raw id is reusable, replay reads or mutates state, capability material leaks, or the successful path adds setup |
| `canonicalSessionAgentAuthority` | web/Telegram creation and every Call/Wing turn under global `USE`, resource `VIEW`, revocation, body-decoy, and Listen-Only controls | session/body metadata bypasses ACL, revocation is delayed, hidden Agent existence leaks, or Listen-Only executes an agent |
| `taskPagingCrossProcessTail` | more than one durable page, full replay before sync, malformed/repeated cursor negatives, and isolated API writer observed without reconnect | sync certifies partial history, a boundary skips/duplicates, another process is missed, or reconnect is required |
| `needsInputCapabilityTruth` | authenticated runtime owner inventory; when input is advertised, capable owner accepts exactly once and resumes; when zero owners advertise input, explicit `NOT_APPLICABLE`; incapable owner emits `task_input_unsupported`; Listen-Only hides input/retry | hand-authored/missing inventory, N/A reported as PASS, dead textbox, fake acceptance, duplicate delivery, unsupported owner stays in `needs_input`, or Listen-Only gains new-work authority |
| `livekitDependencyPromotionGate` | identical `1.5.10` and candidate suites, measured user-grade call gates, warning diff, exact package set, build/install/clean parity | recency alone promotes a candidate, plugins are mixed, or a no-benefit/new-warning candidate replaces the accepted set |

The harness adds one named `FAIL` gate per field for the `audible` acceptance result. Its self-test
checks only schema and parser behavior and never supplies these runtime values or implies the probes
passed.

## Commands

Fast, offline harness self-test:

```bash
node qa/modern-playground-voice/scripts/world_class_call_acceptance.js \
  --self-test \
  --output-root /private/path/to/voice-qa-output \
  --result /private/path/to/voice-qa-output/self-test.json
```

Run one profile only after the integrated source, built artifact, and active runtime are frozen and
verified to match:

```bash
node qa/modern-playground-voice/scripts/world_class_call_acceptance.js \
  --profile switches \
  --config /private/path/to/runtime-manifest.json \
  --output-root /private/path/to/voice-qa-output
```

The audible profile needs `--allow-command-actions` only when the private scenario deliberately
uses local provider fault/recovery commands. A nonzero exit or any `FAIL`, `PARTIAL`, or `BLOCKED`
result prevents completion.

Use `environment: "dev"` for 4180/4190/4300, `environment: "installed_prod"` for
3180/3190/3300, and `environment: "clean_install"` for the new-directory proof. After dev passes,
promote and repeat a real synthetic audible call against the installed artifact with
`livekit_synthetic_audio_qa.js`. The exact ordered commands are in the acceptance manifest.

## Review Checklist

- Source checkout, nested component pin, build, installed artifact, and running process match.
- All requested actions ran on the real browser/call surface; no manifest action was counted merely
  because it was declared.
- Delivered audio playback events and complete latency traces exist.
- Inbound WebRTC audio energy rises in early, middle, and late windows of the audible run, with no
  evidence gap longer than 20 minutes; one initial audio-element play is not accepted as 65-minute
  proof.
- Authoritative source events and at least two call-scoped speaker keys were observed.
- Cancellation reached a real cancelling/cancelled state.
- Provider degradation appeared as a persisted degraded/failed call state and recovery succeeded.
- The 120-minute final RSS sample for every named process is no more than 10% above its post-warm
  baseline; no process crashed and no active task leaked.
- Task, segment, and result replay counters are all zero.
- Raw artifacts remain private; the sanitized result has no paths, URLs, IDs, or transcript text.
