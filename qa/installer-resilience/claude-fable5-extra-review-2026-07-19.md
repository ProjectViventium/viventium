# Fable 5 Extra Easy Install Audit Reconciliation — 2026-07-19

## Review boundary

- Surface: one visible Claude Desktop session controlled through Computer Use.
- Model and effort: Fable 5, Extra.
- Mode: review only. The prompts prohibited edits, file creation, install/runtime/account/config
  changes, stage/commit/push/PR/release actions, cloud changes, and external messages.
- Context: the original installer/new-user request, Easy Install / Custom Settings Install naming,
  personal-machine safety rules, current implementation/docs/QA evidence, competing explanations,
  and the provisional PARTIAL product verdict. Private connection details and local paths were
  sanitized.
- Role: independent supporting review. It did not substitute for installer, browser, DB/state,
  artifact, or automated user-path evidence.

## Findings and closure

The first coherent pass rejected the superseded closeout and found seven defects:

| Finding | Final status | Verified correction |
| --- | --- | --- |
| F1 stock-Python restore dependency/misclassification | CLOSED | Restore/check are standard-library-only, skip bootstrap/App Support creation, and pass 146-path and `-I -S` regressions |
| F2 stale contradictory test totals | CLOSED | Living report/cases and reproducible commands use one exact final collected total |
| F3 unquoted interpreter path | CLOSED | Upgrade and restore pass with spaces in both interpreter directory and filename |
| F4 pull-before-stop and inaccurate wording | CLOSED | A running stack stops before pull; stop refusal truthfully says no pull/component refresh occurred |
| F5 stdout magic-string safety gate | CLOSED | Post-bootstrap alignment is structured JSON |
| F6 retired-label guard gaps | CLOSED | Active source/contracts ban capitalized `Express`; the prebuilt is scanned for retired labels; lowercase internal compatibility remains |
| F7 malformed marker/helper-integrity/help gaps | CLOSED | Marker parsing is bounded/fail-safe, source and binary hashes fail closed, universal architecture is parsed, and restore help says apply is unavailable |

The follow-up then raised four minor residuals. The same session re-inspected their corrections:

| Residual | Final status | Verified correction |
| --- | --- | --- |
| R1 bundle/config schema coupling | CLOSED | Separate bundle and config version constants plus a decoupling regression |
| R2 untracked-parent upgrade behavior | CLOSED | Requirement, QA case, structured guidance, preservation, exit `3`, and no-App-Support-mutation evidence align |
| R3 terminology guard residual | CLOSED | Bare capitalized token and shipped-binary regressions close the escape |
| R4 unreproducible focused count | CLOSED | The documented six-file command reproduced exactly at 148 passed |

No new material defect remained after the micro-recheck.

## Independent reruns

- Focused continuity/upgrade/helper/label command: **148 passed**.
- Claude's full suite from the spaced-interpreter environment: **1,077 passed, 2 skipped,
  0 failed**.
- Supported acceptance environment: **1,072 passed, 7 skipped, 0 failed**.
- Both environments collected **1,079** tests; five environment/opt-in cases skipped by the
  supported acceptance command executed successfully in Claude's environment.
- Source and binary helper digests matched, the binary was universal, and the review retained the
  distinction between neighboring integrity hashes and publisher provenance.

## Final second-opinion verdict

- **AUDIT PACKAGE: PASS** — internally consistent, reproduced, and all Claude findings closed with
  regression evidence.
- **PRODUCT RELEASE: PARTIAL** — not public-release-ready.

The unchanged product blockers are an immutable Developer-ID-signed/notarized publisher-bound
payload; a pristine no-developer-tools cold install; completed synthetic provider grant and
persistent first/second answer; a complete public capture/apply restore engine; safely isolated
headed Docker/Keychain/TCC QA; Intel, inclusive-UX, and broad fault matrices; and exact nested
commit/pin/build/payload/installed-artifact alignment.

No cloud action, stage, commit, push, PR, release, account grant, channel mutation, or external
message was part of this installer-audit review.
