# Project Vision

## Core Idea
Viventium is a brain-inspired voice AI system where a single conscious agent handles live dialogue while multiple specialized background agents analyze in parallel. The system should feel like one coherent mind with fast, natural voice interaction and non-blocking background reasoning.

## Original Inspiration (v0.3)
- A frontal cortex agent speaks to the user in real time.
- Subconscious cortices run in parallel to check facts, plan, and research.
- Insights are written to shared state and surfaced organically by the conscious agent.

## Evolution (v0.4)
- The UI and product language shifted from neuroscience terms to "Background Agents" to keep UX clean.
- LibreChat now hosts the main agent pipeline with background activation and follow-ups.
- Voice-first realism (low latency, barge-in, micro human cues) is a core requirement.

## Non-Negotiable Principles
- Non-blocking background processing: the main response must never wait on background agents.
- Separation of concerns: capture, routing, execution, storage, and synthesis remain distinct.
- Voice realism: responses should sound like a natural phone call, not a narrator.
- Extensibility: new background agents or cortices must be easy to add.
- Traceable changes: upstream edits must be marked with VIVENTIUM START/END.

## Success Criteria
- Voice conversations feel real-time and interruptible.
- Background analysis improves quality without delaying responses.
- Single source of truth documentation is maintained for every feature.
- Both stacks can run independently without breaking each other.
