# 40. Public / Private Boundaries and License Matrix

## Purpose

This document defines what belongs in public, private personal, and private enterprise release surfaces.

## Boundary Rules

- Public product repo contains orchestration, docs, tests, examples, and release tooling.
- Public component repos contain the active nested forks that remain part of the v0.4 product surface.
- Private personal repo contains secrets, backups, source-of-truth live state, private docs, and personal prompts.
- Private enterprise repo contains deployment automation and service runbooks, but not live customer secrets.
- Private personal and enterprise companion repos may be stored locally under the `viventium_core`
  root for workspace convenience, but only as independently managed repos that are ignored by the
  main repo and excluded from every public export.
- A directory only counts as a `<private-companion-repo>` or `<enterprise-deployment-repo>` when it
  is the root of a separate git repo or worktree. A plain folder with that name is not trusted as a
  private boundary.
- Public-facing docs must not leak owner-private identity, private machine names, personal contact
  text, absolute private paths, or token-like examples.
- Machine-local continuity manifests, recall markers, helper logs, and restore pre-backups are
  runtime artifacts, not public repo content.
- Continuity manifests may exist under App Support or private companion storage only as
  public-safe metadata:
  - sanitized `~/...`-style paths are acceptable
  - raw home-directory paths, raw DB URIs, message text, prompts, tokens, cookies, and personal
    identifiers are not
- Secret-bearing snapshot payloads, backup archives, restore pre-backups, and companion-enriched
  continuity bundles must stay machine-local or in the private companion repo. They must never land
  in `docs/`, `qa/`, `tests/`, fixtures, or git history for the public repo.
- Memory hardening raw workpacks, model proposals, rollback snapshots, and local account backup
  manifests are private runtime artifacts. They may exist under App Support or an operator-chosen
  private local backup directory, but must never be copied into public docs, QA evidence, fixtures,
  commits, or release bundles.
- Semantic memory hardening uses host-authenticated Claude Code or Codex CLI sessions when enabled.
  That means per-user conversation context and saved-memory text may transit the operator's CLI
  provider account. This is different from the live memory writer's user-connected-account path and
  must remain opt-in, documented, and auditable.
- Operator-only deployment or service runbooks belong in the private companion repo or enterprise
  repo, not in the public product docs.
- A nested `<private-companion-repo>` or `<enterprise-deployment-repo>` subtree is not an acceptable
  part of any final public export, even when ignored locally during development.

## Leak Scenarios To Prevent

- Unsafe local folder names:
  - A plain `private-companion-repo/` or `enterprise-deployment-repo/` directory inside the public
    checkout is not sufficient isolation.
  - Discovery helpers must require a separate git repo root or worktree before treating that folder
    as private-only state.
- Unsafe public artifacts:
  - `docs/`, `qa/`, `tests/`, fixtures, example configs, and commit messages must not include raw
    App Support paths, local usernames, hostnames, personal emails, or secret-bearing command
    examples.
- Unsafe machine-local exports:
  - support bundles, debug zips, helper logs, and continuity manifests must stay metadata-only on
    the public path
  - if richer private payload is needed, it must go only to App Support or the separate private
    companion repo
- Unsafe backup handling:
  - snapshot roots may contain companion-enriched payload locally, but the public wrapper must stay
    usable without that helper and must never require private payload to function
  - restore pre-backups, Telegram safety copies, Mongo exports, and recall rebuild markers are
    machine-local runtime artifacts and must not be promoted into public git history
- Unsafe memory-hardening artifacts:
  - `proposal.private.json` and `*.rollback.private.json` contain raw saved-memory values and must
    stay private
  - public summaries may include only hashed user ids, key names, counts, model family, timestamps,
    and validator outcomes

## License Rules

- Viventium-owned original code/docs/brand in the main public repo use an FSL-based source-available posture.
- Upstream open-source components keep their required notices and compatible licenses.
- `skyvern-source` remains AGPL in its own public component repo.
- Placeholder public component repos must clearly declare placeholder status and carry the intended
  upstream legal files before upstream-derived source is published there.
- Public-facing docs for FSL repos must say source-available / Fair Source today, not OSI open
  source before the future Apache-2.0 conversion date applies.
- The public surface must use a license matrix; it must not claim a single blanket license over every component.

### Easy Install Native Runtime Candidates

| Runtime/artifact | Current license/distribution boundary | Easy Install Native decision |
| --- | --- | --- |
| Node.js supported LTS official macOS runtime | Node is MIT with bundled third-party notices; preserve the complete upstream license/notice set. Node 20 is EOL. | Compatibility-test and pin the latest supported Node 24 LTS patch per architecture; Node 22 is fallback only if required by proven compatibility. Do not ship Node 20. |
| MongoDB Community Server 8 macOS archive | SSPL is source-available, not OSI open source. MongoDB documents redistribution, but public conveyance still needs explicit notice/compliance/legal review. | The implemented producer downloads the exact official per-architecture archive, verifies digest/version/publisher, and can place the allowed runtime files in the payload. Candidate and release workflows fail closed until `release/native-payload/mongodb-redistribution-approved` records the required approval; do not upload or publish the bundled candidate before then. |
| Meilisearch Community Edition | Community code/assets are MIT; the repository also has separately licensed enterprise functionality. | If runtime evidence proves chat works without it, defer it. Otherwise select only an exact Community Edition asset, preserve MIT notices, and cap memory/threads. Never select an enterprise asset by pattern or `latest`. |
| Sparkle updater | Sparkle is MIT; archive/feed signing does not replace Apple code signing/notarization or Viventium's runtime/data health gate. | Candidate for the small macOS helper only after dependency/security review. Runtime payload activation remains Viventium-owned and health-gated. |
| Viventium runtime/helper bundles | Viventium license plus all nested third-party notices. Apple distribution requirements are separate from copyright licenses. | Sign nested code first, then enclosing bundles; notarize every downloaded executable payload; publish SBOM, exact manifest, notices, and installed-artifact evidence before release. |

