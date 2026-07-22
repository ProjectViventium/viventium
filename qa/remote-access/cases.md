# Remote Access QA Cases

## Case ID Convention

Use stable `REMOTE-NNN` IDs for remote access cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `REMOTE-001` | Remote/local network access exposes only supported surfaces and reports disabled/degraded states truthfully. | User-visible behavior matches source, docs, persisted state, and logs | CLI/status, browser origin, tunnel config, voice origin | `tests/release/test_remote_call_tunnel.py` plus user-grade QA when visible | PASS-AUTOMATED/PARTIAL 2026-07-15; contract tests pass, isolated lab user-path proof NOT RUN |
| `REMOTE-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS-AUTOMATED/PARTIAL 2026-07-15; public-safety contracts pass, isolated lab report NOT RUN |
| `REMOTE-003` | Custom-domain voice and GlassHive links remain externally usable without exposing local control surfaces. | An off-LAN synthetic client can open call and opaque GlassHive links; lab hairpin failure is diagnosed truthfully. | Isolated external browser, synthetic channel, lab HTTPS edge, GlassHive signed refs | Remote helper/compiler/UI tests plus isolated external-browser QA | PASS-AUTOMATED/PARTIAL 2026-07-15; link/control-boundary tests pass, isolated lab external-browser proof NOT RUN |
| `REMOTE-004` | Public voice acceptance proves the WebRTC media path, not only the page and signaling path. | An off-LAN synthetic caller connects over a public ICE candidate and delivers fixture audio to the worker. | Lab Playground, LiveKit TCP/UDP/TURN, voice worker, fixture DB | `livekit_synthetic_audio_qa.js`, release contract tests, runtime logs/DB | NOT RUN for this public candidate; requires an isolated lab edge/router and synthetic account |

## `REMOTE-001` - Core User Flow

- Requirement: Remote/local network access exposes only supported surfaces and reports disabled/degraded states truthfully.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_remote_call_tunnel.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-15; CLI/config/edge contract tests pass. Isolated lab
  browser and media proof is NOT RUN.

## `REMOTE-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-15; public-safety contract checks pass. A synthetic lab
  user-path report remains NOT RUN.

## `REMOTE-003` - Public Call And GlassHive Link Boundary

- Requirement: public links use the configured HTTPS origins, while the GlassHive operator surface stays closed unless an opaque signed ref/session authorizes the request.
- Risk covered: Telegram `/call` or GlassHive returns localhost; a same-Wi-Fi NAT-loopback failure is misdiagnosed as a dead edge; or port 8780 is exposed as an unauthenticated control plane.
- Preconditions: custom-domain public edge is active, GlassHive is enabled, synthetic public-safe worker/artifact data is available, and an off-LAN phone or external fetch path exists.
- Steps:
  1. Send Telegram `/call`, verify the returned URL uses the configured public playground origin, then open it with phone Wi-Fi disabled.
  2. Generate synthetic GlassHive workspace and artifact refs and verify their visible URLs use `public_glasshive_origin`, contain opaque refs, and contain no localhost/raw token.
  3. Fetch GlassHive `/health` externally; verify `/`, `/docs`, `/api/bootstrap`, raw worker routes, and raw signed-token routes fail without a signed session.
  4. Open the workspace ref in a real browser, verify the tokenless Watch / Steer page, expand status/detail, and refresh. Open/download the artifact ref and verify synthetic content.
  5. Correlate Caddy state/config, generated runtime env, UI/runtime logs, and short-ref DB state without preserving secrets or raw refs in public evidence.
- Expected result: cellular/off-LAN call and opaque GlassHive links work; same-Wi-Fi-only failure is labeled NAT hairpin/loopback; GlassHive control surfaces fail closed.
- Forbidden result: a localhost URL is returned, public root/control UI is available without a signed session, a raw signed token is visible, or local mocks are treated as the phone/browser result.
- Evidence to capture: sanitized host/status codes, visible browser outcome, synthetic artifact marker/hash, generated-config key presence, external fetch proof, and exact remaining phone action if cellular audio cannot be completed in-session.
- Automation: `tests/release/test_remote_call_tunnel.py`, `tests/release/test_config_compiler.py`,
  `tests/release/test_install_summary.py`, `tests/release/test_voice_playground_dispatch_contract.py`,
  `qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js`, and
  `frontends/glass-drive-ui/tests/test_server.py`.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-15. Link generation, route denial, compiler, and helper
  regressions pass. The isolated lab off-LAN browser/media path and lab hairpin classification are
  NOT RUN.

