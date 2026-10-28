# Phone and local call entry — 2026-10-27

## Summary

- Result: **PARTIAL**; source repairs, loaded artifact identity and bounded failure-path recovery pass. Successful signed phone/local call and audible acceptance remain blocked or NOT RUN.
- Build/source under test: Core call readiness, frontend/Auth, helper local entry, DNS diagnostics and seven response-lifetime consumers.
- Runtime/artifact under test: rebuilt frontend/API, installed helper and actual served development source checked in the dated evidence below.
- Environment: local development with existing sign-in, public DNS and phone/OS prerequisites.
- Tester: agent-operated Chrome/CLI checks and independent Opus source review.
- Related change: use existing local call entry and preserve deadlines through complete response reads.
- QA mode and authorizing instruction: blast-radius; surgical phone/local call repair and confirmed consumers.
- Selected cases and causal relevance: local-call-entry and telegram-call-public-edge, including denied and stalled-body paths.
- Deferred / unselected cases (NOT RUN): successful signed call, audible response, actual phone networks, hardware recovery, worker join, transcript persistence, endurance and latency.

## Scope Run

| Case | Result | Evidence | Limit |
| --- | --- | --- | --- |
| local-call-entry source/artifact | PASS | Route/client/helper checks, build and served-source identity | Not actual helper-menu-to-audible-call acceptance. |
| local-call-entry degraded/recovery | PASS for recorded paths | Real Chrome expired link and controlled stalled-body recovery | Controlled fixture is not an authenticated call. |
| telegram-call-public-edge | BLOCKED | Stale public DNS and existing registrar/phone access gates | No external DNS save or successful phone call. |
| local-call-entry successful speech | BLOCKED | Ordinary local sign-in not completed | Audible response and dependent continuation checks NOT RUN. |

## Natural User Use Case Checklist Run

| Use case | Natural action | Surface | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| local-call-entry navigation | Open local chat and preserve normal Login destination | Chrome | PASS for signed-out navigation | Existing Login retains destination; no automatic capture | Rebuilt bundle and matching source | Helper-menu interaction and successful sign-in remain open. |
| local-call-entry denial/recovery | Open invalid launch; stall a response after headers | Actual Playground and controlled Chrome fixture | PASS for failure paths | Expired-link screen; bounded recovery page | Typed denials, source maps and request counts | Not a signed call or audio test. |
| telegram-call-public-edge phone | Start a call from phone on Wi-Fi and cellular | Phone path unavailable | BLOCKED | No successful call observed | DNS/auth/OS prerequisites recorded | Signed call and audible acceptance remain PARTIAL overall. |

## Traceability

Phone/local entry → [Voice](../../../docs/requirements_and_learnings/capabilities/voice.md) and [remote access](../../../docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md) → start an ordinary authorized call → [local-call-entry and telegram-call-public-edge](../cases.yaml) → reachable launch, native worker, speech and durable transcript → source/artifact and recorded browser failure proof below → successful sign-in, public edge and audible call acceptance remain open.

## Full-View Evidence Checklist

| Evidence surface | Recorded result and limit |
| --- | --- |
| Requirement and use case | CORE-005/007/008/009, CC-057 and PW-052; local and phone call entry. |
| Code owning path | Call readiness/launch, frontend Call/Auth, helper Open, DNS/status and body-read consumers. |
| Docs and nested docs/repos | Voice/remote-access owners, Voice case bank and component call contracts. |
| Scripts or harnesses | Causal route, client/Auth, Swift, DNS/status, body-deadline and direct CSP checks below. |
| Prerequisites | Internal runtime responds; ordinary local sign-in and external DNS/phone OS access remain unresolved. |
| Logs and DB/state/persistence | Typed launch denial, unchanged configuration/pins and private source/process receipts support bounded observations. |
| Generated/shipped artifact | Rebuilt frontend, installed signed helper, bootstrap/CSP/source maps and served client chunk checked. |
| Real user path and visual/UX | Chrome Login navigation, expired-link screen and controlled failure recovery observed. |
| Not run / blocked | Actual helper menu, signed local/phone call, audio, microphone recovery and dependent persistence remain open. |

## User-Grade Evidence

