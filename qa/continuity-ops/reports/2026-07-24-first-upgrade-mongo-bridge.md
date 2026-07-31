<!-- qa-evidence-exempt: Isolated upgrade-bridge implementation record; installed Native/Docker acceptance remains tracked in the owning cases catalog. -->
# First-Upgrade Mongo Bridge — 2026-07-24

## Scope

Successor-owned Mongo-only startup for the stopped semantic baseline. All fixtures used synthetic
state under disposable test directories; no installed App Support, personal database, conversation,
schedule, prompt, credential, or live runtime was read or changed.

## Acceptance evidence

- Native App Support bind: the bridge accepts only a complete immutable checkpoint, forces the
  recorded profile/path/port on loopback, and requires the predecessor PID-era executable path,
  SHA-256, version, arguments/dbpath, process-start identity, and available code-signature identity.
  It starts Mongo only with that exact recorded binary, then revalidates the new PID, binary hash,
  version, dbpath, and signature before any semantic read or stop.
- Docker named volume: the bridge requires the recorded volume and cached image, creates a unique
  transaction-labeled container with `--pull never`, publishes only to loopback, proves the exact
  mount/configured-image/immutable image ID/labels/port/container ID and Mongo ping, then revalidates
  the same identity before stop/removal. A mutable tag is never the launch authority, and a retargeted
  `.Image` identity fails closed.
- Docker bind: future ledgers record `runtime_engine=docker` and the image observed from the running
  predecessor container. The bridge uses that image and exact App Support bind rather than host
  `mongod`.
- Durable engine receipt: future runtimes record direct native process identity or Docker
  container/mount/image-ID identity while Mongo is running. Clean stop seals the same identity plus
  a bind-directory or named-volume anchor in an owner-only, digest-protected, fsync'd receipt. A
  stopped upgrade revalidates exact path/volume/container and native binary hash/version or cached
  immutable image ID. The receipt is independently checkpointed and restored byte-exactly.
- Legacy ambiguity: the exact support-floor isolated-Docker ledger can describe either a native
  fallback or a Docker bind without recording the engine; its inspected Docker-bind branch can
  also omit the image. Raw stopped durable native/Docker bind or named-volume storage without
  direct or clean-stop proof rejects in policy preflight before source fetch or transaction
  creation. Guessing from install mode is forbidden.
- Physical clone limit: opening an immutable clone with a candidate-compatible engine is only a
  diagnostic. It does not identify which engine created the original and is not upgrade authority.
- One authority: the obsolete candidate-environment `_first-upgrade-runtime start-storage` action is
  absent. Baseline storage is owned only by the Python successor bridge and is stopped before any
  candidate runtime start.

## Tests actually run

- Focused synthetic storage/engine/support/rollback suite: PASS (33 cases across the three owning
  files), including running/stopped native, Docker bind/named volume, mutable-tag retarget,
  missing engine prerequisites, receipt ownership/integrity, anchor drift, and exact rollback.
- Python compile and shell syntax checks: PASS.
- Native-stack helper regressions: PASS.
- Real disposable Docker proof using an already-cached Mongo 8.0 image: PASS for named volume and
  bind path. A synthetic document was written/read in each disposable database, readiness succeeded,
  the exact containers were removed, and the labeled QA volume was removed. A post-run Docker query
  found no bridge container or QA volume left behind.

## Remaining gaps

- Raw stopped exact-floor bind/named-volume states without required engine proof need a separately
  released intermediate that observes the running creator engine and cleanly stops it, or a
  complete supported snapshot restored into a fresh same-profile install. The floor is therefore
  conditional, not a universal claim based only on Git ancestry.
- Real installed Native and Docker upgrades, interruption recovery, full headed persistence, and
  shipped/pinned/installed artifact parity are not proven by this disposable storage lane.
- Candidate validation must keep background/channel writers quiesced during the strict stopped/live
  comparison. That is a separate runtime-controller acceptance lane; storage evidence does not
  replace it.
- Expired ephemeral gateway tokens can be legitimately removed by successor TTL migration. The
  schema-driven private lifecycle ledger now normalizes only documents expired by the live capture
  cutoff while retaining exact active/durable protection; synthetic proof passes, while installed
  TTL-monitor/browser acceptance remains open in
  `2026-07-24-ttl-semantic-continuity.md`.