## `REMOTE-004` - Public Voice Media, Not Page-Only Acceptance

- Requirement: a public call is usable only when the browser establishes a public ICE pair and
  delivers media; page render, settings load, signaling, or a listening TURN port alone is not
  acceptance.
- Risk covered: private-only LiveKit candidates or an unforwarded TURN relay range let the public
  page look healthy while every off-LAN call fails with `could not establish pc connection`.
- Preconditions: canonical local-prod runtime, public-safe synthetic call session/audio, public
  Playground and LiveKit DNS, and an independently routed browser path.
- Steps:
  1. Run the public Playground browser through an off-LAN SOCKS path and disable non-proxied UDP so
     the test cannot silently use the LAN.
  2. Start the real call with a fake microphone WAV and assert the LiveKit client selects TCP media.
  3. Correlate the selected public candidate and external peer class in LiveKit logs, worker join,
     expected STT transcript persistence, and targeted DB cleanup.
  4. Force TURN/TLS separately when it is claimed as fallback; require a selected relay pair, not
     only a relay candidate or successful TLS handshake.
  5. Probe the same public hostname without the off-LAN proxy and classify a same-Wi-Fi timeout as
     NAT loopback/split-DNS work, not as an application regression.
- Expected result: off-LAN browser and TCP media connect, the worker receives the synthetic audio,
  expected transcript persists once, and all synthetic records are removed. Same-Wi-Fi status is
  reported independently.
- Forbidden result: accepting HTTP `200`, loaded voice settings, WebSocket signaling, private-only
  server candidates, or a TURN/TLS allocation with no selected relay pair as proof of a call.
- Evidence to capture: sanitized selected-pair protocol/candidate types, worker/session presence,
  transcript match/count, cleanup counts, public runtime config alignment, and same-Wi-Fi result.
- Last run: NOT RUN for this public candidate. Acceptance requires an isolated lab edge/router,
  synthetic account, selected public media pair, fixture transcript, and exact cleanup evidence.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Remote Access. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `REMOTE-UC-001` | On CLI/status, browser origin, tunnel config, voice origin, verify that remote/local network access exposes only supported surfaces and reports disabled/degraded states truthfully. | owning requirement for `REMOTE-001` / `REMOTE-001` | CLI/status, browser origin, tunnel config, voice origin | Source, owning requirement doc, case steps, logs, fixture state, generated config, and shipped artifact evidence that apply to REMOTE-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS-AUTOMATED/PARTIAL 2026-07-15; contracts pass, isolated lab user path NOT RUN |
| `REMOTE-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `REMOTE-002` / `REMOTE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, fixture state, generated config, and shipped artifact evidence that apply to REMOTE-002. | The user sees an honest setup, retry, or degraded-state result for REMOTE-002; no fake success is accepted. | PASS-AUTOMATED/PARTIAL 2026-07-15; public-safety contracts pass, isolated lab report NOT RUN |
| `REMOTE-UC-003` | After creating the synthetic public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `REMOTE-002` / `REMOTE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, fixture state, generated config, and shipped artifact evidence that apply to REMOTE-002. | REMOTE-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT RUN pending isolated lab evidence |
| `REMOTE-UC-004` | From an isolated off-LAN browser, open a synthetic channel call URL and one fixture GlassHive workspace/artifact link. | `REMOTE-003`, `REMOTE-004` | Synthetic channel, isolated external browser, lab edge, Watch / Steer | Generated env, selected ICE pair, lab edge state, logs, fixture ref summary, external checks | Public call connects with delivered media and opaque GlassHive links open; raw control paths remain closed. | NOT RUN pending isolated lab edge/router and synthetic account |
| `REMOTE-UC-005` | On the lab serving LAN, open the same public Playground hostname. | `REMOTE-003`, `REMOTE-004` | Isolated browser on lab LAN | DNS result, TCP/HTTPS timing, lab router hairpin/split-DNS fixture | The public hostname reaches a trusted HTTPS edge without changing the public/off-LAN path. | NOT RUN pending isolated lab router |

## Release Test Traceability

- `tests/release/test_remote_call_tunnel.py`
