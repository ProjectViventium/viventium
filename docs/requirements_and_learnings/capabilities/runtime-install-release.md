# Runtime, install, and release

## User promise

A supported user installs, connects, operates, and recovers Viventium without editing runtime
internals.

### Public path

- **CORE-016:** Present one public install and activation path. Native and Docker profiles are
  implementation and recovery choices, not competing products.

### First answer

- **ONB-001:** The supported release target is a signed and notarized Apple Silicon macOS app that
  delivers a persistent first answer without developer tooling or Docker.

### Preservation

- **ONB-002:** Activation preserves user state and the complete product. Optional capability failure
  cannot block first useful chat or silently narrow existing behavior.

### First owner setup

- **ONB-003:** Setup is sparse, branded, dismissible, jargon-free, shown only when needed, and
  preserves drafted input through connection.

### Provider connection

- **ONB-004:** Offer only provider-authorized routes. Advanced credentials stay optional. Readiness
  needs a bounded live probe; fallback uses only configured, authorized, ready routes and never
  silently switches to a paid account.

### Provider lifecycle

- **ONB-005:** Connect, denial, probe failure, expiry or revocation, rate or network failure, retry,
  reauthorization, repair, disconnect or upstream revoke with scoped local-secret deletion,
  restart, and two persistent answers each produce one truthful next action while unrelated state
  survives.

### Capability preservation

- **ONB-006:** Main, continuity, memory, Call, Wing, Listen-Only, Telegram, workers, and supported
  local or remote use remain first-class after initial chat.
- Installed workers must use the user's authorized computer capabilities. Setup requests
  Accessibility and Screen Recording for the persistent Viventium app, offers access to protected
  files, and lets macOS request Automation permission for each target app. The user should only
  need the consent steps macOS requires, not worker-specific configuration or special prompts.
  Missing or revoked access stays visible and repairable from **Computer Access**; chat remains
  usable. A permission held by the installer, Terminal, Codex, or Claude is not evidence that a
  Viventium worker has it.
- The installed app's stable signing identity and launch chain must own worker access from first
  start through restart, login, and upgrade. Prove screen capture, app control, and an authorized
  browser action from the actual worker. Helper permission preflight and service health are
  supporting checks, not full computer-readiness evidence. Permissions do not authorize unrelated
  actions or remove purchase, submission, or other user-set boundaries.

### Lifecycle control

- **ONB-013:** Stop records one intentional stopped state that helpers and supervisors honor until
  explicit Start or Restart.
- Native GUI installation releases the lifecycle lock before opening the installed helper, which
  starts fresh worker services. Upgrade retires only the owned prior helper; failed startup restores
  the prior app, configuration, and runtime state. Setup acknowledgement and user preferences survive.
  `--no-start` opens the helper with stopped intent. External Stop retires its supervisor before
  recording stopped intent, and queued automatic starts honor it under the same lifecycle lock.
  Menu Stop keeps the app's Start control available; reopening a hidden app offers to show its menu.

### Developer install presentation

- **ONB-014:** Interactive developer installs show elapsed time, current step, pending surfaces, and
  failures. An optional separate playful line uses approved copy, pacing, rotation, and no-repeat
  defaults. Headless output stays plain.

### Candidate identity

- **CORE-013:** A delivered candidate binds source, component commits and pins, compiled or prebuilt
  artifacts, installed runtime identity, visible behavior, and durable state. Agent sync also proves
  source/live drift before mutation.
- **ONB-011:** Use the smallest reviewable manifest and checks. Add another registry or launcher only
  after measured drift or isolation needs prove its value.

### One-time repository reconciliation

- **ONB-010:** Repository migration preserves recoverable source and private state, classifies each
  delta, and reconciles reviewed changes before checking component pins, artifacts, installed
  runtime, and fresh QA. This is a migration gate; it does not authorize publication or activation.

### Release evidence

- **HARD-024:** Evidence is authenticated and tamper-evident from writer through evaluation; bound
  to case, owner, surface, candidate, artifact, semantic verifier, evidence, and real service
  acknowledgement; and rejects replay, stale scope, forgery, and fabricated acknowledgement.

## Owners

- Commands and lifecycle: `bin/viventium` and `scripts/viventium/`
- Configuration schema and compiler: `config.schema.yaml` and
  `scripts/viventium/config_compiler.py`
- Stack launcher: `viventium_v0_4/viventium-librechat-start.sh`
- Component delivery pins: `components.lock.json`
- Operator guide: [install and operate](../../how-to/install-and-operate.md)
- macOS access setup and app identity:
  `apps/macos/ViventiumHelper/`, `scripts/viventium/install_macos_helper.sh`, and the native
  payload signing workflows. macOS consent remains owned by the operating system.
- Upgrade and recovery: [upgrade, restore, and migrate](../../how-to/upgrade-and-migrate.md)
- QA: `qa/installer-*`, `qa/stable-dev-runtime/`, `qa/release-readiness/`, and
  `qa/config-*`

The detailed contracts below retain current install, restore, runtime, and release behavior.

## Detailed contracts

- [LibreChat v083 Config Alignment](../37_LibreChat_v083_Config_Alignment.md)
- [Public Productization and Release](../38_Public_Productization_and_Release.md)
- [Installer and Config Compiler](../39_Installer_and_Config_Compiler.md)
- [Public Private Boundaries and License Matrix](../40_Public_Private_Boundaries_and_License_Matrix.md)
- [Remote Access and Tunneling](../47_Remote_Access_and_Tunneling.md)
- [Stable Dev Runtime](../50_Stable_Dev_Runtime.md)

## macOS implementation references

Apple requires an [Automation usage description](https://developer.apple.com/documentation/bundleresources/information-property-list/nsappleeventsusagedescription)
and the [Apple Events entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.automation.apple-events)
for the applicable hardened app. Its [responsible-code guidance](https://developer.apple.com/forums/thread/702907)
explains why a helper's launch relationship and clean-machine tests matter. Keep consent in native
macOS controls; do not edit TCC databases, reset unrelated grants, or grant a development tool's
permissions and report the installed product as repaired.
