# Telegram overlapping-reply recovery

QA mode: **blast-radius**. Scope: the reported Telegram reply failure and its confirmed
generation, source-order, receipt, rollback and retained-input consumers.

**Result for this 2026-10-23 candidate: PARTIAL.** The loaded repair passed ordinary replies, corrected A/B/C output and
Web Stop-to-Telegram continuation. Natural contextual file work now reaches its native worker and
delivered the correct document. A reminder also reached the worker but arrived late without a
durable timer. Missing-file inspection returned an unsupported answer. The bounded poller
identity and normal-reply recovery checks passed. This is not whole-system readiness.

The [later Should-flow acceptance](../../parallel-orchestrator/reports/2026-10-23-should-flow-acceptance.md)
records the 24 October follow-up. Its matching paths have later evidence; this report retains
the results and limits of its own candidates.

## Cause and correction

A newer input could revoke an older reply before Core marked that reply superseded. The old
producer then reported a failure. Telegram could send a conflicting failure receipt after
removing its preview. Rollback could restore that terminal revision and repeat admission errors.

The repair uses existing owners:

- Classify supersession from recorded generation and source-order state. Join concurrent
  supersession work, and keep the logical turn open until its successor is claimed.
- Keep one noncommitted receipt per revision. Persist it in the existing acknowledgment outbox
  before transport, and retry the same receipt after an outage or adapter restart.
- Retain unadmitted input and original source authors. Do not reactivate terminal or deleted
  admitted jobs, or discard pending input during completed-job cleanup.
- Start new input after a genuinely failed predecessor without borrowing its native continuation
  authority or silently replaying its work.
- Accept a failure receipt even when no assistant row was published. Successful delivery still
  requires its exact saved presentation.
- Use the existing ordered source linker for recovered input batches. A missing unpublished
  first parent needs validated retained-input and owned ancestry evidence and the existing
  native source mutation fence. Invalid ancestry remains unavailable.
- Include the owning context guard in existing sanitized error-location diagnostics. Do not log
  source text, credentials or machine paths.

The initial overlap repair changed no model, prompt, tool, memory, Feeling, provider selection or
Queen/worker policy. The later capability-description candidate is recorded separately below.

## Evidence

Counts below describe separate banks; some coverage overlaps.

| Check | Result |
| --- | --- |
| Actual Core controller, final candidate | 167 passed |
| Actual receipt routes | 86 passed |
| Telegram stream, removal, outage and typing consumers | 176 passed |
| New watermark-before-claim cases and genuine-failure controls | 7 passed per job store |
| Generation completion consumers | 169 passed |
| Final job-store, rollback, ordering and source recovery consumers | 218 passed |
| Final Memory parity consumers, including three causal cases | 169 passed |
| Durable negative receipt and existing outbox/poll consumers | 15 passed |
| Sanitized context error-location checks | 18 passed |
| Real Telegram ordinary reply | Passed |
| Real Telegram A/B/C overlap on final running build | Passed |
| Saved reply visible after reopening the chat | Passed |
| Delivery source ledger and saved receipts | Ordered A/B/C; earlier revisions removed; final committed |
| Typing after completed reply | Stopped |
| Reply error log during final live checks | No new reply error |
| Build and installed Telegram source identity | Matched the loaded candidate |
| Canonical configuration | Unchanged |
| Retained batch after an injected admission failure, real Telegram | NOT RUN; acceptance PARTIAL |

The live overlap used a normal request and two corrections. One final reply retained the original
request and both corrections. A later independent message also received a committed answer.
The separate deterministic recovery checks carried every original pending source through the
real provider formatter and protected Main context carrier; invalid-source controls still fail
closed. They did not reset or rerun old failed personal requests.

An independent Opus review challenged the source and evidence. Material findings were corrected;
the final source candidate was approved. Review approval does not replace the omitted live check.

## Happy and unhappy path follow-up

The follow-up found and repaired additional causes in the same owning paths:

