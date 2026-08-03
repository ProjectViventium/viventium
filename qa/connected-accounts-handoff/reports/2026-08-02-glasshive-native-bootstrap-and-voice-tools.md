# GlassHive Native Bootstrap And Voice Tool QA — 2026-08-02

## Summary

- Result: `PARTIAL`.
- Universal capability dispatch, missing-auth recovery, Telegram delivery controls, real GlassHive
  LiveKit scheduling and authenticated Microsoft inbox reads, and host-native restart durability
  pass.
- The feature work is accepted by the independent code review and real local surfaces. The overall
  report remains `PARTIAL` only because the requested Claude Opus 5 review is externally
  quota-blocked and the supported clean install/upgrade gate cannot run within current free disk.
  No external message or account mutation was attempted.

The signed Agent capability grant and broker MCP configuration reached the native Codex process,
but conversation mode did not place the signed broker operating contract in native developer
instructions. Because LIFE correctly contains no transient GlassHive scaffolding, the harness had
no authoritative instruction to use the broker and could try an unrelated native connector or web
path.

GlassHive now merges application developer instructions with profile-specific signed bootstrap
instructions for every fresh or resumed native conversation. Application authority is preserved,
the broker contract refreshes with the current grant, and no runtime prompt, transcript, or harness
file is written into LIFE. OAuth failures carry a provider-independent recovery action pointing to
Agent Builder, the owning Agent, and **Connect** beside the unavailable MCP server.

The browser pass also found an Agent Builder delete race: cache removal could refetch a just-deleted
Agent and log a 404. The editor now clears the active selection before deletion and restores it if
deletion fails.

## Scope Run

| Surface / case | Result | User-visible outcome | Correlated evidence |
| --- | --- | --- | --- |
| LibreChat browser, disconnected Microsoft inbox | `PASS` | Exact Agent Builder MCP Connect recovery; no native Gmail or web substitution | One GlassHive conversation request/run; native broker describe returned typed unreadable-credential state; persisted answer matched the visible reply |
| Telegram, same disconnected inbox | `PASS` | Same accurate recovery in one reply | Telegram ingress, one GlassHive request/run, one stored assistant answer, no late duplicate |
| Telegram, authenticated Microsoft inbox | `PASS` | One concise verified unread count; no generic connection error or substitute provider | Telegram Desktop, one GlassHive request/run with connected-tool activity, and exactly one user plus one assistant Mongo message agree |
| Telegram delivery controls | `PASS` | Synthetic request produced two separate text bubbles and no voice note | Delivery log recorded model-requested voice skip, one message break, and two segments; Mongo stored one assistant answer |
| Agent Builder main and Voice Chat Model | `PASS` | GlassHive appears in both provider lists; Codex, LIFE/full defaults, readiness, and low voice effort persist after reload | Playwright save/reload plus Agent API/DB round trip; zero new console or network failure after the delete-race fix |
| Modern Playground / LiveKit GlassHive scheduling read | `PASS` | Visible transcript returned the verified active-schedule count and TTS audio frames were delivered | Selected GlassHive Codex Voice Chat Model, one LibreChat request, one provider session/request/run, one native broker scheduling call, one stored answer, one non-cancelled TTS turn |
| Modern Playground / LiveKit authenticated Microsoft inbox | `PASS` | Visible transcript returned a verified unread count; no Gmail/web substitute and no external mutation | Existing OAuth refreshed non-interactively, MCP connected, voice route selected GlassHive Codex, one provider request/run and connected-tool event completed, Mongo stored one user and one assistant message, one non-cancelled TTS turn |
| Host-native API restart durability | `PASS` | Accepted Codex and Claude turns survive API restart without duplicate launch or truncated input | Large synthetic prompt hashes, atomic supervisor state, exactly one harness launch, active-child cancellation, exact non-zero exit, and timeout regressions |

## Traceability

| Feature | Requirement | Use case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Native GlassHive MCP bootstrap | Signed Agent grants remain authoritative inside the harness | Ask main Agent to inspect a disconnected inbox and an authenticated inbox | Use only the declared broker; either return verified data or the exact supported recovery | LibreChat and Telegram returned the typed Agent Builder Connect path when unavailable; LiveKit later returned a verified Microsoft unread count through the signed broker | None |
| Voice tool parity | Voice uses the selected Agent's actual capability graph | Ask a GlassHive Voice Chat Model for active schedules and authenticated Microsoft unread status | One native broker tool result authors each spoken response | Both LiveKit transcripts, broker invocations, persisted answers, and non-cancelled TTS delivery agree | None |
| Telegram delivery controls | Model may skip voice and split one answer into multiple messages | Request two text segments with no voice note | Two text bubbles, no audio, one stored assistant answer | Telegram UI, delivery log, and Mongo state agree | None |
| Agent Builder persistence | GlassHive is selectable for main and Voice Chat Model | Configure, save, reload, delete synthetic Agent | Exact provider/model/options round-trip and no deletion error | Playwright UI, API/DB state, and repeat delete after fix agree | None |
| Host-native execution durability | An accepted conversation turn is owned beyond one API process | Restart the API during a large Codex or Claude prompt; cancel/timeout/fail separate runs | Complete input reaches one child; exact terminal state is recoverable | Supervisor-owned instruction/start permit/PID/exit markers and focused runtime tests agree | None |

## Full-View Evidence Checklist

