# Promotion Policy

Mission work stays inside its workspace by default. A proposed promotion records source, canonical
destination, reason, authority impact, and an authorization checkpoint in the mission receipt.

A write outside the workspace is allowed only after an explicit user instruction or an approved
checkpoint supplies `authorizedBy`, `authorizedAt`, and `checkpointRef`. Promotion never overwrites
history silently, never upgrades generated text to fact merely by moving it, and never bypasses
stricter Health, Legal, Finance, safety, or relationship rules.
