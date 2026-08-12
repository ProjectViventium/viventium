# Mission Questions

Typed worker-to-parent questions, blockers, permission requests, and responses. Start from
[`question.example.json`](question.example.json) and validate against the portable question schema.

Use this only when the worker cannot proceed safely or faithfully with the available context. A
question is not live until it is paired with a supported callback/checkpoint event and an observable
status transition; a file silently waiting here is not a transport.