| Evidence surface | Result | What was verified |
| --- | --- | --- |
| Requirements and architecture docs | `PASS` | Broker authority, connected-account recovery, voice capability parity, and no LIFE scaffolding |
| Owning code and generated config | `PASS` | Compiler policy, signed grants, native developer bootstrap, Graph handoff, Voice model selection, and scheduling prompt parity |
| LibreChat browser and Agent Builder | `PASS` | Recovery wording, provider lists, readiness, defaults, save/reload, and delete behavior |
| Telegram UI | `PASS` | Missing-auth recovery, one authored response, split delivery, and voice-note skip |
| Modern Playground / LiveKit | `PASS` | GlassHive Voice model, native scheduling and authenticated Microsoft tool use, visible transcripts, and delivered TTS turns |
| Logs, database, and provider state | `PASS` | Single request/run/session correlation, broker calls, persistence, and no late duplicate |
| Automated regression suites | `PASS` | Focused parent, LibreChat, Telegram, voice, GlassHive, and client coverage listed below |
| Authenticated Microsoft inbox read | `PASS` | Existing authorization refreshed without creating or expanding access; a real LiveKit call returned a verified count |
| Supported clean install / upgrade | `BLOCKED` | Current free disk is below the supported clean-install prerequisite; no user data was deleted to manufacture space |
| Claude Opus 5 review | `BLOCKED` | The local Claude Desktop plan had no usage credit available; no substitute model was used |

## User-Grade Evidence

- Surface exercised: LibreChat browser Agent Builder, Telegram, Modern Playground / LiveKit voice,
  and Playwright CLI.
- Real user path: Selected and persisted GlassHive for main and Voice Chat Model, asked natural inbox
  and scheduling questions in Telegram and LiveKit, observed the replies, refreshed Agent Builder,
  and removed the temporary Microsoft selection from the synthetic voice Agent after QA.
- Visible outcome: Unavailable OAuth produced the exact Connect recovery without fabricated inbox
  data; Telegram produced two text bubbles without a voice note; LiveKit displayed verified schedule
  and Microsoft unread counts and delivered non-cancelled TTS turns.
- Expanded/detail state: Agent Builder showed GlassHive provider/model, readiness, LIFE/full defaults,
  and low voice effort; the owning Agent's MCP panel showed the Microsoft Connect action.
- Persistence/reload result: Agent settings survived browser reload and matched Agent API/DB state;
  each Telegram and LiveKit QA turn stored one assistant answer with no late duplicate. The temporary
  Microsoft tool selection was removed through Agent Builder, saved, and verified absent in Mongo.
- Backend/log/DB confirmation: LibreChat, Telegram, LiveKit, native harness, broker, GlassHive state,
  and Mongo evidence correlated each surface to a single authoring request and the expected tool call.
- Final model/runtime wording check: Replies truthfully distinguished unavailable credentials from an
  empty inbox, named the supported recovery, did not claim unverified access, and did not substitute
  Gmail or web search.
- Substitution check: UI evidence was required for visible behavior, audio delivery was proven by
  the active TTS stream and visible transcript, and logs/DB supported rather than replaced those
  paths. The run does not claim the automated tester subjectively heard the audio.

## Automated Evidence

- LibreChat backend focused capability/OAuth/graph/follow-up suites: `393 passed`.
- LibreChat API package MCP and Agent validation suites: `30 passed`.
- LibreChat data-provider configuration suite: `63 passed`.
- Agent delete-race client regressions: `2 passed`.
- Telegram suite: `378 passed`.
- Voice gateway: `352 passed`, `48 subtests passed`.
- GlassHive runtime: `795 passed`, `3 skipped` across the final `798`-case collection after the
  supervisor input-ownership fix.
- Parent release suite: `2239 passed`, `6 skipped` in the final complete dependency-enabled run.

## Findings

- Fixed: native conversation runs did not receive the signed broker operating contract in developer
  authority even though the grant and configuration were present.
- Fixed: OAuth recovery was not consistently available as typed, provider-independent state across
  LibreChat, Graph handoff, GlassHive, and the native broker.
- Fixed: Agent Builder could refetch a just-deleted Agent and log a 404 race.
- Fixed: accepted host-native requests could still depend on the API process to feed stdin, so an
  API restart could truncate a harness prompt even though the child survived.
- Fixed: deferred MCP projection missed default/legacy graph shapes; conclusive-unavailable checks
  treated inspection failures as outages; the omitted Feelings denylist did not inherit its safe
  Viventium default; and a compiled no-op Codex setting implied support that did not exist.
- Fixed: the tracked scheduling prompt registry lagged the live server instruction by one live-read
  requirement.
- Verified unhappy paths: unreadable OAuth credential, invalid or unsigned grant, unavailable
  registry, discovery failure, capability-empty optional handoff, deletion failure, and reload.
- Remaining external review blocker: Claude Opus 5 usage credit is unavailable until the plan reset;
  no Claude approval is claimed.
- Remaining environment blocker: the supported clean install/upgrade gate requires more free disk;
  no original workspace, LIFE folder, runtime history, or user data was modified to create space.

## Public-Safety Review

- [x] No credentials, cookies, OAuth tokens, account identifiers, private message content,
  screenshots, local absolute paths, machine names, run/session/message IDs, or database exports.
- [x] All prompts and visible evidence described here are synthetic and non-personal.
- [x] Raw logs, database rows, and native transcripts remain private runtime evidence outside git.
- [x] The report does not expose conversation IDs, Telegram chat IDs, Mongo `_id` values, stack
  traces with private paths, or raw runtime dumps.
