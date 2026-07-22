# Release gate matrix audit — 2026-07-20

## Summary

The current candidate is **not release-ready**. Source-level release enforcement is strong and the
focused contract suites pass, but the operational signed/notarized release is `BLOCKED`, the full
physical accessibility and fault matrices are incomplete, and end-to-end component delivery
alignment is `FAIL`: all lock refs equal current nested `HEAD`, but LibreChat and both playgrounds
contain reviewed working-tree fixes that no commit, parent pin, or shipped artifact represents.

This was a read-only audit of release code and candidate state in an isolated worktree, except for
the public-safe QA status corrections linked below. It did not install into a personal runtime,
change accounts or Keychain state, publish a release, or perform any commit, push, PR, or cloud
mutation.

### 2026-07-21 post-audit closeout amendment

- The exact current local source passed the full parent suite with `1,524 passed, 10 skipped in
  305.19s` after the symlink-staging and structured Voice error corrections. The run reused existing
  read-only dependencies and removed its one temporary Playwright link.
- The nested status is not clean: LibreChat has 11 dirty paths, `agents-playground` has 2, and
  `agent-starter-react` has 2. The 11 parent refs match repository `HEAD`, not the current working
  content.
- The parent `.gitignore` previously failed to ignore nested-repository symlinks, whose targets can
  contain producer-local paths. A failing regression reproduced that staging hazard; root-anchored
  symlink-safe rules now pass for every `components.lock.json` path.
- The Voice missing-assistant path now uses structured `voice_agent_required` metadata instead of
  coupling the client to the English server sentence; parent, API, and client focused tests pass.
- These corrections improve source safety only. They do not change the overall `NO-GO` verdict or
  substitute for commit/pin/artifact alignment and installed user-path proof.

### Independent corrected-delta review

A visible review-only Claude Desktop pass used Fable 5 with Extra effort against the attached
isolated candidate after the corrections above. It independently exercised the ignore rules,
inspected the Voice server/client/tests and current delivery statements, and reported **no new
actionable findings** in the corrected delta. It confirmed OpenClaw is optional preserved work and
is not part of the Easy Install/runtime-parity critical path.

The reviewer initially carried forward two older concerns, then retracted both after inspecting the
owning paths:

- `stapler validate` belongs to the protected producer workflow, which staples and validates the
  bootstrap and payload apps. Adding `xcrun` to the consumer bootstrap would violate the
  no-developer-tools contract; the consumer correctly verifies signature, exact Team ID, signed
  release policy, and Gatekeeper assessment.
- The first-run account intent is carried across login in the validated `redirect_to` URL. The
  session-scoped pending key only survives same-tab shell remount/URL cleanup and is cleared on
  dismissal, preventing a persistent onboarding nag.

The corrected independent blocker chain is unchanged from the evidence here: uncommitted nested
fixes -> stale committed manifest -> absent signing authority -> no signed/notarized artifact ->
unrun exact installed lifecycle and parity proof.

## Result meanings

- `PASS`: the declared scope was actually exercised and met its expected result.
- `PARTIAL`: a useful subset passed, but one or more required rows remain unrun or blocked.
- `BLOCKED`: a required external authority, credential, machine, or user-grade surface was not
  available; supporting evidence is not substituted for it.
- `FAIL`: current evidence shows the candidate does not meet the requirement.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `REL-003` | `FAIL` | Read-only ledger across all 11 nested candidates, parent refs, and Native policy; candidate identity refreshed 2026-07-21 | Refs equal current nested `HEAD`, but LibreChat has 11 dirty paths and both playgrounds have 2; none of that newest content is pinned, pushed, merged, built, or installed. |
| `REL-006` | `PARTIAL` | 111 payload/workflow tests and static workflow scan | The source contract passes; the exact signed/notarized artifact does not exist. |
| `REL-008` | `BLOCKED` | Final-candidate prerequisites and authority inventory | Exact PR, immutable release, shipped artifact, and installed identity proof cannot run before remote publication and signing authority. |
| `INST-019` | `PARTIAL` | 258 focused fault tests | The wider physical/user-grade matrix remains open. |
| `INST-020` | `PARTIAL` | Universal helper integrity plus 34 focused tests | Publisher signing, helper UI, Keychain, TCC, and login startup remain open. |
| `INST-023` | `PARTIAL` | Existing dated real-Chromium evidence plus current source/artifact audit | Browser rows pass; native assistive-technology and exact-artifact rows remain open. |

