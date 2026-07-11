from __future__ import annotations


PERIPHERY_REQUIRED_FIELDS = (
    "schemaVersion",
    "moduleId",
    "generatedAt",
    "snapshotRef",
    "scheduledRunRef",
    "sourceRefs",
    "confidence",
    "severity",
    "timeSensitivity",
    "ttl",
    "staleAfter",
    "observations",
    "risks",
    "blindSpots",
    "opportunityCosts",
    "opportunities",
    "whatWouldMakeThisWrong",
    "whenToSurface",
    "proposedActions",
    "memoryProposalRefs",
)

PERIPHERY_CONTENT_FIELDS = (
    "observations",
    "risks",
    "blindSpots",
    "opportunityCosts",
    "opportunities",
    "whatWouldMakeThisWrong",
    "whenToSurface",
    "proposedActions",
    "memoryProposalRefs",
)

NIGHTLY_PROMPT_TEMPLATE = """Review the private evidence in `scheduled-prompt/periphery-snapshot.json` and notice only material risks, blind spots, opportunity costs, or opportunities. Use sourceRef values from that snapshot for every non-trivial claim. Separate observations, inferences, and hypotheses. Do not invent urgency, current facts, medical conclusions, or insight when the evidence is weak.

Write one private risk_radar artifact for this run. Use {{local.viventium.my_folder}} and write paired .md and .json files under:
periphery/risk_radar/YYYY/MM/YYYYMMDDTHHMMSSZ.risk_radar.md
periphery/risk_radar/YYYY/MM/YYYYMMDDTHHMMSSZ.risk_radar.json

Use schemaVersion 2 and moduleId "risk_radar". Copy snapshotRef and scheduledRunRef from `scheduled-prompt/run-context.json`. The JSON sidecar must include: schemaVersion, moduleId, generatedAt, snapshotRef, scheduledRunRef, sourceRefs, confidence, severity, timeSensitivity, ttl, staleAfter, observations, risks, blindSpots, opportunityCosts, opportunities, whatWouldMakeThisWrong, whenToSurface, proposedActions, memoryProposalRefs. Every object in an insight array must include its own sourceRefs chosen from the top-level sourceRefs. A no-result or missing-prerequisite observation may use an empty sourceRefs array.

Keep both files concise and evidence-first. If there is no strong evidence, leave every content array empty except for one observations object with kind "no_result" or "missing_prerequisite", a short text, and sourceRefs: []. Do not add a saved-memory key, inject the artifact into chat, copy raw conversations into the sidecar, or create memory proposals unless the evidence supports a genuinely durable fact.

# snapshot manifest = {{viventium.periphery.snapshot}}
"""
