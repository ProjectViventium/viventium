from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "ViventiumHelperApp.swift"
)
HELPER_PACKAGE = REPO_ROOT / "apps" / "macos" / "ViventiumHelper" / "Package.swift"
HELPER_INFO_PLIST = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumHelper"
    / "Sources"
    / "ViventiumHelper"
    / "Resources"
    / "Info.plist"
)
PREBUILT_DIR = REPO_ROOT / "apps" / "macos" / "ViventiumHelper" / "prebuilt"
PREBUILT_EXECUTABLE = PREBUILT_DIR / "ViventiumHelper-universal"
PREBUILT_SOURCE_HASH = PREBUILT_DIR / "source.sha256"


def _source_digest() -> str:
    digest = hashlib.sha256()
    helper_dir = HELPER_PACKAGE.parent
    for path in (HELPER_PACKAGE, HELPER_SOURCE, HELPER_INFO_PLIST):
        digest.update(path.relative_to(helper_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_status_bar_exposes_direct_feelings_navigation_for_running_and_stopped_stack() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")
    assert 'Button("Open Feelings")' in source
    assert "func openFeelings()" in source
    assert 'self.openBrowser(path: "/feelings")' in source
    assert 'self.startStack(openWhenReady: true, openPath: "/feelings")' in source
    assert 'alert.addButton(withTitle: "Start and Open Feelings")' in source
    assert "Start Viventium now and open Feelings in your browser?" in source
    assert re.search(
        r"private func startStack\(openWhenReady: Bool, openPath: String\? = nil, launchReason:",
        source,
    )
    assert "self.openBrowser(path: openPath)" in source
    assert "private func openBrowser(path: String? = nil)" in source


def test_prebuilt_helper_matches_source_and_contains_feelings_menu_contract() -> None:
    assert PREBUILT_EXECUTABLE.exists()
    assert PREBUILT_SOURCE_HASH.read_text(encoding="utf-8").strip() == _source_digest()
    strings = subprocess.run(
        ["strings", "-a", str(PREBUILT_EXECUTABLE)],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert "Open Feelings" in strings
    assert "Start and Open Feelings" in strings
    assert "/feelings" in strings