## Natural User Use Case Checklist Run

| Use case | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Fresh Easy Install | Run the published command on a pristine Mac and reach first useful chat | Installer | `BLOCKED` | No new exact signed-artifact UI was available in this audit | Workflow and payload contract suites pass | Signed/notarized immutable payload and pristine exact-artifact run |
| Intel install | Install and restart the exact candidate on supported Intel hardware | Installer and helper | `BLOCKED` | No current Intel user run exists | Dual-architecture source matrix and universal helper inspected | Exact Intel producer, install, first-use, and restart evidence |
| Inclusive onboarding | Use account setup and Feelings by keyboard across narrow, contrast, motion, and locale states | Browser | `PASS` for the scoped browser rows | Existing dated real-Chromium report records the visible states and recovery | Focused tests, production build, persistence, and loopback evidence in the owning report | Native assistive technology and exact artifact are separate rows |
| Native accessibility | Complete helper, Keychain, TCC, and repair with VoiceOver | Helper and macOS security UI | `BLOCKED` | No safely isolated headed native session was available | Source and helper integrity checks only | Real VoiceOver/helper/Keychain/TCC interaction |
| Failure recovery | Interrupt install, upgrade, config, restore, and dependency paths and recover | Installer and CLI contracts | `PARTIAL` | CLI behavior is asserted by focused subprocess fixtures; no new physical UI run | 258 focused tests | Low resources, broader network, reboot, sleep/wake, MDM/no-admin, concurrency, and headed Docker Desktop |
| Delivery parity | Install exactly the component commits that were reviewed | Installer, payload, and installed runtime | `FAIL` | No replacement built, payload, shipped, or installed identity was run | All refs equal nested `HEAD`, but current LibreChat and playground fixes are uncommitted | Commit and review nested fixes, update pins, then build, ship, install, and compare exact identities |
| Public review | Read current QA status without mistaking historical passes for current acceptance | QA documentation | `PASS` after correction | Current matrix now says `FAIL`, `PARTIAL`, and `BLOCKED` where required | QA ownership/public-safety checks | Continue updating only from exact-candidate evidence |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: immutable Easy Install release and installer resilience.
- Requirement: requirements 39, 40, and 45 plus `REL-003`, `REL-006`, `REL-008`, and
  `INST-015` through `INST-023`.
- Use case: a new or upgrading user installs the exact reviewed artifact on supported ARM64 or Intel,
  completes accessible setup, survives declared faults, and receives the reviewed component code.
- QA case: the scoped rows in the Scope Run and natural user use case tables above.
- Expected result: signed/notarized immutable artifact, supported dual-architecture behavior,
  user-grade inclusive/fault coverage, and exact source-to-installed identity.
- Actual evidence: focused source and contract suites pass; browser coverage passes in its dated
  scope; all refs equal current nested `HEAD`, but three nested repositories contain uncommitted
  reviewed fixes; operational signing, remote publication, downstream artifact identity, and several physical
  surfaces remain unrun or blocked.
- Remaining gap or fix: complete every open row in the closure sequence below without substituting
  supporting evidence for the required real user path.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirements and cases define acceptance? | Requirements 39/40/45; release-readiness and installer-resilience case catalogs |
