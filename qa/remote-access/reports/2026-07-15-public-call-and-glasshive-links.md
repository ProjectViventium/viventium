# Public Call And GlassHive Links QA Run - 2026-07-15

## Summary

- Result: PARTIAL overall. Off-LAN public voice now passes end to end after the canonical runtime
  config was corrected to advertise the public LiveKit media address. Public Playground HTTPS,
  LiveKit TCP media, the real voice worker, synthetic microphone STT, transcript persistence, and
  cleanup all passed through an independently routed browser. GlassHive links and fail-closed
  controls remain passed. Same-Wi-Fi public-host access is still blocked by this router's missing NAT
  loopback/split-DNS path.
- Build/source under test: active root checkout plus the active nested GlassHive checkout.
- Runtime/artifact under test: freshly compiled and restarted local-prod runtime.
- Environment: single-user local-prod test install with the custom-domain public HTTPS edge and five router
  mappings.
- Tester: Codex plus the operator for DNS verification.
- Related change: canonical machine-local public LiveKit node-address config plus reusable off-LAN
  browser/media QA. No application runtime code was changed for the recovery. Existing public
  GlassHive-origin and signed-link work remains under the same boundary.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `REMOTE-001` | PASS | Live status, five-surface edge state, generated config, real browser checks | Local and public origins were reported truthfully. |
| `REMOTE-002` | PASS | This sanitized report plus diff/public-safety scan | Private browser/chat media and raw identifiers remain outside the repo. |
| `REMOTE-003` | PARTIAL | Telegram `/call`, external Playwright call/media, GlassHive browser flow, public health checks | Off-LAN voice passes; same-Wi-Fi public hostname is blocked by router NAT loopback. |
| `REMOTE-004` | PASS off-LAN | Public page through a Tor exit, selected TCP ICE pairs, worker join, expected STT transcript, DB cleanup | Page-only and signaling-only evidence was rejected. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `REMOTE-UC-001` | Inspect the public/local runtime state and supported origins. | `bin/viventium status`, public edge, browser | PASS | Status showed the app and GlassHive public URLs and all affected services running. | Generated env, five edge surfaces, five router mappings, no edge error. | None. |
| `REMOTE-UC-002` | Review a public-safe QA record. | QA report and diff | PASS | Evidence is summarized with synthetic markers and no private media. | Public-safety scan and targeted tests. | None. |
| `REMOTE-UC-003` | Recheck after compile, restart, and regenerated links. | CLI, browser, MCP, edge | PASS | Fresh artifact preview survived refresh and showed the exact synthetic marker. | Fresh ref/token lifetimes and active Caddy config matched source. | None. |
| `REMOTE-UC-004` | Open the latest call and GlassHive links off-LAN. | Telegram, public edge, Tor-routed Playwright browser, real microphone fixture | PASS off-LAN | The public call UI stayed active and the expected synthetic phrase was delivered to STT; the GlassHive artifact flow remained available. | LiveKit selected public TCP for both browser peer connections, the worker joined, one transcript persisted, and targeted cleanup removed every synthetic record. | None for off-LAN. |
| `REMOTE-UC-005` | Open the same public Playground hostname from the serving Wi-Fi. | Direct LAN browser/HTTPS probe | BLOCKED | The public hostname times out before HTTP while the same URL returns `200` through the external path. | Router state and direct-versus-external timing isolate missing NAT loopback. | Enable router NAT loopback or install an equivalent trusted split-DNS/HTTPS path. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: public call and public GlassHive access.
- Requirement: `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md` and
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: receive a non-local public link in Telegram/chat and open it from a phone.
- QA case: `REMOTE-003` and `GHWATCH-012`.
- Expected result: public HTTPS URLs work off-LAN; GlassHive exposes only opaque refs; local control
  surfaces fail closed; same-LAN hairpin failure is diagnosed accurately.
- Actual evidence: the original cellular failure correlated to private-only server candidates. After
  compile/restart, the real public page and TCP media traversed a Tor exit, the worker received the
  synthetic microphone audio, the expected transcript persisted once, and logs/DB/config agreed.
- Remaining gap or fix: same-Wi-Fi public-host access requires router NAT loopback or an equivalent
  trusted split-DNS/HTTPS edge. Embedded TURN/TLS also needs an explicitly forwarded relay UDP range
  before it can be claimed as fallback; the direct public TCP path is the proven recovery.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Remote-access docs, `REMOTE-003`, and `GHWATCH-012`. |
| Code owning path | Which code path owns the behavior? | Config compiler -> launcher -> public-edge helper -> Telegram/call or GlassHive signed-ref server. |
| Docs and nested docs/repos | Which docs define expected behavior? | Remote-access and GlassHive runtime requirements plus nested signed-link/server implementation. |
| Scripts or harnesses | What exercised it? | Compiler/helper tests, GlassHive UI tests, MCP worker run, Playwright CLI, Telegram Desktop, and external health nodes. |
| Local/external prerequisite state | Were required dependencies healthy? | Caddy alive, all five router mappings present, GlassHive/runtime/playground healthy, custom DNS resolving externally. |
| Logs | What confirms or contradicts the result? | The pre-fix cellular call had no connection and private-only media candidates. Post-fix LiveKit selected public TCP against an external exit and the worker became active. Forced TURN/TLS gathered relay candidates but selected none because the router does not expose the relay UDP ports. |
| DB/state/persistence | What persisted? | The off-LAN call created one expected synthetic transcript and active worker/session evidence; targeted cleanup removed the synthetic message, conversation, ingress event, call session, and user. Existing GlassHive ref lifetimes remain aligned. |
| Generated/shipped artifact | What generated output was inspected? | Fresh runtime env used the public origin, public-links-only mode, secure cookies, 86,400-second signed-link/reference lifetimes, and a 1,800-second watch session. Active Caddy config had all five hosts and redaction. |
| Real user path | What was used like a user? | Telegram `/call`, the public call page through an independently routed real browser, Start Chat, synthetic microphone delivery, live GlassHive worker completion, artifact preview/download, expanded workspace status, and refresh. |
| Visual/UX comparison | Did visible UX match? | Yes for Telegram, call page, Watch / Steer, artifact preview, download, refresh, and unchanged marketing landing. |
| Not run / blocked | What required surface was not run? | Same-Wi-Fi public-host access is blocked before HTTP by missing router NAT loopback. The post-fix physical-phone rerun is optional confirmation, not a substitute for the completed off-LAN browser/media proof. |

