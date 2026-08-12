# The Portable Viventium Brain Pack

## Definition

`Viventium/Brain_Pack/` is the portable, inspectable configuration of who Viventium is and how its
special cognition behaves. It is a sibling of `Life/`, not a stripped LibreChat installation and
not a runtime database.

```text
Brain_Pack/
├── README.md
├── Character/
│   ├── Identity.md
│   ├── Emotional_Baseline.md
│   └── Voice.md
├── Cortices/
│   └── [cortex_name]_Cortex.md
├── Automations/
│   └── [automation_name]_Automation.md
├── Policies/
│   ├── Context_and_Permissions.md
│   └── Surfacing_and_Approvals.md
└── Evals/
    └── README.md
```

Character files hold editable baseline and preferences. Live Feeling values, active runs, queues,
indexes, provider sessions, and secrets remain runtime state outside the pack.

## Cortex file contract

The user's three sections stay first because they define the cortex. Four compact sections make it
portable, safe, visible, and improvable.

```markdown
---
id: red-team
display_name: Red Team
version: 1
status: enabled
execution: background
---

# 1. Activation Condition

When should this cortex activate? What evidence is sufficient? When must it remain silent?

# 2. What To Do

The cortex's goal, stance, boundaries, and useful output. Describe intelligence, not a brittle
step-by-step script.

# 3. Capabilities

## Included
- Skills, tools, MCPs, data types, and execution bodies it may use.

## Excluded
- Capabilities or scopes it must not use.

# 4. Context And Permissions

- Allowed `life://` areas and source classes
- Read/write/propose boundaries
- Sensitivity and retention rules
- Required current-turn or mission context

# 5. Output And Surfacing

- Phase A acknowledgement, if any
- Phase B contribution and evidence contract
- When to remain silent, notify, interrupt, or request approval
- Where durable outputs and receipts belong

# 6. Evaluation And Correction

- Success and failure criteria
- Required evidence and confidence
- Representative activation/non-activation evals
- Known failure modes and degradation behavior
- Owner, review date, and change history
```

## Why the added sections are necessary

- Metadata gives different hosts one stable identity and version.
- Context and permissions prevent “included tool” from becoming blanket data access.
- Output and surfacing let MIND display activation and results consistently without runtime
  keyword guesses.
- Evaluation and correction let prompt changes be proven rather than merely felt.

Do not add a giant workflow language. Markdown remains the human authority; a compiler may derive a
small typed runtime manifest and reject ambiguous or unsupported fields.
