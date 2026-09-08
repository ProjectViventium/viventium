# Prompt Workbench architecture

Prompt behavior has one lineage:

```text
tracked authoring source -> registry reference -> compiler -> generated runtime -> live runtime
                                   -> Prompt Workbench view and evaluation
```

## Resolver parity

- **GOV-024:** Compile, sync, and runtime resolvers share one semantic contract for references,
  includes, strictness, variables, placeholders, order, and failure.
- **GOV-026:** Every runtime placeholder is declared. Invalid placeholders fail; valid runtime
  placeholders survive compile and sync but never leak unresolved into the model.
- Generated or installed files cannot become compiler inputs.
- Prompt changes use registered sources; hidden inline fallback text cannot alter behavior.
- Workbench reports source, compiled, and live state separately and never treats sync as evaluation.

Product behavior is owned by
[Prompt Workbench](../requirements_and_learnings/capabilities/prompt-workbench.md).
