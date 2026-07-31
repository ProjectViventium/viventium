# Telegram Loopback Client Latency Recovery - 2026-07-25

## Summary

- Result: `PASS-AUTOMATED/PARTIAL-LIVE`
- Scope: real Telegram ingress stall, local LibreChat HTTP client setup, and restart recovery
- Source under test: local universal-upgrade candidate

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-013` | `PASS-AUTOMATED/PARTIAL-LIVE` | Real Telegram send, pending update, process sample, actual claim-path tests, and full Telegram suite | Post-fix reply and restart repeat remain unrun. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-012` | Send a text turn while background delivery polling is active. | Telegram Desktop and configured bot | `FAIL-BEFORE/PARTIAL-AFTER` | Synthetic bubble sent; no reply arrived before the fix. | Pending-update count stayed at one, bot log did not advance, process sample showed CA-bundle open. | Activate fixed runtime and measure reply. |
| `TELEGRAM-UC-003` | Restart Telegram runtime and repeat the turn. | Not yet run after the fix | `PARTIAL` | No post-fix bubble is claimed. | Automated handoff and complete Telegram suite pass. | Restart, send, receive, and correlate logs. |

## Escaped Behavior

A synthetic text message was visibly accepted by Telegram, but the Bot API kept one pending update
and the bot produced no new ingress log. The process and two Bot API sockets were still alive, so a
process-only status check looked healthy.

A one-second live process sample placed every main-thread sample inside
`SSLContext.load_verify_locations` while opening a certificate bundle. That proves an anomalously
slow CA-bundle open blocked the receive event loop, but a statistical process sample does not
identify which local HTTPX caller initiated the open. The periodic GlassHive dispatcher is one
plausible initiator; ordinary construction frequency alone is insufficient to explain one second of
continuous blocking unless an individual filesystem open stalls.

Alternative explanations were checked:

- The message had not reached Telegram: contradicted by the visible sent bubble and pending update.
- Model generation was slow: contradicted because no Telegram ingress handler or LibreChat turn ran.
- A configured webhook owned delivery: contradicted by an empty webhook URL.
- Telegram reported a Bot API error: no current Bot API last-error field was present.

## Fix

For plain-HTTP loopback origins only (`127.0.0.1`, `localhost`, and `::1`), bridge and attachment
clients use `trust_env=false` and skip the unused TLS verifier. Remote HTTP, lookalike hosts, and
every HTTPS origin keep HTTPX's normal environment and certificate-verification defaults.

This removes the CA-bundle-open class from every identified plain-HTTP loopback LibreChat request
without weakening any encrypted remote hop. A real post-fix Telegram retry remains the gate for
whether this fully resolves the escaped stall; reusing a long-lived HTTPX pool remains a possible
separate optimization.

## Evidence

| Surface | Result | Evidence |
| --- | --- | --- |
| Real Telegram send | `PASS` | A synthetic public-safe text bubble was visibly sent. |
| Stall reproduction | `PASS` | Pending update stayed at one, bot log did not advance, and the process sample showed CA-bundle open on the main event loop. |
| Loopback boundary | `PASS` | Tests cover IPv4, localhost, and IPv6 loopback. |
| Remote security boundary | `PASS` | Tests prove remote HTTP, HTTPS loopback, and lookalike hosts retain default HTTPX verification/environment behavior. |
| Telegram regressions | `PASS` | 128 focused bridge/attachment tests and all 346 Telegram tests pass. |
| Post-fix reply | `PARTIAL` | Activation/restart and visible reply timing have not yet run. |
| Restart repeat | `PARTIAL` | A second visible turn after restart has not yet run. |

## Performance Probe

An Opus 5 review repeated the client-construction probe in the Telegram environment and measured
about 3.58 ms per default client, 3.62 ms with only `trust_env=false`, and 0.12 ms with the final
loopback-only options. The CA-verifier change owns the measured speedup; `trust_env=false` is kept
for loopback proxy correctness. This is supporting evidence, not a substitute for the real
post-fix send/reply.

## Traceability