| Code owning path | Which code enforces release truth? | Native candidate/release workflows, payload assembler/verifier, bootstrap, upgrade, helper, and component manifest code |
| Docs and nested docs/repos | Do public docs and selected nested repositories agree? | Refs agree with nested `HEAD`, but current working content in LibreChat and both playgrounds is not represented by those refs or the Native policy |
| Scripts or harnesses | What executed the contract? | Focused release Pytest suites and static workflow scanner listed below |
| Local/external prerequisite state | Which required authority or machine was available? | ARM64 source host available; signing/notary authority and exact Intel/native headed surfaces unavailable |
| Logs | Which logs prove the result? | Sanitized command totals and return results only; no private or runtime logs were published |
| Logs, DB/state/persistence | What persistent result was checked? | Existing browser report proves its scoped refresh/restart rows; no exact installed release DB/state existed for this audit |
| Generated/shipped artifact | Did generated and shipped identities match source? | `NOT RUN`; replacement built/payload/shipped/installed identity ledger is absent |
| Real user path | Which installer, CLI, browser, or helper path was used? | Existing dated browser and isolated CLI evidence was reviewed; no new signed installer, Intel, or headed native path was available |
| Visual/UX comparison | Does visible behavior match the requirement? | Browser scope does; native and exact-artifact UI remains blocked |
| Not run / blocked | What remains and why? | Signing authority, protected release, Intel, VoiceOver, helper/Keychain/TCC, and wider physical faults |

Required user-path evidence that was not run remains `BLOCKED` or `PARTIAL`. Unit tests, source
inspection, browser Axe results, a universal helper, and another model's review cannot replace
required user-path evidence.

## User-Grade Evidence

- Surface exercised: existing real browser onboarding/Feelings evidence and isolated installer/CLI
  subprocess evidence were audited; release workflows and helper artifacts were inspected directly.
- Real user path: no new signed installer, Intel, or headed native helper path was available. The
  owning dated real-Chromium report remains evidence only for its browser scope.
- Visible outcome: the scoped browser report records usable keyboard, narrow, contrast, motion,
  locale-fallback, recovery, and Feelings states; this audit produced no new visible release UI.
- Expanded/detail state: provider cards, retry states, account-menu navigation, Feelings failure and
  recovery, and browser persistence are recorded in the owning report; native dialogs were not run.
- Persistence/reload result: browser refresh and runtime restart pass only in the scoped existing
  report; exact signed-artifact install/restart and Intel persistence remain blocked.
- Local/external prerequisite state: ARM64 source inspection was available. Signing/notary authority,
  an exact Intel target, and safely isolated native assistive-technology state were unavailable.
- Evidence retrieval classification, if applicable: no provider lookup was part of this audit.
- Fallback path, if applicable: source and automated contract checks supported diagnosis but were
  not treated as a fallback acceptance path.
- Backend/log/DB confirmation: no private logs or DB rows were required or published. Existing
  sanitized state evidence supports only the browser scope; no final installed release existed.
- Final model/runtime wording check: no model answer was generated. QA wording now explicitly
  distinguishes proven local source alignment from unrun remote and artifact identity gates.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Gate matrix

