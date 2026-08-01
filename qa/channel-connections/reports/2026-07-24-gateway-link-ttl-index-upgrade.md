<!-- qa-evidence-exempt: Isolated migration implementation record; installed channel acceptance remains tracked in the owning cases catalog. -->
# Gateway Link TTL Index Upgrade

Date: 2026-07-24
Status: BLOCKED for public release — the historical local acceptance below exercised changes that
are not present in the currently pinned public LibreChat component.

Current correction (2026-07-31): the pinned LibreChat tree contains neither the cited `collMod`
migration nor its cited regression spec. The evidence below remains a record of an unreleased local
evaluation, not proof of the public component. This case must be reimplemented in the nested
component, reviewed, merged, repinned, and rerun before it can return to `PASS`.

## Incident and root cause

An older runtime could already have the single-field `gatewaylinktokens.expiresAt_1` index without
the schema-required `expireAfterSeconds: 0` option. Channel persistence called Mongoose
`createIndexes()` during readiness, MongoDB rejected the same-name/same-key option mismatch, and the
worker reconciler repeated a generic warning every 30 seconds.

The supported migration is MongoDB's in-place `collMod` conversion for an existing single-field
index. The implementation accepts only the exact legacy name/key with no behavioral modifiers,
applies only the TTL option, rereads index metadata, and fails closed on any different name, key,
TTL duration, or unsafe option. It does not drop indexes, synchronize the collection broadly, or
write documents.

Reference:
[MongoDB TTL index conversion](https://www.mongodb.com/docs/manual/core/index-ttl/#convert-a-non-ttl-single-field-index-into-a-ttl-index)

## Evidence run

```text
cd viventium_v0_4/LibreChat/api
npx jest \
  server/services/viventium/__tests__/channelPersistence.spec.js \
  server/services/viventium/__tests__/channelPersistence.mongodb.spec.js \
  --runInBand
```

Result: PASS for the isolated slice — `2` suites and `17` isolated tests passed.

Before implementation, the focused unit suite failed `10` new assertions and passed only the `4`
pre-existing behaviors, proving the regression cases exercised missing functionality.

The real ephemeral-Mongo case proved:

- one populated synthetic link-token document survived the conversion;
- an unrelated synthetic index survived;
- `expiresAt_1` gained `expireAfterSeconds: 0`;
- a second readiness run was idempotent;
- a reserved-name/different-key conflict left both the document and index inventory untouched.

The final wider channel, gateway, and native-socket selection passed `11` suites and `87` tests.
ESLint passed for all four changed nested JavaScript files, Prettier reported every changed nested
file compliant, and `git diff --check` passed. This implementation slice used no live database or
personal channel state.

## Historical local acceptance (not present in the public pin)

- The established local runtime that had produced the unavailable Channels screen was upgraded and
  restarted through the supported activation path.
- Database metadata showed the exact `gatewaylinktokens.expiresAt_1` index with
  `expireAfterSeconds: 0`; there were no duplicate indexes or duplicate link records.
- Settings > Channels loaded in a real signed-in Chrome session, showed truthful per-channel state,
  and remained healthy after refresh and full runtime restart.
- The incompatible-index, command-failure, and verification-failure paths remain covered by the
  public-safe synthetic fixtures; they fail closed without document mutation or private output.

The installed run used private local evidence only for the verdict. No database export, account ID,
chat ID, credential, raw log, or screenshot was added to the public repository.