| Cause | Delivered change | Proof |
| --- | --- | --- |
| A single retained input pointed to a reply that was never published | The existing Telegram parent selector keeps a valid original or repaired parent. Only a genuinely missing original can use validated, complete conversation ancestry through the existing native source-mutation fence and exact old-parent update. Deleted, foreign, cyclic, incomplete and malformed parents remain rejected. | Actual route and protected Main carrier regression; 67 selected cases passed on the final source. |
| Recovery waited behind an already removed predecessor when the successor's first claim never arrived | Both stores admit the saved input only with the exact current removal receipt and matching revoked native publication. Existing release, complete-source recovery and effect checks remain required. | 234 store/consumer cases passed; both original causal failures now pass. |
| Background activation completed after the Main client had cleared its context | Capture the accepted request, agent and canonical IDs before disposal. Continue through the existing background execution, persistence and completion lane. Superseded revisions cannot speak again. | 450 client cases passed, including the actual disposer. The loaded Telegram run completed late background work and saved its terminal results. See `ACT-51`. |

These are structural corrections. They add no intent rules, prompt changes, model changes,
queue, harness layer or wait before the first answer. Healthy turns add no history scan or
job-store network round trip.

### Final candidate checks

The supported launcher compiled and restarted the candidate before the final live checks.
The source, compiled store guard, installed Telegram code and active processes matched. Canonical
configuration was unchanged.

| Path | Actual result |
| --- | --- |
| Ordinary Telegram message after loading | Correct reply; saved and committed. |
| Rapid A/B/C corrections after loading | One final answer respected all three inputs. A and B had removal receipts; C committed with all original sources in order. |
| Reopen and idle | Saved replies remained visible; no duplicate, status message or lingering typing. |
| Background activation after Main disposal | Ordinary and corrected turns settled their background batches. Superseded batches remained silent. No recurrence of the null-agent or one-pass pipeline failure in the correlated runs. |
| Persistence | Four user inputs and two assistant replies; no obsolete A/B assistant row or error row. |
| Lost negative receipt before Core acceptance | Existing outbox retained the exact receipt across bridge reconstruction. |
| Core accepted receipt, then local cleanup was interrupted | Same receipt replayed idempotently; no new conversational send. |
| Local outage, then real Core acknowledgment | Injected local 503, reconstructed bridge, real Core 200, owned queue drained to zero. No chat or audio resend. |
| Invalid acknowledgment credential | Real Core 401; receipt stayed pending. Live credentials and configuration were unchanged. |
| Genuine current failure and ambiguous start | Twelve selected controls passed. Genuine failure stayed failed; ambiguous accepted work was not automatically replayed. |
| Source-order outage, send/edit/delete errors, typing and status speech | Fifty-two selected producer checks passed. Unknown state did not become invented removal proof. |
| New receipt interruption boundaries | Three new integration checks passed. Counts overlap the selected banks above. |
| Ready recovery and singleton missing-parent recovery, fault-injected into live Telegram | NOT RUN; live acceptance remains PARTIAL. Actual route/store/carrier regressions passed. |

Opus approved all four final follow-up product sources. It caught a test-receipt timing error:
some route results preceded the final guard. A single rerun of all 67 selected cases on the
final bytes passed and closed that evidence finding. Independent review found no material
source defect. Review does not substitute for the omitted live fault injection.

The full route bank was not completed: a broad attempt exhausted the owned test process's heap,
including one larger-heap retry. The affected 67-case selection passed; 112 unrelated cases
were deselected. No heap failure or omitted case is reported as a pass.

### Later startup recovery exposed a mutable-parent race

A later availability check found the native app services stopped. Existing logs did not prove
why they stopped. The supported background launcher restored them. An overdue scheduled turn and
a real user message queued during the outage then ran together. Automatic conversation reuse
selected the scheduled assistant while its answer was still unfinished. Its normal final save
changed the captured parent text; the exact-parent guard correctly rejected the user's reply.
The earlier successful live run did not cover this occurrence.

The first filter excluded every declared unfinished assistant. Its causal selector run changed
from six failures to 19 passing; a 30-check consumer run also passed. Review then found that a
confirmed native Stop also retains `unfinished=true`. Those results did not prove Stop recovery.

The corrected selector reuses the existing `finish_reason=incomplete` marker to keep a persisted
Stop while excluding an active draft. Returned history and the shared raw leaf selector stay
unchanged, preserving callback detection of active Main. Native source-edit, deletion, ownership
and explicit-parent proofs remain strict. No wait, extra database request, prompt rule or routing
layer was added. The final frozen-source run passed **46 checks**: actual native Stop persistence,
partial answer and interruption context, replay, stable-parent selection, Telegram, scheduler,
protected Main carrier and worker callback consumers. There were 466 unrelated deselected checks.
Selector lint passed with no errors or warnings; existing integration fixtures retain their
pre-existing formatting warnings. See `TR-035`.