| Gate | Result | Evidence | Remaining requirement |
| --- | --- | --- | --- |
| Candidate/release workflow contract | `PASS` | 111 focused tests passed; static workflow security scan reported no findings. Candidate and release workflows fail closed on architecture, policy, exact commit, digest, signature, notarization, stapling, Gatekeeper, immutable-release, and asset-allowlist checks. | An actual protected release run is a separate gate. |
| Signed/notarized immutable payload execution | `BLOCKED` | The approved-signer, Apple team, and MongoDB redistribution policy files are absent or empty; the host has zero valid code-signing identities; signing/notary release credentials were not provisioned. | Approved policy values, Developer ID authority, notary authority, protected release environment, immutable-release setting, and a successful exact-payload run. |
| Local helper architecture/integrity | `PASS` | The checked helper is a universal `x86_64` + `arm64` Mach-O and its SHA-256 matches its tracked sidecar; 34 helper/native stack tests passed. | Publisher signing and installed headed behavior are covered by separate gates. |
| Exact dual-architecture producer/install matrix | `BLOCKED` | Source declares and tests separate ARM64 and Intel lanes, but this audit ran on ARM64 and found no current exact-candidate Intel producer/install result. A universal helper alone does not prove the payload. | Exact candidate build/install/first-use/restart on both declared architectures, including a real Intel lane. |
| Scoped browser inclusive UX | `PASS` | The dated real-Chromium report proves keyboard operation, 320/390 px reflow, forced colors, reduced motion, German fallback, refresh/restart, recovery, Feelings, and settled-state Axe checks. | This pass is scoped to the browser matrix. |
| Full inclusive/native accessibility | `PARTIAL` | Browser coverage passes, but it cannot stand in for native assistive technology. | Native VoiceOver/screen-reader operation, helper dialogs, Keychain/TCC prompts, complete translations, Intel, and the exact shipped artifact. |
| Focused installer fault contracts | `PASS` | 258 tests passed across hostile/tampered payloads, transactional config/upgrade/continuity behavior, interruption and rollback, symlink/ownership boundaries, Telegram ownership, and explicit Docker endpoint handling. | User-grade physical fault coverage is separate. |
| Full physical installer fault matrix | `PARTIAL` | Focused contracts and scoped disposable-machine runs cover important failures, but the complete declared matrix was not run. | Low-resource and broader network faults, crash/reboot, concurrency, downgrade/delete breadth, physical sleep/wake, headed Docker Desktop, MDM/no-admin, Keychain/TCC, and Intel. |
| Alignment enforcement contract | `PASS` | 144 tests passed. Bootstrap, upgrade, and payload assembly reject dirty, unrelated, unverifiable, or mismatched selected repositories and require exact embedded metadata. | The current candidate must still satisfy the contract. |
| Current nested commit -> parent pin -> payload -> installed alignment | `FAIL` | As refreshed 2026-07-21, all refs equal nested `HEAD`, but LibreChat has 11 dirty paths and both playgrounds have 2. Those fixes are absent from commits and pins; replacement built/payload/shipped/installed identity is `NOT RUN`. | Commit reviewed nested fixes, update pins without drift, then build the replacement artifact and prove embedded, shipped, and installed identity equality. |
| Public QA status truthfulness | `PASS` after correction | `INST-023` records the browser pass as `PARTIAL` overall, while `REL-003` distinguishes proven local source-pin alignment from the unrun origin/merge and artifact chain. The May result remains historical. | Keep results scoped and update them only from exact-candidate evidence. |

## Automated Evidence

Commands were run from the repository root in the isolated release worktree. The dependency options below only
create an ephemeral test environment.

### Frozen parent release suite — 2026-07-21

```sh
python -m pytest tests/release/ -q
```

Test evidence: historical frozen snapshot `1,489 passed, 11 skipped in 271.53s`; exact current local source
`1,524 passed, 10 skipped in 305.19s` after the final review corrections. This source run does not
supply signing authority, remote PR identity, or a blocked physical user path.

### Signed payload and workflow contract

```sh
uv run --with pytest --with pyyaml --with 'pydantic>=2.7' \
  --with 'croniter>=2.0' --with fastapi --with httpx \
  python -m pytest \
  tests/release/test_ci_release_workflows.py \
  tests/release/test_native_payload.py \
  tests/release/test_native_payload_builder.py \
  tests/release/test_native_payload_assembler.py \
  tests/release/test_native_public_safety.py \
  tests/release/test_public_bootstrap_manifests.py -q
```

Test evidence: `111 passed in 4.84s`.

```sh
uvx zizmor \
  .github/workflows/native-payload-candidate.yml \
  .github/workflows/native-payload-release.yml \
  .github/workflows/config-compile.yml
```

Scan evidence: no findings. The scanner reported offline mode, so this is static workflow evidence, not a
remote release-run result.

### Signing authority check

```sh
for policy_file in \
  release/native-payload/allowed_signers \
  release/native-payload/apple-team-id \
  release/native-payload/mongodb-redistribution-approved
do
  test -s "$policy_file" && printf '%s PRESENT_NONEMPTY\n' "$policy_file" \
    || printf '%s ABSENT_OR_EMPTY\n' "$policy_file"
done
security find-identity -v -p codesigning
```

Signing evidence: all three policy files were absent or empty and macOS reported `0 valid identities found`.
Required signing/notary variables were also unset. No secret value was printed or recorded.

### Helper and architecture contract

```sh
file apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal
shasum -a 256 apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal
cat apps/macos/ViventiumHelper/prebuilt/binary.sha256

uv run --with pytest --with pyyaml --with 'pydantic>=2.7' \
  --with 'croniter>=2.0' --with fastapi --with httpx \
  python -m pytest \
  tests/release/test_macos_helper_install.py \
  tests/release/test_native_stack_helpers.py -q
```

