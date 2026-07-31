# Persisted PGDATA Credential Migration

<!-- qa-evidence-exempt: Source and disposable-data-plane note; browser and installed-runtime evidence belongs in the universal-upgrade run report. -->

**Date:** 2026-07-24
**Scope:** source/Docker RAG PostgreSQL credential continuity
**Result:** PASS-ISOLATED / PARTIAL-INSTALLED

## Requirement

An established install must keep its existing PGVector corpus when internal runtime credentials
change. PostgreSQL image initialization variables are not an upgrade mechanism: they apply only to
an empty data directory. Migration must preserve vector rows, be safely replayable after
interruption, avoid secret disclosure, and reject unknown or foreign PGDATA.

## What Ran

- `tests/release/test_rag_postgres_migration.py`: `19 passed`
- `tests/release/test_rag_api_override_contract.py` plus
  `tests/release/test_rag_compose_resource_guardrails.py`: `20 passed`
- launcher shell syntax: PASS
- opt-in `tests/release/test_rag_postgres_migration_docker.py`: `2 passed`

The Docker test used a new temporary Compose project, no published ports, a temporary bind path, and
synthetic values only. It:

1. initialized the pinned PostgreSQL/PGVector image with a predecessor password;
2. created the two recognized RAG relations and one synthetic vector row;
3. stopped the container and ran the migration with a new owner-state directory;
4. proved PostgreSQL system identity, the complete recognized schema digest, and streamed
   UUID-ordered digests of every collection/embedding row were unchanged;
5. proved the stable migrated password authenticated from a separate network container while the
   predecessor password did not;
6. reran the migration and proved the credential stayed stable;
7. added an unrelated relation and proved migration refused the now-foreign schema without removing
   the synthetic RAG row;
8. started the exact pinned RAG API image against a second disposable cluster, proved it created only
   the two recognized relations, and promoted the same receipt from fresh to initialized state;
9. removed its temporary containers and networks.

Focused contracts also covered same-row-count content drift, empty first-run adoption,
missing/foreign database or role identity, mount mismatch, partial/foreign relations, interrupted
role reconciliation, stable replay, receipt redaction, owner-only file mode, missing credential
beside a receipt, and launcher ordering.

## Evidence Boundary

- Raw credentials were not printed, stored in this report, passed as CLI arguments, or included in
  migration receipts.
- The only secret-bearing product artifact is the machine-local owner-only credential file.
- Public evidence records statuses, counts, digests, and equality checks only; it contains no local
  path, account identity, private corpus content, or PostgreSQL system identifier.

## Not Run

- upgrade of the installed owner runtime;
- installed RAG API startup using the migrated credential;
- browser-visible grounded Recall before and after upgrade;
- a shipped immutable public installer artifact;
- reboot/helper-driven restart.

Those are required before universal-upgrade or installed-release acceptance. This result proves the
data-plane migration and fail-closed boundaries in isolation; it does not claim the full user path.
