# Mission Context

## Read order

1. `MISSION.md`
2. `context/CONTEXT_MANIFEST.json`
3. `context/conversation.example.jsonl` in this template, or `conversation.jsonl` in a live mission
4. `context/attachments.json`
5. `context/life_refs.json`
6. `context/deltas.example.jsonl` in this template, or `deltas.jsonl` in a live mission
7. Relevant evidence and authorized Life references

## Orientation

This folder is a bounded agent mission under the Life contract. The context bundle preserves the
full visible task history the parent is authorized to share. It does not contain hidden reasoning,
credentials, or blanket permission to inspect all of Life.

## Continuation

Later user corrections or parent updates are appended as attributable records in
`context/deltas.jsonl`. Do not silently rewrite the original handoff. The transport must wake or
notify the worker through a supported callback/checkpoint path; appending a file alone is not a
working round-trip.
