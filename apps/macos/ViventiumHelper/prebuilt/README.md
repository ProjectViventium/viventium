# ViventiumHelper Prebuilt Fallback

This directory holds the shipped fallback artifact for the macOS menu-bar helper.

Rules:

- the installer uses this shipped binary first when `source.sha256` matches the current helper sources
- local source builds remain available for development via `VIVENTIUM_HELPER_FORCE_LOCAL_BUILD=1`
- direct `swiftc` compile remains the fallback after SwiftPM when local source builds are forced
- the installer must only use the prebuilt artifact when `source.sha256` matches the current helper sources

Regeneration command:

```bash
./scripts/viventium/build_macos_helper_fallback.sh
```

The source hash covers:

- `apps/macos/ViventiumHelper/Package.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/Resources/Info.plist`
