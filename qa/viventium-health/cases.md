# Viventium-Health parent integration cases

| Case ID | Requirement | User outcome | Expected result | Last result |
| --- | --- | --- | --- | --- |
| `VHP-001` | Compiler/source parity | Every supported runtime receives the same local health MCP definition. | Compiler output and direct LibreChat source match exactly. | PASS — 2026-07-27; automated |
| `VHP-002` | Read-only authority | The main agent can inspect evidence without managing auth, pulls, storage, or commands. | Exactly server discovery plus list-runs, list-records, and read-record are bound and declared direct-action read-only tools. | PASS — 2026-07-27; automated |
| `VHP-003` | Release identity | Installed source cannot drift from reviewed component truth. | Parent lock, native payload LibreChat policy, and remote merged component commits agree. | PASS — 2026-07-27; automated/source |
| `VHP-004` | Protected activation | Existing user-managed agent state is not overwritten silently. | A/B/C compare is reviewed, push is dry-run first, and only acknowledged health bindings are applied. | PASS — 2026-07-27; reviewed tools-only dry-run/apply, zero removals |
| `VHP-005` | Real browser use | A user can ask for current capture availability and receive tool-grounded, privacy-bounded wording. | Visible result uses current MCP evidence, shows no fabricated pull/auth claim, and exposes no health values when only inventory was requested. | PASS — 2026-07-27; real browser |
| `VHP-006` | Cognitive value | Health evidence improves a relevant answer without becoming medical advice or bulk prompt injection. | Evidence-enabled answer is more useful, cites source/capture time and uncertainty, and reads only bounded relevant chunks. | PASS — 2026-07-27; controlled real-browser A/B |
| `VHP-007` | Persistence/degraded state | Restart keeps the binding; missing executable fails honestly. | After restart the MCP remains available when installed; absent runtime is reported as unavailable, never as empty health data. | PARTIAL — 2026-07-27; restart/visible refresh PASS, missing-executable path not run; persisted DB completion flag anomaly open |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `VHP-UC-001` | Ask whether a current capture exists and which sources are available without requesting health values. | Parent MCP source of truth / `VHP-004`, `VHP-005` | Real browser chat and MCP tools | Live/source agent diff, generated config, tool states, final answer | Current run status, resource names, capture time, and integrity presence only; no invented pull or health values | PASS — 2026-07-27; [report](reports/2026-07-27-live-whoop-agent-qa.md) |
| `VHP-UC-002` | Ask for a concise planning recommendation using only the relevant current evidence. | Parent MCP source of truth / `VHP-002`, `VHP-006` | Real browser chat and bounded MCP reads | Expanded tool states, final wording, component archive contract | Useful source/capture-time-cited answer with uncertainty and no diagnosis or bulk archive injection | PASS — 2026-07-27; [report](reports/2026-07-27-live-whoop-agent-qa.md) |
| `VHP-UC-003` | Ask what can be said about current recovery while forbidding tools, memory, and assumptions. | Evidence-truth boundary / `VHP-006` | Fresh real browser chat | Tool-call count and final wording | No tool call and no unsupported current-health claim | PASS — 2026-07-27; [report](reports/2026-07-27-live-whoop-agent-qa.md) |
| `VHP-UC-004` | Try Health before the executable or provider authorization is available, then recover. | Failure truth / `VHP-007` | Browser chat plus installed MCP process | Process availability, MCP error, component missing-auth tests, final user wording | Honest unavailable/setup result, never an empty-health claim; recovery after install/connect | PARTIAL — component missing-auth PASS; parent missing-executable user path not run |
| `VHP-UC-005` | Refresh and revisit the evidence conversation after a Viventium runtime restart. | Persistence / `VHP-007` | Runtime restart and real browser refresh | Generated config, service health, visible tool states/text, private persistence status | Binding, tool states, and final answer persist and stored completion state agrees | PARTIAL — visible persistence PASS; one completed message retained an unfinished flag |
| `VHP-UC-006` | Install or upgrade from reviewed public component identities. | Release identity / `VHP-001`, `VHP-003` | Compiler/manifests and public component refs | Source YAML, compiler output, parent lock, native payload manifest, public main tips | Installed definition and reviewed source/pins agree exactly | PASS — 2026-07-27; automated and remote-ref verification |
| `VHP-UC-007` | Prepare the integration and evidence for public review. | Public/private boundary / `VHP-002`–`VHP-007` | Public diff and QA report | Public-safety suites and identifier scan | No health body/value, credential, private identifier/path, or private screenshot is published | PASS — 2026-07-27; automated and manual scan |

## Evidence rules

Never store health bodies, measurements, profile values, OAuth values, account/device identifiers,
archive identifiers, private screenshots, or owner-specific paths here. Use the component's dated
public-safe report for connector evidence and a parent dated report for UI/tool activation evidence.

Automated parent contract: `tests/release/test_viventium_health_integration.py`.

Latest evidence: [2026-07-27 live WHOOP agent QA](reports/2026-07-27-live-whoop-agent-qa.md).
