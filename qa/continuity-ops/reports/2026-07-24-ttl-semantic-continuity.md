<!-- qa-evidence-exempt: Isolated semantic-continuity implementation record; installed lifecycle acceptance remains tracked in the owning cases catalog. -->
# TTL-Aware Strict Semantic Continuity — 2026-07-24

Status: PARTIAL — source and synthetic migration proof pass; installed user-path proof remains.

## Root cause

The first-upgrade bridge compared every fingerprinted Mongo collection by aggregate count and hash.
The successor also converts the exact legacy `gatewaylinktokens.expiresAt_1` index into the
schema-required TTL index. MongoDB may then remove a token that was already expired before the
upgrade. That legitimate lifecycle cleanup changed the aggregate fingerprint and made strict
candidate acceptance roll back indefinitely, even when all durable user state was intact.

Excluding the whole token collection would hide loss of active link tokens and weaken the channel
continuity gate. Using the comparator's current wall clock would also make identical manifests
nondeterministic.

## Implemented contract

- The Mongo adapter fingerprints every present non-system collection by default, so `toolcalls`,
  future/custom durable collections, and newly introduced product state cannot fall through a
  maintained allowlist. Managed default agents retain their explicit baseline-aware exception.
- The adapter has an explicit policy matching each schema-owned TTL collection, including channel
  delivery, ingress quota, pairing attempt, worker lease, Viventium ingress/call-session, and
  GlassHive callback-delivery ledgers.
- Each expiring document contributes only a canonical Extended-JSON SHA-256 digest and effective
  database expiry. Non-expiring rows remain protected by an aggregate count/hash, avoiding a
  per-message expansion for ordinary chat history.
- The strict comparator uses the live manifest's recorded `capturedAt` as its deterministic cutoff.
  It removes a digest from both protected sets only when its effective expiry is at or before that
  cutoff.
- A missing/malformed cutoff, field, delay, count, digest, lifecycle ledger, active document, or
  non-expiring aggregate fails closed.
- Durable channel connections, threads, gateway/Telegram user mappings, auth/provider
  personalization, ordinary conversations/messages/files/users, agents, prompts, memory, and
  schedules retain their existing exact semantic comparison.
- Every non-internal scheduling SQLite table is hashed with every column and row. Runtime status,
  next-run, conversation, delivery state, and `scheduled_prompt_runs` are protected rather than
  treated as disposable outcomes.
- The manifest and comparison differences contain no raw token, document ID, account, message,
  prompt, or provider value.

Declared policies are zero-delay for API/provider keys, pairing/link tokens, delivery/ingress/lease
state, temporary conversations/messages, sessions, and auth tokens; one hour for file expiry; and
seven days for user expiry.

## Evidence actually run

The primary regression was RED before implementation: a snapshot containing one already-expired
gateway token and one future token compared against a live manifest containing only the future token
returned `error`.

After implementation:

- the expired token may disappear;
- losing the future token returns a strict error;
- changing durable channel connection state returns a strict error;
- deleting durable `toolcalls`, an unknown future collection, an active channel delivery, scheduler
  run/status/next-run fields, or a scheduled-prompt run returns a strict error;
- malformed lifecycle proof and a missing live cutoff fail closed;
- every currently fingerprinted TTL field/delay emits the expected effective expiry;
- optional non-expiring API-key state remains aggregate-protected;
- synthetic private token/account/content values do not appear in adapter output; and
- atomic JSON output replacement leaves one mode-`0600` result and no temporary file.

Command:

```text
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_continuity_audit.py \
  tests/release/test_continuity_bundle.py -q
```

Result: `102 passed`.

No installed App Support path, personal database, conversation, schedule, prompt, credential,
channel account, or live runtime was read or mutated.

## Remaining acceptance

- Commit/push the nested LibreChat TTL migration, update the parent component pin, and prove the
  built/shipped/installed artifacts all carry it.
- Upgrade an isolated established install containing the exact legacy index, an already-expired
  synthetic token, a future token, and durable synthetic connection/mapping state.
- Wait for the MongoDB TTL monitor, then verify strict acceptance, exact index metadata, and active
  and durable state in the database.
- Open Settings > Channels in a real browser, verify visible connection state, refresh, restart,
  and correlate the result with logs and private semantic manifests.
- Keep all candidate writers quiesced during stopped/live comparison. TTL normalization is not a
  substitute for preventing concurrent chat, channel, schedule, or delivery mutations.