Build evidence: universal `x86_64` + `arm64`; binary digest matched the sidecar; `34 passed in 2.90s`.

### Focused fault matrix

```sh
uv run --with pytest --with pyyaml --with 'pydantic>=2.7' \
  --with 'croniter>=2.0' --with fastapi --with httpx \
  python -m pytest \
  tests/release/test_native_payload.py \
  tests/release/test_upgrade_transaction.py \
  tests/release/test_config_transaction.py \
  tests/release/test_continuity_bundle.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_telegram_launchctl_ownership.py \
  tests/release/test_preflight.py \
  tests/release/test_cli_upgrade.py -q
```

Test evidence: `258 passed in 61.89s`.

### Alignment enforcement

```sh
uv run --with pytest --with pyyaml --with 'pydantic>=2.7' \
  --with 'croniter>=2.0' --with fastapi --with httpx \
  python -m pytest \
  tests/release/test_bootstrap_components.py \
  tests/release/test_public_bootstrap_manifests.py \
  tests/release/test_cli_upgrade.py \
  tests/release/test_native_payload_assembler.py -q
```

Test evidence: `144 passed in 41.36s`.

The read-only candidate ledger compared every `components.lock.json` path/ref with that repository's
`HEAD` and porcelain status, then compared the LibreChat ref with
`release/native-payload/components.json`. On 2026-07-21, `11/11` refs equal repository `HEAD` and
LibreChat `d64d3f8` equals the Native policy, but LibreChat has 11 dirty paths and the two playgrounds
have 2 each. None of that working content is commit-addressable, pushed, merged, built, shipped, or
installed. Replacement built/payload/shipped/installed identity remains `NOT RUN`.

### QA-document safety

```sh
uv run --with pytest --with pyyaml --with 'pydantic>=2.7' \
  --with 'croniter>=2.0' --with fastapi --with httpx \
  python -m pytest \
  tests/release/test_qa_operating_contract.py \
  tests/release/test_qa_results_public_safety.py -q

git diff --check -- \
  qa/installer-resilience/cases.md \
  qa/release-readiness/README.md \
  qa/release-readiness/cases.md \
  qa/release-readiness/reports/2026-07-20-release-gate-matrix-audit.md
```

Final result after this report was linked: `24 passed in 6.72s`; diff check and the targeted
personal-path/identifier/credential-pattern scan passed with no findings.

## Findings

- Defects: the public catalog understated completed browser coverage for `INST-023`, while the
  release-readiness overview overstated current component alignment and implied PR merge was the
  only remaining gate. Both status defects were corrected; the later frozen source-pin
  reconciliation is now recorded without generalizing it to unrun delivery artifacts.
- Regressions: no product code regression was introduced or claimed by this audit.
- Flakes: none observed in the focused suites.
- Environment issues: signing/notary authorities, exact Intel execution, and safely isolated headed
  native assistive-technology state were unavailable.
- Residual risks: signed artifact execution, pristine exact-artifact lifecycle, physical native
  accessibility/fault coverage, remote candidate reachability, and built-to-installed identity
  remain release blockers.

## Closure sequence

### Locally actionable after candidate freeze

1. Finish, test, review, and commit the dirty LibreChat and two playground working trees independently.
2. Push and merge nested commits first; recheck the parent refs and Native LibreChat policy against
   the exact reachable merged commits, updating them only if merge identity changes.
3. Build the exact candidate and compare source commit, embedded build metadata, archive digest,
   shipped manifest, and installed runtime identity.
4. Run the replacement pristine lifecycle and all remaining safe synthetic fault rows.

### Requires external authority or a missing real surface

1. Obtain approved signer, Apple team, MongoDB redistribution, Developer ID, and notarization
   authorities; configure the protected release environment and immutable-release setting.
2. Execute dual-architecture candidate and protected release workflows on the frozen commit.
3. Run the exact candidate on a real Intel target and a safely isolated headed Mac through
   VoiceOver, helper, Keychain, TCC, Gatekeeper, login startup, Docker Desktop, and physical
   sleep/wake/resource paths.

Release approval must remain closed until every required row is `PASS`; source inspection, unit
tests, a universal helper binary, or browser Axe results do not substitute for the missing user-grade
surfaces.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
