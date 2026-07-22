# LiveKit Immutable Runtime Docker QA — 2026-07-21

## Summary

- Result: `PARTIAL` release acceptance; all bounded arm64 Docker cases in this report passed.
- Runtime: `livekit/livekit-server:v1.13.4@sha256:189f7c81b704a36642bc5c7e2d3e1ae83744627c11978a23a251bf19fbec64e0`.
- Upstream source revision: `0b3fd288e3ef3263ec475ba0d78cf3ad77459981`.
- Isolation: synthetic credentials, loopback-only high ports, private generated config/logs, one
  named container at a time, and no Viventium volume creation or deletion.
- Remaining gates: Intel execution, TURN/TLS selected-pair proof, headed microphone/Keychain/TCC,
  remote media, and final installed-artifact alignment.

The nested `livekit` checkout is a source-audit placeholder. It was not treated as the running
artifact. The Docker image has an immutable multi-architecture index and per-platform SLSA
provenance, but no publisher/Cosign signature was found; this report does not call it signed.

## Scope Run

| Case | Result | Actual evidence |
| --- | --- | --- |
| Exact pull | `PASS` | Docker resolved the exact v1.13.4 multi-architecture index digest. |
| First start | `PASS` | The container ran as `linux/arm64`; configured image, Viventium image label, and upstream source label matched the lock exactly. |
| Health | `PASS` | The loopback HTTP endpoint responded after startup. |
| Restart/reuse | `PASS` | Restart retained the same container identity and returned healthy. |
| Stale managed upgrade | `PASS` | A synthetic managed container with a stale source label was detected and replaced by the real launcher with the locked release. |
| External/unrelated preservation | `PASS` | A healthy container without Viventium ownership labels remained running; the launcher reused the endpoint and did not remove it. |
| Cleanup/storage boundary | `PASS` | All named synthetic LiveKit containers were removed, Docker volume count was unchanged, and no global prune ran. |
| TURN v1.13 migration | `NOT RUN` | Requires TTL-aware TURN credentials and selected relay-pair evidence, not only a listener. |
| Intel runtime | `NOT RUN` | Requires the single final disposable Intel acceptance machine or physical Intel Mac. |
| Headed microphone/Keychain/TCC | `NOT RUN` | Requires isolated headed macOS access with synthetic accounts and permission handling. |

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What defines acceptance? | Installer requirement 39, voice-component requirement 52, `MPV-025`, and `MPV-UC-025`. |
| Code owning path | What selects and validates the runtime? | The full-stack launcher exact image constant, release labels, existing-container identity guard, and stale replacement branch. |
| Docs and nested repos | Do source and runtime roles agree? | Yes. Requirement 52 keeps the nested LiveKit checkout as a placeholder and identifies the locked image as the running artifact. |
| Scripts or harnesses | What actually ran? | The real full-stack launcher with every unrelated service disabled, plus Docker pull/run/restart/inspect and loopback health. |
| Local/external prerequisites | What was available? | Recovered Docker Desktop on arm64; no personal provider account, microphone, TURN service, or remote network was used. |
| Logs | What corroborated behavior? | Private launcher evidence recorded stale replacement, exact start, unrelated-port reuse, and bounded cleanup. |
| DB/state/persistence | Was personal state involved? | No DB data was read or written. Docker volumes were inventoried and the count was unchanged. |
| Generated/shipped artifact | Was final release delivery proven? | Source and runtime lock alignment passed; final signed/notarized installed artifact remains unavailable. |
| Real user path | Which real path ran? | The Custom Settings Docker-backed Voice launcher path ran with synthetic loopback configuration. |
| Visible/delivered result | What did the operator receive? | Terminal output truthfully reported stale replacement, exact v1.13.4 startup, external reuse, and cleanup. |
| Not run / blocked | What remains? | Intel, TURN selected-pair, microphone/Keychain/TCC, remote media, and signed installed-artifact proof. |

## User-Grade Evidence

- Surface exercised: Custom Settings Docker-backed Voice through the real full-stack CLI launcher.
- Real user path: start the optional Voice runtime, restart it, upgrade a stale managed runtime, and
  start while a deliberately external healthy LiveKit endpoint owns the port.
- Visible outcome: the terminal reported the exact v1.13.4 start, stale managed replacement, safe
  external reuse, and final cleanup without a false healthy result.
- Expanded/detail state: Docker inspection showed the exact configured image, image label, upstream
  source label, `linux/arm64` platform, running state, and unchanged volume inventory.
- Persistence/reload result: a real container restart retained the same container identity and
  returned to a healthy loopback endpoint.
- Backend/log/DB confirmation: HTTP health and Docker inspect agreed with the launcher; no database
  or personal account state was involved.
- Final model/runtime wording check: source/docs/log wording says immutable digest and SLSA
  provenance, not publisher-signed, and identifies the unrun platform/permission cases.
- Substitution check: automated tests support the result, but the actual Docker image and launcher
  paths were run. This does not substitute for the unrun Intel, TURN, microphone/TCC, or installed
  signed-artifact paths.

## Traceability

`Docker-backed Voice -> installer and voice-component requirements -> MPV-UC-025 -> MPV-025 -> exact image and safe upgrade behavior -> Docker/launcher evidence -> Intel, TURN, and headed permission gaps`

## Automated Evidence

- `tests/release/test_optional_runtime_provenance.py`
- launcher shell syntax validation
- `release/optional-runtime-components.json`

## Recovery And Cleanup Safety

The Docker content store initially reported an I/O-corrupt blob after earlier disk exhaustion. A
complete secret-excluding continuity snapshot was created and independently validated before one
Docker Desktop restart. Previously running Viventium services were inventoried; services without an
automatic restart policy were started again explicitly and reached their normal running/startup
health states. Cleanup removed only exact synthetic QA image tags and named QA containers. No
volume, owner data, unrelated image, or personal configuration was deleted.

## Findings

- Fixed defect: the runtime previously used the floating `livekit/livekit-server` repository name,
  while the nested placeholder SHA did not govern executing code.
- Fixed upgrade risk: a stale Viventium-managed LiveKit container is no longer silently reused.
- Preserved custom path: an unrelated healthy external endpoint is reused without deletion.
- Residual risk: v1.13 removed compatibility for TURN authentication without TTL; selected relay-pair
  acceptance is still required before declaring TURN upgrades ready.
- Release status remains `PARTIAL` because the platform, permission, remote-media, and final
  installed-artifact cases listed above were not run.

## Public-Safety Review

- No username, home path, hostname, provider credential, account, conversation, private screenshot,
  or secret-bearing command is included.
- Raw configs, launcher logs, continuity data, and host storage evidence remain outside the public
  repository.
- All displayed identifiers are public component versions/digests or synthetic QA classifications.
