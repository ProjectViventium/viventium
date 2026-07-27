# Viventium-Health parent integration cases

| Case ID | Requirement | User outcome | Expected result | Last result |
| --- | --- | --- | --- | --- |
| `VHP-001` | Compiler/source parity | Every supported runtime receives the same local health MCP definition. | Compiler output and direct LibreChat source match exactly. | PASS — 2026-07-27; automated |
| `VHP-002` | Read-only authority | The main agent can inspect evidence without managing auth, pulls, storage, or commands. | Exactly server discovery plus list-runs, list-records, and read-record are bound and declared direct-action read-only tools. | PASS — 2026-07-27; automated |
| `VHP-003` | Release identity | Installed source cannot drift from reviewed component truth. | Parent lock, native payload LibreChat policy, and remote merged component commits agree. | PASS — 2026-07-27; automated/source |
| `VHP-004` | Protected activation | Existing user-managed agent state is not overwritten silently. | A/B/C compare is reviewed, push is dry-run first, and only acknowledged health bindings are applied. | PENDING — live review required |
| `VHP-005` | Real browser use | A user can ask for current capture availability and receive tool-grounded, privacy-bounded wording. | Visible result uses current MCP evidence, shows no fabricated pull/auth claim, and exposes no health values when only inventory was requested. | PENDING — browser run required |
| `VHP-006` | Cognitive value | Health evidence improves a relevant answer without becoming medical advice or bulk prompt injection. | Evidence-enabled answer is more useful, cites source/capture time and uncertainty, and reads only bounded relevant chunks. | PENDING — owner-private A/B required |
| `VHP-007` | Persistence/degraded state | Restart keeps the binding; missing executable fails honestly. | After restart the MCP remains available when installed; absent runtime is reported as unavailable, never as empty health data. | PENDING — restart/degraded run required |

## Evidence rules

Never store health bodies, measurements, profile values, OAuth values, account/device identifiers,
archive identifiers, private screenshots, or owner-specific paths here. Use the component's dated
public-safe report for connector evidence and a parent dated report for UI/tool activation evidence.

Automated parent contract: `tests/release/test_viventium_health_integration.py`.
