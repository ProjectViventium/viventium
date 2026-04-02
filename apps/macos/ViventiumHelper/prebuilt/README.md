# ViventiumHelper Prebuilt Fallback

This directory holds the shipped fallback artifact for the macOS menu-bar helper.

Rules:

- source builds remain the preferred path
- direct `swiftc` compile remains the first fallback when SwiftPM fails
- this prebuilt binary is only used if local source builds fail
- the installer must only use the prebuilt artifact when `source.sha256` matches the current helper sources

Regeneration command:

```bash
./scripts/viventium/build_macos_helper_fallback.sh
```

The source hash covers:

- `apps/macos/ViventiumHelper/Package.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift`
- `apps/macos/ViventiumHelper/Sources/ViventiumHelper/Resources/Info.plist`
