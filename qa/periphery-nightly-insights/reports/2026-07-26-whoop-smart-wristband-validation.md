# WHOOP Smart Wristband Integration Validation

Date: 2026-07-26

Status: official contract, authentication boundary, and community connector validation complete;
owner export and OAuth data remain not run

Scope: research and isolated tests only; no product code, live Viventium configuration, WHOOP app,
developer account, credential, or owner health data was changed

## Outcome

WHOOP is a strong second direct connector after Oura and can use the same web/backend architecture.
The owner continues syncing the wristband through the WHOOP mobile app, but Viventium does not need
its own iOS or Android application to use the official WHOOP cloud API. One development app can be
used immediately with up to ten WHOOP members before app approval.

WHOOP cannot be validated with the same public synthetic-data technique used for Oura. Its documented
test-data endpoint belongs to the separately gated Healthcare Partner API and is available only in
non-production partner environments. The honest validation ladder is therefore:

1. official OpenAPI, scope, authentication, pagination, rate-limit, and webhook contract validation
2. a private mobile-app CSV export cognitive A/B test
3. a one-owner official OAuth connection using the actual wristband account
4. a real sync, correction, deletion, webhook, refresh, revoke, and restart test

A current community WHOOP MCP implementation was also audited. It is a useful reference and much
stronger than the Oura community connector previously rejected, but it is **not approved for direct
Viventium adoption as-is** because of transport, scope, privacy-contract, export, dependency-security,
and version-reporting gaps.

## Official Integration Contract

### Developer access and cross-platform behavior

- The standard developer API uses OAuth 2.0 authorization code flow and user consent.
- A WHOOP membership is required to create a developer app.
- Development begins immediately with a ten-member limit; approval is required beyond ten members.
- The `offline` scope is required to receive a rotating refresh token.
- The official REST API is cloud/backend based. It works for an owner who uses either the iOS or
  Android WHOOP app; a Viventium mobile bridge is not required.
- Phone/app sync remains an upstream prerequisite. A cloud connector cannot make unsynced wristband
  data appear.