## User-Grade Evidence

- Surface exercised: Telegram Desktop, the public modern call page through an off-LAN browser path,
  LiveKit TCP media, GlassHive Watch / Steer and artifact preview, and the marketing landing page.
- Real user path: sent `/call`; opened the public deep link from outside the LAN; clicked Start Chat;
  delivered a synthetic fake-microphone phrase to the real worker; ran a real synthetic GlassHive
  worker; expanded the delivered output; opened/downloaded the artifact; refreshed the preview.
- Visible outcome: Telegram returned the public call action; the call UI entered the active call
  state without `could not establish pc connection`; the artifact preview showed the expected
  synthetic marker and explicit download/workspace actions.
- Expanded/detail state: Watch / Steer exposed latest workspace output and public opaque actions.
- Persistence/reload result: artifact preview survived reload; the completed worker state and output
  remained visible.
- Local/external prerequisite state: all live local services were ready; public HTTPS and LiveKit
  TCP were externally reachable; the same public Playground returned `200` externally and timed out
  only from the serving LAN.
- Evidence retrieval classification, if applicable: successful.
- Fallback path, if applicable: TURN/TLS was forced as a separate diagnostic. TLS and relay-candidate
  allocation succeeded, but no relay pair could be selected because the router does not forward the
  allocated relay UDP range. The working off-LAN call selected direct public TCP instead.
- Backend/log/DB confirmation: live env, Caddy state/config/log policy, selected external TCP pair,
  worker activity, expected transcript, targeted cleanup, short-ref state, and artifact bytes/hash
  matched the visible result.
- Final model/runtime wording check: generated links use `https://playground.app.viventium.ai` and
  `https://glasshive.app.viventium.ai`; newly generated GlassHive links contain no localhost or raw
  signed token.
- Substitution check: logs, DB rows, API responses, source inspection, and unit tests supported but
  did not replace the real public browser, media, worker, and transcript run. Same-Wi-Fi remains an
  explicit network blocker.

## Automated Evidence

```bash
python -m pytest tests/release/test_remote_call_tunnel.py \
  tests/release/test_config_compiler.py tests/release/test_install_summary.py \
  tests/release/test_voice_playground_dispatch_contract.py -q
HOME=/tmp/viventium-qa-clean-home viventium_v0_4/GlassHive/frontends/glass-drive-ui/.venv/bin/pytest \
  viventium_v0_4/GlassHive/frontends/glass-drive-ui/tests/test_server.py -q
bin/viventium compile-config
bin/viventium dev-runtime activate-current --validate --restart
bin/viventium status
node qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js \
  --audio output/qa/modern-playground-voice/synthetic-audio/short.wav \
  --expect 'Short synthetic voice QA. Alpha bravo.'
```

Focused results: 250 affected root release tests passed. The existing GlassHive UI acceptance run
remains 95/95. The QA operating-contract suite passed 22 checks and still reports one repository-wide
failure caused by unrelated older reports; this report itself has zero template violations.

## Findings

### Voice Root Cause And History

- The April public-edge implementation advertised the discovered public media address.
- The May local-first change intentionally switched the default to the LAN address to preserve local
  callers and expected TURN/TLS to cover remote clients.
- This install left the canonical node-address override blank. The failing Android 5G call therefore
  completed page/signaling setup but received private-only usable media candidates and never formed
  a peer connection.
- The config-only recovery set the canonical public node address, recompiled, and restarted. The
  active LiveKit process then advertised public TCP/UDP candidates, and the autonomous off-LAN call
  selected public TCP successfully.
- Forced TURN proved the old fallback assumption incomplete: allocation produced random relay UDP
  ports outside the router mappings. That remains a documented hardening gap rather than part of the
  working direct-public fix.

- Defects: the failed cellular call exposed private-only LiveKit server candidates while the public
  call page and signaling remained healthy. The canonical machine-local node-address config was
  blank, so the May local-first default advertised the LAN address. A separate forced-relay probe
  showed that TURN/TLS listening on its configured port is not enough when allocated relay UDP ports
  are not forwarded. Existing GlassHive link-lifetime findings remain fixed under their owning work.
- Regressions: none in the affected suites or browser surfaces.
- Flakes: the first nested UI command inherited the installed runtime because its test fixture
  intentionally removes runtime-env overrides. Rerunning with a clean temporary home produced the
  expected 95-pass result.
- Environment issues: same-LAN public-host access times out because the router does not provide NAT
  loopback/hairpin support. Forced embedded TURN is not a valid external fallback until a bounded
  relay range is configured and forwarded.
- Residual risks: the config-only public node address is tied to the current public IP and must be
  updated if that address changes. The preferred long-term LiveKit configuration advertises both
  external and internal candidates. Same-Wi-Fi still needs router NAT loopback or equivalent trusted
  split DNS. Source QA/docs changes remain in dirty developer checkouts and are not a pinned release.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
