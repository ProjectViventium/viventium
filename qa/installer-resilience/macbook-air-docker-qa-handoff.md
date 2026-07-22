# MacBook Air Easy Install + Docker QA Handoff

Status: BLOCKED. This is a planned physical-machine acceptance lane, not evidence that the Docker path has
passed.

## Why a physical Mac is required

The disposable macOS VM is appropriate for the lightweight native Easy Install path, but it is not a
credible acceptance environment for Docker Desktop. Tart is constrained by Apple's Virtualization
framework; its documented nested-virtualization support is for Linux guests on specific Apple
Silicon generations, not a macOS guest running Docker Desktop. Docker recommends running Docker
Desktop natively on macOS and limits its supported VM/VDI configurations. Therefore the Docker,
macOS permission, audio, sleep/wake, thermal, and real resource-contention lane belongs on the spare
MacBook Air.

Sources:

- [Tart nested virtualization FAQ](https://tart.run/faq/#nested-virtualization-support)
- [Docker Desktop VM/VDI guidance](https://docs.docker.com/desktop/setup/vm-vdi/)
- [Install Docker Desktop on Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Docker Desktop virtual machine managers on Mac](https://docs.docker.com/desktop/features/vmm/)

## Safety order

Use the first practical option. Do not erase a machine or volume without an explicit, verified
backup and separate approval.

1. Best: a sacrificial MacBook Air with a freshly erased macOS installation and no Apple Account,
   iCloud, personal Keychain, personal browser profile, or personal files.
2. Strong: a fresh macOS installation on an encrypted external APFS startup volume. Boot from that
   volume for QA and leave the internal user volume untouched.
3. Limited: a new local administrator named for synthetic QA on the existing OS. This isolates the
   user's home directory, but it is **not** a clean-machine test because Homebrew, launch daemons,
   Docker components, ports, caches, and system permissions may be shared.

Before any lane:

- complete and verify a Time Machine or equivalent encrypted backup if the Mac contains data;
- record macOS version, CPU architecture, RAM, and free disk space;
- create only synthetic Viventium users and provider accounts;
- do not sign into personal iCloud, email, messaging, browser-sync, or provider accounts;
- keep the Mac on a trusted local network or a direct Thunderbolt Bridge, with no public port
  forwarding, cloud tunnel, Tailscale, or remote-management service;
- keep FileVault and the macOS firewall enabled;
- ensure a person is physically present for macOS permission, Docker privileged-helper, provider
  consent, microphone, speaker, and recovery prompts.

## Connect the two Macs locally

On the QA MacBook Air:

1. Open **System Settings -> General -> Sharing**.
2. Turn on **Remote Login** and set **Allow access for** to only the dedicated QA user. Do not grant
   remote users Full Disk Access unless a specific test proves it is required.
3. Turn on **Screen Sharing** and restrict it to only the same QA user. Leave Remote Management,
   File Sharing, Internet Sharing, and Remote Apple Events off.
4. Note the `.local` hostname or local IP shown by macOS. Apple documents the SSH form as
   `ssh username@hostname`.
5. If normal LAN discovery is unreliable, connect the Macs with a Thunderbolt cable and use the
   **Thunderbolt Bridge** network service. Do not enable File Sharing merely to make discovery easy;
   the IP address is sufficient.

Official procedures:

- [Allow Remote Login to a Mac](https://support.apple.com/guide/mac-help/mchlp1066/mac)
- [Share the screen of another Mac](https://support.apple.com/guide/mac-help/mh14066/mac)
- [Use IP over Thunderbolt](https://support.apple.com/guide/mac-help/mchld53dd2f5/mac)

### Dedicated SSH key

On the controlling Mac, create a task-specific key. Do not reuse or send a password:

```bash
ssh-keygen -t ed25519 -f "$HOME/.ssh/viventium-qa-air" -C "viventium-local-qa"
```

Install only the `.pub` key into the dedicated QA user's `~/.ssh/authorized_keys`. The Mac owner
should do the one-time password/physical confirmation locally. Then verify a second terminal can
connect before changing any SSH authentication setting:

```bash
ssh -i "$HOME/.ssh/viventium-qa-air" <qa-user>@<qa-mac>.local
```

For temporary QA, the System Settings user allow-list plus the dedicated key and trusted local
network are the minimum. If password authentication is disabled in an `sshd_config.d` fragment,
keep physical access and verify the key-only session first to avoid lockout. At handoff, provide
only the QA hostname and QA username—never a password, recovery key, provider secret, or personal
account credential.

For visual QA, connect with the built-in Screen Sharing app or:

```bash
open "vnc://<qa-mac>.local"
```

## Physical-machine test sequence

### Baseline capture

- Confirm no Viventium checkout, App Support directory, status-bar helper, launch item, listening
  Viventium port, Mongo process, Docker container, or Viventium browser state exists.
- Capture CPU, memory pressure, swap, disk use, battery state, Docker state, listening ports, and
  enabled Sharing services.
- Save evidence outside the public repository until it has been sanitized.

### Native Easy Install control

- Run the supported public entrypoint exactly as a novice would.
- Verify one-command install, truthful progress, setup URL, registration/login, Connected Accounts,
  popup cancel/retry, Feelings discovery, restart, reboot, sleep/wake, offline recovery, and clean
  failure wording.
- Complete one synthetic provider grant and prove a first answer renders, persists after refresh,
  and survives restart. Then cover denial, wrong account, expired/revoked grant, quota/rate limit,
  provider outage, and network interruption.
- Record install time, time to first usable screen, idle and active RAM/CPU/swap, disk growth, and
  battery/thermal behavior.

### Easy Install + Docker comparison

- Install Docker Desktop from the official Mac package and have the Mac owner personally accept
  its agreement and privileged-helper prompts.
- Run the supported Docker profile from the same clean baseline where possible.
- Verify Docker-not-installed, Docker-not-running, daemon-starting, image-pull interruption,
  insufficient disk, occupied ports, container health failure, restart, reboot, sleep/wake,
  upgrade, rollback, and uninstall/cleanup behavior.
- Verify feature truth for every Docker-backed capability: search, recall/RAG, scraper, worker and
  any optional channel. A healthy core UI must not mislabel a deferred or failed capability as
  ready.
- Compare native and Docker time-to-ready, idle/active memory, CPU, swap, disk, network transfer,
  battery impact, and user-visible steps. Keep the native Easy Install path the default unless the
  Docker result adds a capability the user intentionally chose.

### Real macOS surfaces

- Status-bar helper install, relaunch, hide/show, login item, update, and uninstall.
- Gatekeeper/notarization wording and recovery from a rejected or damaged artifact.
- Keychain allow/deny/locked-state behavior without leaking secrets to logs or screenshots.
- Microphone and audio happy/denied/revoked/interrupted paths with synthetic content.
- Screen sleep, lid close/open, network change, Wi-Fi loss/recovery, and low-battery behavior.
- Keyboard-only navigation, focus visibility, VoiceOver labels, zoom, reduced motion, and a basic
  large-text pass.

## Evidence and acceptance

Every case must be marked `PASS`, `FAIL`, `PARTIAL`, or `BLOCKED` in the installer-resilience QA
source of truth with:

- exact public entrypoint and profile;
- expected and visible result;
- sanitized screenshot or transcript when a UI is required;
- relevant process/log/API/database evidence;
- persistence/restart result;
- resource measurements;
- exact remaining fix for every mismatch.

The physical lane does not pass until clean install, real Connected Account completion and first
answer, continuity/restore, helper/Keychain/Gatekeeper, Docker degraded paths, and sleep/network
recovery are all user-tested. Source inspection, mocks, or the VM lane cannot substitute for those
surfaces.

## Teardown

1. Stop Viventium and Docker using their supported commands.
2. Export only sanitized evidence; keep secrets, tokens, screenshots with personal UI, logs, and
   machine paths outside the public repository.
3. Revoke synthetic provider grants and delete synthetic accounts if their retention is not needed.
4. Remove the dedicated SSH public key, then turn off Screen Sharing and Remote Login.
5. Verify no listening QA ports, login item, helper, container, app-owned database, or synthetic
   credential remains.
6. If the machine/volume was sacrificial, erase it only after evidence and backup verification and
   with explicit owner approval.