Sources:
[developer overview](https://developer.whoop.com/docs/developing/overview/),
[app approval](https://developer.whoop.com/docs/developing/app-approval/),
[OAuth](https://developer.whoop.com/docs/developing/oauth/).

### Scopes and resources

The reviewed official OpenAPI 3.0.1 description contains 20 paths, 19 of them v2 paths. The core
read scopes are:

| Scope | Official data family | WHOOP pilot decision |
| --- | --- | --- |
| `read:cycles` | physiological cycles and day Strain | Request |
| `read:recovery` | recovery score, HRV, and resting heart rate | Request |
| `read:sleep` | sleep performance and stage durations | Request |
| `read:workout` | workouts, activity Strain, and heart-rate summaries | Add only if the accepted questions need it |
| `read:profile` | name and email | Exclude by default |
| `read:body_measurement` | height, weight, and max heart rate | Exclude by default |
| `offline` | refresh-token access | Request for a continuous pilot |

The official collection paths cover cycles, recoveries, sleeps, and workouts. Profile and body
measurement are separate singleton resources. Collection requests accept ISO-8601 `start` and `end`,
use an opaque `nextToken`, default to ten records per page, and allow at most 25 records per page.

Source: [WHOOP API reference](https://developer.whoop.com/api/).

### Data semantics that Viventium must preserve

WHOOP is cycle-oriented rather than a simple calendar-day feed. Recovery is associated with sleep,
and sleep can cross midnight. Viventium must preserve:

- WHOOP cycle, sleep, recovery, and workout identifiers and relationships
- UTC start/end plus the recorded timezone offset and derived local wall time
- `score_state`, including pending or unscorable records, rather than coercing missing scores to zero
- vendor meanings and units for Strain, Recovery, sleep performance, HRV RMSSD, and other metrics
- vendor update time, ingestion time, correction lineage, and deletion tombstones

A single “daily WHOOP score” normalized against Oura or another vendor would destroy meaning and is
not an acceptable canonical model.

### Rate limits and pagination

WHOOP documents two default client limits:

- 100 requests per minute
- 10,000 requests per day

Limit/remaining/reset headers are returned and an exceeded limit produces HTTP 429. A 30-day initial
backfill must follow every `next_token` until empty rather than assuming the first page is complete.

Sources: [rate limits](https://developer.whoop.com/docs/developing/rate-limiting/),
[pagination](https://developer.whoop.com/docs/developing/pagination/).

### Webhooks and reconciliation

WHOOP v2 webhooks use UUIDs and publish `updated` and `deleted` events for workout, sleep, and
recovery. They do not contain the authoritative biometric record; the consumer fetches that record
from the API. Cycle/day-Strain and body-measurement webhooks are not currently available.

The connector must:

- validate `X-WHOOP-Signature` against the timestamp plus raw body using HMAC-SHA256
- return a successful response quickly and process asynchronously
- tolerate duplicate deliveries using `trace_id`
- process delete events and preserve a tombstone
- run reconciliation because deliveries may be missed
- poll cycle/body resources because those event types are absent

WHOOP retries failed delivery five times over roughly one hour. Its own documented real-data test is
useful for the owner pilot: create a short past activity to trigger `workout.updated`, edit an earlier
sleep boundary by one minute to trigger sleep/recovery updates, then revert or delete the synthetic
activity and confirm the corresponding correction/deletion path.

Source: [WHOOP webhooks](https://developer.whoop.com/docs/developing/webhooks/).

### Official exports and phone-platform bridges

The official export is requested from the WHOOP mobile app on either iOS or Android. WHOOP emails a
download link within 24 hours; the link expires after seven days. Standard exports contain multiple
CSV files covering physiological cycles, Recovery, RHR, HRV, Strain, heart rate, sleep/stages, SpO2,
skin temperature, workouts, and journal entries. This is the best no-token cognitive-value test, but
it is not a dependable automated daily ingestion mechanism.

WHOOP also exports selected data to Apple Health and Android Health Connect. These bridges are useful
for a later vendor-neutral mobile lane but are lossy:

- Apple Health currently omits WHOOP HRV; WHOOP uses RMSSD while Apple Health uses SDNN.
- Health Connect omits WHOOP Age, Pace of Aging, VO2 Max, and regulated Heart Screener/Blood Pressure
  data; availability also varies by membership.
- Both platform integrations can create duplicate activities when several sources write the same
  event and require phone permissions to be re-enabled after reinstall.

Sources: [WHOOP export](https://support.whoop.com/s/article/How-to-Export-Your-Data),
[Apple Health integration](https://support.whoop.com/s/article/Apple-Health-Integration?language=en_US),
[Health Connect integration](https://support.whoop.com/s/article/Google-Health-Integration-For-Android).

## Isolated Official API Validation

No credential or owner data was used.

| Check | Actual result | Meaning |
| --- | --- | --- |
| Current OpenAPI parse | PASS; OpenAPI 3.0.1, 20 paths, 19 v2 paths, six read scopes | The current contract is machine-readable and suitable for generated contract tests |
| Core resource inventory | PASS; cycles, recoveries, sleeps, workouts, profile, and body measurement present | Supports the planned evidence families |
| Pagination contract | PASS; default ten, maximum 25, ISO start/end, opaque next token | Backfill must be explicitly paginated |
| Missing bearer token | PASS; all six representative resource probes returned HTTP 401 | Endpoints fail closed instead of returning owner data |
| Invalid synthetic bearer token | PASS; representative profile/body probes returned HTTP 401 with no data | Arbitrary strings do not unlock a sandbox or production data |
| Ordinary developer synthetic sandbox | NOT AVAILABLE | The documented add-test-data path is a healthcare Partner API facility, not a normal developer sandbox |
| Real owner OAuth/data | NOT RUN | Requires an app registration and explicit user authorization |

The public Oura sandbox therefore remains the better unauthenticated transport prototype. WHOOP's
actual semantics must be validated with the official export and then an authorized owner account.

## Community WHOOP MCP Audit

### Candidate and evidence

The isolated candidate was
[AshwanthramKL/whoop-mcp](https://github.com/AshwanthramKL/whoop-mcp), version 0.8.5,
commit `a34d3eb5bc37fdc32127caf17e4483ddd217f434`. It is a pre-1.0, single-user,
local stdio MCP using only WHOOP's official v2 API.

Validated strengths:

- 198 unit/contract tests pass after the missing Parquet dependency is installed.
- Ruff and mypy pass.
- MCP initialize and tool discovery work at protocol version `2025-06-18`.
- A no-credential `get_whoop_auth_status` call returns the truthful `no_tokens` state.
- Created cache, log, and encryption-key files use owner-only `0600` permissions.
- The connector is read-only toward WHOOP, preserves score state and units, caches locally, models
  corrections/idempotency, and returns structured errors rather than raising through MCP.

### Adoption blockers

| Finding | Evidence | Viventium consequence |
| --- | --- | --- |
| Transport mismatch | The package explicitly supports stdio only | It is not a drop-in user-created Viventium remote HTTP/SSE MCP; adopting it would need a managed local-component boundary or a reviewed remote wrapper |
| Over-broad OAuth grant | Its setup script hard-codes profile, body measurement, cycles, recovery, sleep, workout, and offline scopes | Violates the proposed least-privilege pilot and exposes name/email and body data without an accepted use case |
| Parquet packaging failure | Clean `.[dev]` install fails one test because `pyarrow` is absent from published project/dev dependencies | The advertised complete test/install path is not reproducible as documented |
| Vulnerable full-source dependency | Source `requirements.txt` pins `pyarrow>=15,<19`; resolution selected 18.1.0, affected by high-severity `PYSEC-2026-113`, fixed in 23.0.1 | The documented full requirements/Parquet path cannot pass a current dependency audit under its version cap |
| Privacy contract drift | Privacy docs say only WHOOP is contacted, but `health_check(live=True)` contacts PyPI by default for updates | Network behavior is broader than the stated privacy contract, even though no health payload is sent to PyPI |
| Unsafe agent export surface | `export_whoop` accepts an arbitrary path and overwrite flag; exported health files are not forced to owner-only permissions or encryption | Do not expose this tool to the Main Agent without a governed private-artifact boundary |
| Misleading handshake version | MCP initialize reports SDK version `1.28.1` while the connector is version 0.8.5 | Client/runtime evidence cannot reliably prove the installed connector version from `serverInfo` |
| Callback uncertainty and busy wait | Default callback is plain localhost HTTP and the setup loop spins continuously until callback | Must be tested against the current WHOOP redirect policy and corrected before user-grade performance acceptance |
| Mock-only upstream tests | The suite mocks all WHOOP HTTP interactions by design | Good regression evidence, but no substitute for a real owner sync, token rotation, or API correction event |

The dependency finding is supported by
[OSV PYSEC-2026-113](https://osv.dev/vulnerability/PYSEC-2026-113), which affects PyArrow 15.0.0
through 23.0.0 and identifies 23.0.1 as the fixed release. CSV/JSONL and core API access do not need
PyArrow. The advisory's documented trigger involves reading a crafted Arrow IPC file with
pre-buffering; exploitability through this connector's Parquet-writing tool was not demonstrated.
This does not invalidate the whole design, but the affected dependency and incompatible version cap
still block adopting the current advertised full export installation unchanged.

The package's separate `whoop-insights` skill was not installed. It adds baseline, anomaly, and
correlation interpretation beyond the raw connector. Viventium should own that inference under its
health-pressure evidence, humility, and surfacing contracts rather than importing a connector's
analysis behavior.

### Community decision

Use this candidate as a source of regression cases and as evidence that a read-only local WHOOP MCP
is feasible. Do not install it into the live runtime or treat it as the production connector until the
blockers above are resolved and its exact transport is reconciled with Viventium's managed MCP
boundary. Private-API MCPs that expose hundreds of reverse-engineered read/write endpoints are a
stronger rejection: they bypass the official stable API, expand mutation risk, and create account and
terms-of-use exposure.

Also avoid the similarly named `@whop/mcp` package: **Whop** is a different commerce platform, not the
WHOOP wearable company.

## Proposed Actual WHOOP Evaluation

### W1 — private export cognitive A/B

1. Request a standard export from the WHOOP mobile app.
2. Use 14–30 days of the cycles, sleep, and workout CSVs in private runtime storage.
3. Do not include profile, email, GPS, journal responses, or regulated WHOOP MG data unless the user
   explicitly selects a question that requires them.
4. Compare Viventium answers without and with the export for sleep consistency, recovery/workload
   timing, missing-data honesty, and today's planning.
5. Require each health-data claim to cite source file, record date/time, metric, and WHOOP score state.
6. Score intelligence, relevance, usefulness, alignment, evidence traceability, uncertainty, latency,
   and privacy. More numbers without better judgment is not a pass.
7. Delete the private test copy and retain only sanitized counts, hashes, status, and conclusions.

### W2 — one-owner official OAuth connector

1. Register a development app and exact callback; confirm the current dashboard accepts the chosen
   local-development or HTTPS callback before promising a localhost flow.
2. Request `read:cycles read:recovery read:sleep offline`. Add `read:workout` only for an accepted
   workout use case. Do not request profile/body by default.
3. Backfill 30 days through every pagination token and preserve WHOOP cycle/sleep/recovery joins.
4. Expose only bounded status, cycle, recovery, sleep, and optional workout reads through the MCP
   boundary. Keep sync/refresh internal; exclude arbitrary export paths and analysis skills.
5. Complete an actual wristband-to-app-to-WHOOP-cloud sync and prove the new record appears through
   the connector with measurement and ingestion times.
6. Follow WHOOP's own webhook test: add a short past activity, edit a prior sleep boundary by one
   minute, observe update events and fetched authoritative objects, then revert/delete and verify the
   correction/tombstone path.
7. Test expired access token, rotating refresh, revoked grant, missing scope, 401, 429, 5xx, delayed
   score, unscorable record, duplicate/missed webhook, reconciliation, timezone travel/DST, restart,
   disconnect, and raw/derived deletion.
8. Repeat the W1 cognitive A/B through the actual connector and verify ordinary unrelated chat does
   not retrieve WHOOP evidence.

### W2 acceptance gate

- Actual data appears only after the real phone/app sync and the UI states freshness truthfully.
- Recovery is associated with the correct sleep/cycle across midnight and timezone changes.
- Pending/unscorable/missing data never becomes zero, “bad,” or a fabricated baseline.
- The connector requests no unapproved PII or body scope and exposes no email, raw GPS, journal entry,
  token, or client secret.
- Webhook signature, duplicate, delete, missed-delivery, and reconciliation cases all pass.
- Token refresh and revoke work across process restart without broadening scopes.
- All raw and derived data can be disconnected/deleted through a governed product action.
- The answer is materially more useful and still non-diagnostic; proprietary WHOOP scores remain
  vendor facts, not clinical truth or cross-vendor equivalents.

## Final Decision

- **Official WHOOP API:** recommended second direct adapter and a valid alternative first adapter if
  the owner has a WHOOP rather than an Oura device.
- **No-code value test:** recommended now through the official iOS/Android mobile export.
- **Mobile bridge:** unnecessary for direct WHOOP cloud access; useful only for later Apple
  Health/Health Connect breadth, with known metric loss.
- **Current audited community MCP:** promising laboratory reference, not safe or architecture-clean
  enough for direct Viventium adoption unchanged.
- **Private/reverse-engineered WHOOP APIs:** reject for production.
- **Real connector completion:** not claimed until W2 runs with an explicitly authorized owner account.
