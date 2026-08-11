# Python Thread-Exhaustion Guard — 2026-08-10

## Outcome

`dev-env run` now fails closed before a candidate Python process can expand toward the thread counts
observed during the August 10 host crashes. The installed local runtime is outside this guard and
must remain untouched during candidate QA.

## Incident Evidence

Three local macOS panic records shared the same kernel spinlock-timeout signature. Each named a
`python3.11` task with between 9,474 and 12,255 threads. The records reported healthy compressor and
swap state. This supports Python thread exhaustion as the workload trigger, but does not identify
the exact Python command or prove the deeper kernel/user-space root cause.

Raw panic files, process identifiers, machine paths, and local logs remain private and are not part
of this public QA report.

## Prevention Contract

- Candidate startup goes through `bin/viventium dev-env run`.
- Native-library and tokenizer worker pools receive bounded development values even when the parent
  shell contains unsafe inherited values.
- A macOS/Linux supervisor checks only Python members of the isolated candidate process group every
  250 ms. Re-parented candidate services remain covered; unrelated host Python processes are not
  individually inspected.
- The guard stops the isolated process group at more than 512 threads in one Python process or more
  than 2,048 Python threads in the candidate tree.
- Inspection failure is fail-closed. Test-only environment values may lower but never raise limits.
- Inherited detached-start mode is disabled. Ctrl+C, SIGTERM, and SIGHUP wait for the runtime's
  normal cleanup; the five-second forced-stop escalation is reserved for a guard breach or
  inspection failure.
- Broad Python/audio/voice stress remains restricted to disposable infrastructure; a guarded local
  browser smoke test is not soak evidence.

## Automated Evidence

The focused regression was written and run failure-first:

1. Before the implementation, inherited values of 128 reached the child unchanged.
2. Before the implementation, an eight-thread synthetic Python child continued until the test
   timeout.
3. After the implementation, native pool values were bounded and the synthetic child was stopped
   with safety exit 86 and a thread-budget explanation.
4. An adversarial review found that the first draft scanned every host Python process, skipped
   executable paths containing spaces, could miss re-parented candidate services, allowed inherited
   detached start, and used the breach deadline during an ordinary Ctrl+C shutdown.
5. The corrected guard filters by the isolated process group before counting threads, covers a
   re-parented spaced-path Python service, rejects detached start, enforces both per-process and tree
   budgets, fails closed when a live Python process cannot be inspected, and lets SIGINT/SIGTERM
   cleanup finish. Eleven focused dev-env/resource-guard cases pass.

## Guarded Live Evidence

A fresh isolated candidate was started through the guarded `dev-env run` path while installed local
prod remained active. The candidate API, web app, browser runtime, modern playground, LiveKit,
voice gateway, MongoDB, and Meilisearch surfaces all became healthy on their isolated ports. The
candidate voice worker used 9 threads, well below the 512-thread per-process cutoff. Installed local
prod continued answering on its existing ports and was not stopped or restarted.

Headed Playwright opened the candidate web app, followed the login-to-registration navigation, and
confirmed the full registration form with zero browser-console errors. Registration is enabled only
in this isolated candidate so a local test account can be created without changing installed prod.

The candidate Telegram sidecar could not own the singleton bot/port already held by installed prod;
startup reported that truthfully and continued with the browser/voice stack. Telegram coexistence is
not counted as passed by this run. Audible call delivery and endurance stress also remain separate
gates and must not be inferred from this smoke test.