- Surface exercised: Chrome, installed Playground failure path, CLI and installed helper artifact; controlled browser fault fixture separately identified.
- Real user path: open the normal local destination, encounter ordinary Login, open an invalid call link and inspect bounded recovery.
- Visible outcome: Login preserves destination; invalid authority shows the expired-link screen; stalled-body fixture recovers after bounded attempts.
- Expanded/detail state: typed route/status failures and generated/served identity inspected; actual helper menu could not be read.
- Persistence/reload result: rebuilt/served identities and unchanged saved settings checked; successful call transcript persistence NOT RUN.
- Backend/log/DB confirmation: active source maps, call exchange denial, listener health and existing auth/DNS diagnostics support only the recorded failure paths.
- Final model/runtime wording check: health and tests do not establish a signed call, phone reachability, audio or cognitive parity.
- Substitution check: source, artifact and controlled fixture evidence cannot replace required authenticated phone/local call and audible acceptance.

## Automated Evidence

The dated original and follow-up selections remain below, including 62 call routes, 55 client/Auth checks, helper/DNS consumers and the 57 + 58 body-read selections with one CSP consumer. Overlapping selections are not added. No new product test or runtime activation was performed for this report organization.

## Findings

The following original dated details are retained; reorganizing them does not change their evidence scope or result.

### Summary

- Result: **PARTIAL**. Source repairs and focused regression checks pass; required successful phone and local call acceptance remains blocked by existing authentication prerequisites.
- QA mode: **blast-radius**, authorized investigation and surgical repairs of the phone/local call path and confirmed consumers.
- Candidate: active development checkout; fresh Core process, rebuilt frontend and installed source-built macOS helper. Exact source and process receipts are retained privately. This is not a release or full Voice acceptance claim.
- Models, prompts, cognitive configuration and component pins were not changed by this batch. Concurrent Telegram work was preserved.

### Delivered contract

| Area | Change | Actual evidence | Remaining gap |
| --- | --- | --- | --- |
| Call readiness | Check the configured internal Playground health and build. Keep the independently selected public browser launch URL. | Five new causal cases fail before the source fix; all 62 call-route tests pass after. Fresh Core started after the fix. | Successful authenticated public-web call after the external DNS correction. |
| Local entry | Add **Call on this Mac…** to the supported legacy helper. Open the normal local chat, preserve normal sign-in, focus the existing Call control. A real click or Enter remains required. | 55 client/Auth checks pass. Actual Chrome signed-out journey preserves the original destination through Login. | Actual helper menu → authenticated focused Call → audible response. |
| Shared helper Open | Use a reachable loopback address for the local web app instead of a discovered LAN address. Retain the native runtime address. | Current listeners are loopback-only; local HTTP succeeds and actual Chrome LAN navigation is refused. The causal compiled Swift check fails before correction; 4 helper checks and the full Swift build pass after. Updated helper installed and running; signature verification passes. | Native helper menu interaction is not proved by its running process. Computer Use could not read this menu-only app. |
| DNS diagnostics | Observe each managed local public IPv4 hostname, separately from runtime health. Preserve local services, mappings and URL exports. | The earlier unchanged bank has 199 passes. After independent review corrections: 28 focused DNS/status cases and 3 direct summary-consumer cases pass. Actual CLI status identifies the stale records. | The registrar's existing MFA prevented saving the three corrected records. No DNS repair is claimed. |
| Startup compatibility | Status never waits on the lifecycle lock merely to save optional DNS diagnostics. Its existing exit code and healthy field retain runtime-only meaning. | Held-lock and exit-code cases fail before correction. Busy/unwritable storage and a newer lifecycle writer are covered. One interface snapshot is shared. | A later normal startup can reuse these checks; no extra restart was needed for this diagnostic source change. |
| Rejected launch | Invalid or expired launch authority must not start capture or work. | Actual Chrome shows **This call link has expired** and the fresh Playground logs show exchange rejection. No valid capability was supplied. | Used valid-link replay is a separate acceptance check, not substituted by this invalid-link test. |

The served frontend main bundle matches the rebuilt artifact and contains the focus-only entry.
Canonical product configuration and component-lock hashes are unchanged. Helper supervision metadata
can change through the supported installer and normal helper lifecycle.

### Requirement and user-case trace

`Voice → CORE-005 / CORE-007 / CORE-008 / CORE-009 / CC-057 / PW-052 → local-call-entry and telegram-call-public-edge → reachable, authorized call with ordinary user consent → evidence above → acceptance gates below.`

Owners: [Voice capability](../../../docs/requirements_and_learnings/capabilities/voice.md),
[Remote access](../../../docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md),
[Voice cases](../cases.yaml). Core call routes and launch service, helper URL selection, frontend
CallButton/Auth, remote-edge status and install-summary consumers were inspected. Historical prompt,
DB, call-admission and network evidence is retained privately, not copied into this public report.

### NOT RUN / blocked acceptance

