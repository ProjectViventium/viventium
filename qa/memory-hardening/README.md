# Memory Hardening QA

## Scope

This QA record covers the local saved-memory hardening operator job:

```bash
bin/viventium memory-harden dry-run
bin/viventium memory-harden apply --run-id <run-id>
bin/viventium memory-harden rollback --run-id <run-id>
```

## Public-Safe Acceptance Criteria

- The feature is default-off in canonical config.
- Generated runtime env keeps launch-ready model defaults only.
- Dry-run writes no memory entries.
- Apply writes only validated `set` / allowed `delete` operations.
- `working` is never modified by the batch hardener.
- Rollback restores the pre-apply key/value state for each affected user.
- Summary artifacts contain only hashed user ids, counts, key names, timestamps, model/provider,
  and validator outcomes.
- Raw proposals and rollback snapshots stay under local App Support state and are not copied into
  this QA directory.

## Local QA Notes

Use a synthetic or QA account for local browser verification. Do not publish raw memory values,
conversation text, emails, local paths, screenshots with private data, or generated runtime files.

Recommended local sequence:

```bash
bin/viventium memory-harden dry-run --user-email "$QA_EMAIL" --ignore-idle-gate
bin/viventium memory-harden apply --run-id "<run-id>"
bin/viventium memory-harden status
```

Record only redacted run ids, changed key names, and pass/fail outcomes in public reports.