Version numbers and hashes belong in a signed release manifest, not this policy document. The
release process must update notices/SBOM and rerun the license scan whenever any candidate changes.
For npm workspaces, the release inventory is the physical `package-lock.json` package graph in the
exact pruned payload, keyed by installed path so duplicate installations remain distinct. Recursive
`package.json` discovery is forbidden because export-subpath manifests are not independent bundled
packages. The scan records and re-verifies the SHA-256 of every shipped notice it cites and requires
the component-specific Node/Python/MongoDB/LibreChat notice paths. The minimal Python runtime
excludes pip, `site-packages`, `ensurepip`, and `venv`; its inventory instead binds the CPython
license and exact python-build-standalone dependency-license files to the pinned source commit and
archive digest. Static-client packages compiled into browser assets remain obligations even after
frontend `node_modules` is removed: a deterministic normalized Rollup input closure and copied
package-owned notice set must be part of the shipped compliance evidence. A missing declaration,
missing exact notice, or license expression outside the reviewed allowlist remains a release
blocker; it must not be converted into an approval merely to make the producer pass.

### Native Release Authority Boundary

The Native release trust split is explicit:

- public and reviewable: the exact manifest signer public key in an OpenSSH allowed-signers policy,
  the approved Apple Developer Program team identifier, manifest schema, release sequence, payload
  hashes/inventory, component pins, SBOM/notices, workflow source, attestations, and sanitized QA;
- protected release environment only: manifest private key, Developer ID Application certificate and
  password, temporary keychain, App Store Connect notarization key, key id, and issuer id;
- prohibited from candidate artifacts, public logs, docs, tests, and bootstrap overrides: every
  private key, certificate password, token, credential-bearing command, and private runtime datum.

`release/native-payload/allowed_signers`, `release/native-payload/apple-team-id`, and
`release/native-payload/mongodb-redistribution-approved` must not be added until the corresponding
release-owner/legal review approves the real public values. Their absence is an intentional
fail-closed production gate. The candidate producer runs without release secrets; only the protected
release job receives authorities after environment approval. Temporary credentials live under the
runner's temporary directory, use restrictive modes and an ephemeral keychain, and are removed on
exit. Raw notary responses stay in temporary storage; the public draft uses an exact filename
allowlist and contains no runner paths or notary request identifiers. Public bootstrap trust values
are reviewed, signed release resources and cannot be replaced by environment variables or network
metadata.
Release sequence is public trust policy, not operator input. The protected workflow serializes all
Native releases, verifies the complete retained signed bootstrap-index history, and accepts only
sequence `1` or exactly the prior high-water sequence plus one. The tagged public shell's reviewed
minimum floor, its signed outer index, the Developer-ID-signed app's embedded release policy, and
the separately signed payload manifest must carry one identical release identity and sequence.
Established installs additionally persist an owner-only high-water mark. None of these values is a
substitute for an independently authenticated current-release/freshness authority on a machine with
no prior state; that external authority remains a production release prerequisite rather than a
value to invent in this public repository.

## Release Artifacts

- `LICENSE-MATRIX.md`
- `THIRD_PARTY_LICENSES.md`
- `NOTICE`
- `UPSTREAMS.md`
- approval and release evidence captured under `qa/` for the reviewed surface

## CI Provider-Secret Boundary

Pull-request code is untrusted even when the branch is in the same repository. A workflow reachable
from `pull_request` or `pull_request_target` must not reference repository or environment secrets.
Provider-backed live evals use a separate workflow that runs only on the protected default branch,
targets the `productivity-activation-live-eval` environment, and injects provider credentials only
into the final live-eval step after an `npm ci --ignore-scripts` install. Dependency lifecycle hooks
are therefore disabled and never share a secret-bearing step. The secretless pull-request workflow
may run static contracts against proposed code, but it cannot receive provider credentials. The
trusted workflow fetches and validates the exact LibreChat commit from `components.lock.json`; a
missing/unpublished pin fails the live gate rather than silently skipping it.

The repository source cannot prove GitHub-hosted policy. Release owners must configure the named
environment with required reviewers and a deployment-branch rule limited to the protected default
branch, store dedicated synthetic spend-limited provider credentials in that environment, and keep
the default branch protected against direct or unreviewed writes. Until those controls are verified
in GitHub, the source boundary is implemented but the hosted live-eval gate remains `PARTIAL`.