### Native failures must close their saved reply and stream

A separate consumer defect could leave an accepted native reply pending after the host emitted a
terminal error. The ordinary message snapshot ignored native ownership; after revocation, normal
stream error and completion calls could also ignore the old producer.

The existing native failure owner now handles a system error snapshot bound to the exact current
request. Only its pending or prepared reply can fail. A changed authored parent may settle that
failed attempt truthfully, but cannot accept a stale successful answer. Owner, conversation,
source and request identity remain required; Stop, committed, removed, revoked and explicitly
edited sources stay protected. Late Cortex results cannot reopen the terminal answer. The
controller uses the existing revoked-native failure path to close the stream with the saved typed
cause. A typed parent conflict maps to `source_context_unavailable`; auth and rate-limit failures
retain their separate classes. No prose matching or automatic task replay was added.

Review found one further failure boundary: exhausting the terminal Mongo write must not leave the
stream open after this request revoked its own publication. That exact revocation proof now closes
its typed error stream even if the saved row is not yet settled. Existing recorded-failure recovery
later persists only the matching historical failed reply from the durable error job and revoked
receipt. It cannot replace a confirmed Stop, change the failure payload or publish into a successor.
No task or provider call is replayed.

The final ordinary API test configuration passed **27 actual Mongo/message/controller consumer
checks**, including pending and prepared failure, transaction retry, saved-outcome recovery,
exhausted-write stream closure, later recorded-failure settlement, actual error and FINAL delivery,
typed causes and negative ownership/terminal controls. This supersedes the earlier 22-check result;
private test aliases and overlapping runs are not counted as additional final acceptance. The final
correction is JavaScript-only and does not require another package compilation.

### Direct context projection retains one proven inline copy

The existing Direct request-copy projection now omits a repeated inline source prefix only when
the trusted Core protocol, owner, epoch, bound input digest, part index and source manifest prove
an identical version. The earliest visible copy remains; changed, unknown or tampered versions
break reuse. Unique goals, instructions, messages, tool and reasoning protocol, files, images,
source manifests and the raw SDK journal remain intact. This does not summarize conversation
history or remove an unmarked legacy block.

Review also found that omitted inline bytes had left their original delivery counts in the outgoing
metadata. The projected descriptor now sets `inline_chars: 0`, `delivery: retrieval`, and an exact
`retained_inline` reference to the earliest visible copy; source and aggregate counts agree. Unknown
or inconsistent carrier identity, count or delivery metadata preserves the original bytes.

The final **71 focused checks** passed, including the actual official SDK model adapter for three
providers without network or model calls. This supersedes the earlier 66-check result. Three small
synthetic semantic cases also ran old versus proposed through the existing configured Direct
Grok 4.7/Low runner: **6/6 answers passed**. The repeated-source case reused the exact earlier copy;
changed and unbound controls kept their own source. These were no-action checks, not production
worker, Voice or latency acceptance.

One exact private-history replay reduced serialized
user content from 867,501 to 580,797 characters by removing 11 repeated source prefixes containing
264,495 UTF-8 data bytes. These are payload measurements, not tokens or elapsed time. There is
no measured latency gain or proof that duplication caused the missed worker handoff. Every retained
reference resolved to its earlier visible copy; original snapshots and raw SDK journal were unchanged.

### Loaded repair candidate: real user checks

The supported launcher loaded the reviewed repair candidate. The following results belong to that
candidate, not to the additional watchdog and tool-description changes still under repair.

| User path | Actual result | Status and boundary |
| --- | --- | --- |
| Ordinary Telegram message | Correct brief answer, saved native completion and committed Telegram presentation. | PASS for this message; not whole-system readiness. |
| Rapid Telegram A/B/C corrections | One correct final answer retained the three ordered original inputs; its native reply completed and Telegram presentation committed. A later capture confirmed all three ingress records completed, with zero lease, retry, failure or pending acknowledgment and no missing parent. | PASS for visible output, source preservation and durable settlement. |
| Web Stop, then Telegram follow-up in the same conversation | Stop saved a cancelled reply with `finish_reason=incomplete` and empty authored text. The new user message and completed answer's native source parent both retained that exact stopped reply; Telegram committed the answer. | PASS for an empty stopped reply and cross-surface continuation. Nonempty stopped partials and replay remain deterministic coverage, not this live observation. |
| Previously stuck accepted reply | The existing native owner saved a typed failed terminal outcome with the original user-source digest unchanged. | PASS for settlement: zero provider calls, goal replays or direct database writes. The original task was not fulfilled or silently retried. |
| Natural reminder request | Main answered that it could not set the reminder; it did not call the configured worker handoff. | FAIL: a completed conversational response is not completed work. |
| Reminder request with explicit worker guidance | Main called the handoff, which returned typed `runtime_dependency_missing`. | FAIL: no verified reminder creation or due delivery. This distinguishes a capability/runtime failure from the earlier missing handoff decision. |

