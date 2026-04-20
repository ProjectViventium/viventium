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

## License Rules

- Viventium-owned original code/docs/brand in the main public repo use an FSL-based source-available posture.
- Upstream open-source components keep their required notices and compatible licenses.
- `skyvern-source` remains AGPL in its own public component repo.
- Placeholder public component repos must clearly declare placeholder status and carry the intended
  upstream legal files before upstream-derived source is published there.
- Public-facing docs for FSL repos must say source-available / Fair Source today, not OSI open
  source before the future Apache-2.0 conversion date applies.
- The public surface must use a license matrix; it must not claim a single blanket license over every component.

## Release Artifacts

- `LICENSE-MATRIX.md`
- `THIRD_PARTY_LICENSES.md`
- `NOTICE`
- `UPSTREAMS.md`
- approval and release evidence captured under `qa/` for the reviewed surface