| Required path | Status | Exact reason |
| --- | --- | --- |
| Save external DNS and verify all unaffected records | BLOCKED | Existing registrar step-up authentication; the credential manager is OS-locked. No record save succeeded. |
| Phone Telegram and web Call on cellular and Wi-Fi | BLOCKED | Correct public DNS and actual phone access are required. Phone Mirroring is OS-locked. |
| Authenticated local Call, microphone denial/recovery, End/reconnect and valid replay | BLOCKED | The local web app requires an existing sign-in. No credentials were reset and no owner session was manufactured. |
| Audible speech, worker join, linked transcript and persistence | NOT RUN | These depend on a successful authorized call. Health, source tests and model review do not substitute for them. |
| Full-project suites, provider evals and latency benchmarks | NOT RUN | Outside this repair batch's blast radius; no model or prompt behavior changed. |

### Independent review

Opus 5.5 reviewed the concrete source changes, source evidence, original requirements and causal tests.
Its material status-lock and exit-code findings were fixed. Its shared-origin concern was resolved
against actual listener/browser evidence by correcting the existing helper Open address, rather than
moving the new call entry to an unreachable LAN address. The final delta review approved these source corrections subject to updating the existing native-helper loopback assertion; that exact test now passes. Six affected helper-health consumer checks also pass. Review is supporting evidence only.

No Git writes or public release were performed. Raw prompts, credentials, account/device identity,
private paths, DNS account records and screenshots are excluded from this report.

### Follow-up — 2026-10-28

**Current result: source repairs are active; real-call acceptance remains PARTIAL.**

| Further finding | Surgical correction | Evidence | Limit |
| --- | --- | --- | --- |
| A response could send headers, then stall after its timeout had already been cleared. | Keep the existing deadlines through body reads in bootstrap, canonical hydration and the state proxy. Give the launch-exchange proxy the existing proxy deadline and incoming browser cancellation. | Ten causal failures before correction; 57 affected cases and one direct CSP consumer pass. | These are request-lifetime guards, not faster model inference or successful audio proof. |
| A stalled browser state read could block later keepalives. The settings and task-action readers had the same defect. | Keep their existing deadline/cancellation guards through body parsing; preserve malformed-body fallbacks and release in-flight state. | Eight causal failures before correction; 58 affected cases pass. The hook test proves the next existing keepalive recovers after timeout. TypeScript passes. | No new polling, requests, retry policy, authority, model or orchestration layer. |
| A healthy health endpoint could conceal an old uncommitted build. | Verify the actual active output against current source. | The served bootstrap script/CSP match the candidate. Source maps from the active development output match all six remaining source files; the served client chunk matches that output. Invalid-authority requests return the existing typed denial. | Commit ID or file presence alone is not used as current-build proof. This remains a development candidate, not a release. |
| The browser needed actual failure-path proof. | Run the exact candidate bootstrap in real Chrome with controlled normal, final-rejection and headers-then-stalled-body responses. | Normal and final rejection each use one request. Three stalled attempts abort at about 5 seconds each and show the recovered fixture page after about 15.8 seconds. Actual loaded Playground also shows the expired-link screen for invalid launch authority. | The private fault fixture is not an authenticated call. It proves bounded failure recovery, not cellular reachability or audio. |
| Existing sign-ins prevent successful local/public call QA. | Use ordinary saved sign-in and registrar verification; do not manufacture sessions or reset credentials. | One saved local-login attempt is rejected; Core confirms a password mismatch. The registrar requests a current SMS, but Messages shows no new received chat during that request window and its latest matching code predates the attempt. | DNS edits have not been committed. Credential manager and phone mirroring still require normal OS unlock. |

Opus approved all seven source corrections after reviewing the concrete source, causal tests,
requirements and evidence. Its loaded-artifact evidence gate is satisfied by the source-map and
served-asset checks above. No repeated unchanged review or broad test sweep was run.

The original Core, frontend/Auth, helper and DNS evidence remains valid. Full suites, provider evals
and latency benchmarks remain NOT RUN. Successful signed call, audible response, actual phone
cellular/Wi-Fi, microphone recovery, worker join, transcript persistence, reconnect/End and valid
used-link replay remain blocked or NOT RUN as recorded above. Separate local background-provider
authentication failures are retained in private diagnostics; this report does not claim cognitive
parity. Saved agent selections were preserved, including differences from source configuration.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies or credential-bearing commands.
- [x] No private prompts, conversations, media, screenshots, personal emails, accounts or customer data.
- [x] No conversation, message, call, chat, database or provider request identifiers.
- [x] No machine names, private hostnames, absolute local paths, raw logs or runtime dumps.
- [x] Private evidence is represented only by sanitized observations, counts, dates and conclusions.