The stopped reply contained no authored answer, so this live check does not prove that a provider
used a nonempty retained partial. The exact live scheduled-reply/new-input race was not separately
fault-injected. The failed task's saved error and later successful new replies do not prove its
original objective was completed.

### Runtime availability and native prerequisite corrections

The next supported reload retained the r05 repair sources and matched the reviewed source
identity. It also loaded narrow fixes in existing runtime owners:

| Proven cause | Correction and evidence | Boundary |
| --- | --- | --- |
| A quiet health-check grep exited early, causing curl write failure under `pipefail` and false unhealthy results. | Consume the complete health response. Seven focused checks passed, including missing-marker, HTTP-error and truncated-transfer controls. Three live predicate reads passed; a bounded loaded healthy window kept the same Core process without a health-triggered restart. | No restart threshold, process ownership check or health failure was bypassed. This does not prove why every earlier service outage occurred. |
| Native CLI capability probes could lose valid help output through short pipe capture. | Existing probe capture retains stdout, stderr and exit status. Twenty-three focused prerequisite/version/control checks passed. | A passing prerequisite is not an executed Claude fallback or completed user task. |
| Process-start receipt comparison depended on locale. | Use a fixed locale only for the existing process-start identity read. The causal check failed before repair; seven focused writer/reader and stop-owner checks passed, as did shell syntax. Existing live receipts still matched without rewriting them. | No receipt format, ownership fence, broad process-kill rule or timezone changed. |

The first Telegram startup in this sequence did not remain active. Existing supervised recovery
restored the owned poller and real replies. Retained logs did not prove the first exit's cause;
it is not reported as a proven watchdog or process-inspector defect.

### Native worker work and delivery on the second loaded candidate

| User path | Actual result | Status and boundary |
| --- | --- | --- |
| Guided file request using earlier conversation facts | Native Codex GPT-6.1 Sol at High inherited the original three facts and created the correct three-line, 71-byte text file. Actual native commands completed successfully; no Queen-written replacement brief supplied those facts. | PASS for this explicit handoff, inherited context and native file execution. |
| File callback and channel delivery | The exact worker/run/result callback was accepted; Core marked its delivery sent with a Telegram message and attachment receipt. A click on the Telegram document produced a local 71-byte file with the exact terminal manifest hash. | PASS for native bytes, exact delivered-file ledger and actual downloaded bytes. The initial browser download-event wait timed out; later file creation metadata and bytes confirmed that same download succeeded. |
| Natural browser request | A configured Codex worker used native computer tools in Chrome and returned the actual Wikipedia heading. | PASS for this natural handoff and browser task. It ran after the file worker completed, so this does not prove simultaneous worker A/B execution. |
| Natural reminder and natural file requests | Both conversational replies refused the work with no handoff. | FAIL. The guided file success and natural browser success do not establish general action reliability. |

### Handoff-description correction and exact-model evidence

The native wrapper had omitted part of the existing worker-capability contract. Restoring that
contract in the owning tool description is narrower than adding a new Main prompt, router or
intent rule. However, the earlier proposed wording passed **4/4 tool-selection controls** but only
**2/4 truthfulness controls**: it promised a due reminder from accepted work alone and described
computer execution as running before native execution proof. That candidate is not accepted as a
working solution. Mock tool acceptance is not completed work.

A further correction exposes only the factual scopes of the worker's existing typed capabilities
in the same coordination brief. Its five old/proposed full-context mock cases on the configured
Grok 4.7/Low route selected correctly in **5/5 old and 5/5 proposed** cases. Proposed receipt truth
was **3/5**, versus **4/5 old**. There is no incremental causal selection win and no broad
truthfulness pass. These mock scores are not substituted for real actions or discarded because
some later real requests worked.

### Latest loaded candidate: natural action results

