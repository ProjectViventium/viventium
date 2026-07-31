# Workspaces

Every Codex, Claude, GlassHive, or other delegated mission works inside one bounded folder created
by the worker runtime:

`Workspaces/<agent-type>/<YYYY-MM-DD>-<slug>/`

The parent waits for the returned `workspace_dir`, then materializes the authorized bundle using
[`_mission-template/`](_mission-template/MISSION.md). The Life root rules are inherited.
Temporary downloads, scratch files, tool evidence, partial deliverables, and logs stay inside the
mission. Only user-approved deliverables or governed proposals are promoted elsewhere.

The workspace may receive the full visible caller context, but only under the permission and privacy
scope recorded in its context manifest. Hidden reasoning, credentials, private platform prompts, and
unrelated Life data are never part of the handoff.

The first V0.5 slice is host-native with `workspace_root` configured to this directory. A Docker or
sandbox worker sees only its mission mount and bootstrap bundle unless a narrow read-only Life
reference mount is explicitly added to the current runtime contract. This fixture does not claim
that folder placement alone changes current GlassHive mounts or callback behavior.

This is a logical V0.5 contract, not a second GlassHive artifact system. During implementation,
`MISSION.md` must compile to or alias the current `project-definition.md`; completion and evidence
must continue to use the current line-anchored `FINAL REPORT:` and `glasshive-run/evidence.json`
surfaces. The receipt may index that evidence, but it must never become a competing source of truth.
