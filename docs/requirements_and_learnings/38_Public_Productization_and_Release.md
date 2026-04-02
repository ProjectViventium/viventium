# 38. Public Productization and Release

## Purpose

This document is the public release source of truth for how Viventium moves from a private development monolith to a publishable product with:

- zero-loss preservation of personal state,
- a clean public repo boundary,
- one-command install,
- a docs and license structure that other engineers can extend safely.

## Locked Decisions

- Public release is `v0.5.0`.
- macOS is the only supported public install target for the initial release.
- `viventium_v0_3_py` is excluded from the public release.
- Public release happens from fresh repos/history, not by pushing the current mixed repo.

## Release Surfaces

- `viventium`: public product repo
- private preservation repo: private preservation/state repo
- `<enterprise-deployment-repo>`: private enterprise deployment/service repo
- separate public component repos pinned through `components.lock.json`

## Required Gates

- approval manifests generated and reviewed
- private restore drill succeeds on a clean machine
- no live secrets or stateful private paths remain in the public surface
- one-command install works in both Docker and Native modes on macOS

## Future Distribution Surface

The intended public convenience surfaces are:

- `brew install viventium`
- `npx viventium`
- single-clone repo path:
  - `git clone ... && cd viventium && ./install.sh`

These are not interchangeable today, and they do not all become available automatically.

### What `npx viventium` Requires

- a published npm package that ships the public CLI entrypoint
- the npm package must either:
  - embed the public installer/bootstrap logic directly, or
  - fetch a signed/versioned release artifact from the public product distribution surface
- public release versioning and artifact integrity checks
- documentation that clearly states what `npx viventium` installs, where it writes config, and what
  prerequisites it may ask Homebrew to install

### What `brew install viventium` Requires

- either a Homebrew tap/formula we maintain, or upstream inclusion with a stable formula
- a stable downloadable release artifact the formula can install
- macOS support policy pinned to specific versions/architectures
- release automation that updates formula checksums per version

### What the Single-Clone One-Liner Requires

- the main repo README must stay honest about the currently supported path
- the repo must contain all public-facing docs people need:
  - what Viventium is
  - install options
  - setup and auth options
  - how to start/upgrade/stop
- the repo-local installer must remain bulletproof without assuming private state already exists

### Human-In-The-Loop Requirement

The final public `npx` / `brew` surface still needs human release involvement:

- publishing the npm package
- publishing signed or versioned release artifacts
- managing the Homebrew formula/tap
- confirming public names, domains, and release channels

Codex can prepare the code, docs, package structure, and validation plan, but the actual public
package publication and formula ownership remain release-owner actions.
