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
- Public-facing docs must not leak owner-private identity, private machine names, personal contact
  text, absolute private paths, or token-like examples.
- Operator-only deployment or service runbooks belong in the private companion repo or enterprise
  repo, not in the public product docs.
- A nested `<private-companion-repo>` or `<enterprise-deployment-repo>` subtree is not an acceptable
  part of any final public export, even when ignored locally during development.

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