- Feature: Telegram reply responsiveness while background delivery polling is enabled.
- Requirement: loopback request setup in `docs/requirements_and_learnings/03_Telegram_Bridge.md`.
- Use case: `TELEGRAM-UC-012`.
- QA case: `TR-013`.
- Expected: the Bot API update leaves the queue promptly and gets a visible reply while local
  bridge activity continues; remote HTTPS verification stays enabled.
- Actual: the escaped stall location and unnecessary loopback CA setup are reproduced; the initiating
  caller remains an inference, and automated boundaries pass.
- Gap: promoted-runtime visible reply timing and post-restart repetition remain required.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Telegram loopback-client requirement; `TELEGRAM-UC-012`; `TR-013`. |
| Code owning path | Which code path owns the behavior? | Shared loopback HTTP policy plus every Telegram bridge and attachment HTTPX client construction. |
| Docs and nested docs/repos | Which docs define expected behavior? | Telegram bridge requirements, runtime QA map, Telegram runtime cases, and HTTPX client/SSL guidance. |
| Scripts or harnesses | Which harnesses exercised it? | Telegram Desktop, Bot API health metadata, process sampling, focused bridge/attachment tests, and full Telegram suite. |
| Local/external prerequisite state | Which prerequisites were proven healthy or degraded? | Bot API was reachable with no current API error; local LibreChat API was HTTP 200; bot ingress was degraded. |
| Logs | Which sanitized logs confirm or contradict the result? | No ingress line appeared for the pending turn; historical TLS/restart errors support the degraded runtime history. |
| DB/state/persistence | Which state proves it? | Bot API pending-update count remained one; no LibreChat turn was created for the reproduced pre-ingress stall. |
| Generated/shipped artifact | Which artifact was inspected? | Active bot source/venv identity and current local runtime binding were inspected; fixed source activation remains pending. |
| Real user path | Which real surface was used? | Telegram Desktop send through the configured real bot chat. |
| Visual/UX comparison | Does visible UX match supporting evidence? | Visible sent bubble plus no reply matches the pending update and absent ingress log. |
| Not run / blocked | Which required surface was not run? | Post-fix visible reply and post-restart repeat; result remains `PARTIAL-LIVE`. |

## User-Grade Evidence

- Surface exercised: Telegram Desktop configured-bot chat.
- Real user path: sent one synthetic public-safe text message through the normal Telegram user
  surface while the bot process and delivery dispatcher were active.
- Visible outcome: Telegram displayed the sent bubble, but no bot reply arrived before the repair.
- Expanded/detail state: Bot API metadata retained one pending update, the local bot log did not
  advance, and the main event loop was sampled in CA-bundle loading.
- Persistence/reload result: not yet proven after the fix; activation/restart and a repeated turn are
  the next gate.
- Local/external prerequisite state: Telegram Bot API and local LibreChat API were reachable; the
  bot's ingress loop was degraded despite the live process.
- Evidence retrieval classification, if applicable: local prerequisite unavailable at the ingress
  event-loop layer; not a successful-empty model or provider result.
- Fallback path, if applicable: computer/Telegram Desktop supplied the real user surface; no browser
  or local-delegation fallback substitutes for the missing bot reply.
- Backend/log/DB confirmation: pending-update count, absent ingress log, healthy API probe, live
  sockets, and process sample agree that the turn had not reached model generation.
- Final model/runtime wording check: this report identifies a pre-ingress stall and does not call it
  model latency or claim post-fix delivery before the visible rerun.
- Substitution check: process samples, API metadata, source inspection, model review, and unit tests
  support the finding but are not substitutes for the required post-fix Telegram send/reply and
  restart-repeat evidence.

## Automated Evidence

```text
Telegram bridge and attachment slice: 128 passed
Full Telegram suite: 346 passed
Full release suite: 1,993 passed, 11 skipped
Shell syntax, Python compile, and diff checks: pass
```

## Findings

- Defects: plain-HTTP loopback client setup could perform unused CA-bundle I/O synchronously on the
  Telegram event loop and expose Bot API ingress to an anomalously slow open.
- Regressions: bridge and attachment loopback call sites plus remote/HTTPS/lookalike security
  boundaries pass; all Telegram tests pass.
- Flakes: none in focused or complete Telegram reruns.
- Environment issues: the pre-fix bot remained blocked until runtime replacement.
- Residual risks: post-fix visible reply latency and a restart repeat remain required.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