The new factual scope metadata was present in the three actual native inputs, including independent
worker authorization and unproved-live-connection markers. It was loaded, not merely saved in source.
The active compiled job manager and both job stores matched their current source maps, including
the revoked-native failure method.

| Natural user path | Observed result | Verdict |
| --- | --- | --- |
| Create a file from earlier conversation facts | Original request and earlier facts reached native Codex GPT-6.1 Sol at High. It created the correct 77-byte file; one Main follow-up and Telegram document delivered. Ingress completed. | Handoff, inherited context, receipt wording and observed file delivery PASS. Input-to-delivery was 87.492 seconds; this is not a fast-response benchmark. |
| Reopen Web and download that file | Web reload retained the replies and actual document card. Clicking the 77-byte card downloaded a local file with the exact native manifest hash and content. | Persistence and real Web download PASS. This and the reconciled earlier Telegram download close the downloaded-byte gap for these two files only. |
| Send a cue after two minutes | Original request reached native Codex at High. The initial acknowledgment truthfully said accepted and not yet on the clock. Exactly one cue arrived 167.336 seconds after input, 47.336 seconds late. No matching schedule record, timer or sleep action was observed. | Handoff and delivery PASS; precise durable timing FAIL. A late final worker answer is not a verified timer. |
| Inspect a missing file without creating it | Queen asserted that the file was missing with zero work calls, no worker and no native inspection. | Action selection and evidence truth FAIL. This is not a successful negative inspection. The last captured ingress was still admitted, so completion is not claimed. |

These observations do not establish that all action requests now hand off reliably. The missing-file
assertion and inaccurate reminder timing remain two concrete quality gaps. No generic readiness,
parallel-worker, Voice or latency pass follows from the successful file request.

### Poller ownership inspection: bounded repair passed

A later live check found that the existing working-directory inspection could time out against a
healthy, unchanged Telegram process. Two of three `lsof` probes reached the two-second deadline,
so an unavailable inspection could look like a dead candidate and trigger supervision churn.
The existing native macOS working-directory reader now supplies that proof to the shared inspector.
Exact UID, process start, command and working-directory guards remain unchanged. Unavailable native
proof still fails closed. No retry, timeout increase, queue or lifecycle framework was added.

The final active-source bank passed **38 checks**: identity and handoff controls plus an actual
captured-helper import and second immutable integrity verification. The first captured candidate
failed that verification because import wrote bytecode; reuse of the existing temporary
no-bytecode-write guard closed it. The original failure remains evidence, not an omitted pass.

Three fresh real active-helper health reads passed against the same live poller and unchanged start
identity. The existing source-owned watchdog invokes this helper afresh, so no bot signal, restart,
component switch, data or configuration change was needed. This is bounded native-availability
acceptance, not endurance. The original first-startup timeout was not logged; its exact historical
cause remains unproved even though the current repeated timeout and shared inspector defect are
proved. See `TR-037`.

A new ordinary recovery request also passed all **13 source/native/delivery bindings**: correct
short answer, zero worker calls, exact source and parent, native completion, one committed Telegram
presentation and no input failure. A post-lease capture confirmed durable ingress completed with
zero lease, retry and failure. The earlier admitted snapshot was normal lease reconciliation, not
evidence of lost delivery or terminal failure. This recovery does not excuse the two behavioral
failures above.

Earlier Claude Desktop review approved the source repairs at their recorded identities. The later
Claude CLI review attempts timed out, including the latest material-delta attempt; they produced
no final verdict and must not be counted as additional approvals. Review and truthful typed
errors do not establish product readiness.

## Limits

This is focused incident evidence, not whole-system, Voice/audio, complete worker-capability,
parallel-worker, endurance or latency acceptance. Those broader checks were **NOT RUN** in this
batch; the two native worker observations above are narrower. Historical failed requests stay
visible and failed; successful new messages do not prove those original tasks were fulfilled.
Retained-batch recovery has deterministic and real-history structural proof, but no live
fault-injected acceptance. The follow-up above supersedes the earlier singleton and ready-claim
limitations for the configured native path. Invalid ancestry and missing native authority still
fail closed. A non-native predecessor without a native publication record does not receive this
continuation bypass.
The shared runtime also has historical unresolved worker-delivery warnings outside these
correlated turns; this report does not claim those tasks were delivered or the whole log is clean.
Private source snapshots, logs, database rows, review packets and exact identities remain private.
