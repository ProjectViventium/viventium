# ViventiumHelper Prebuilt Fallback

This directory holds the shipped fallback artifact for the macOS menu-bar helper.

Rules:

- the installer uses this shipped binary only when `source.sha256` matches the current helper sources and `binary.sha256` matches the exact shipped executable
- local source builds remain available for development via `VIVENTIUM_HELPER_FORCE_LOCAL_BUILD=1`
- direct `swiftc` compile remains the fallback after SwiftPM when local source builds are forced
- `binary.sha256` detects a missing, replaced, or corrupted shipped executable; it is an integrity check, not a publisher signature
- release provenance still requires the separately tracked signing/notarization gate

Regeneration command:

```bash
./scripts/viventium/build_macos_helper_fallback.sh
```

The source hash covers:

- `apps/macos/ViventiumHelper/Package.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/Resources/Info.plist`
