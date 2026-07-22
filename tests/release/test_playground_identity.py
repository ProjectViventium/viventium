from __future__ import annotations

import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "viventium" / "verify_playground_identity.py"
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
LAUNCHER = START_SCRIPT
CLI = ROOT / "bin" / "viventium"
MODERN_IDENTITY_ROUTE = (
    ROOT / "viventium_v0_4" / "agent-starter-react" / "app" / "api" / "health" / "route.ts"
)
MODERN_NEXT_CONFIG = ROOT / "viventium_v0_4" / "agent-starter-react" / "next.config.ts"
MODERN_APP = (
    ROOT / "viventium_v0_4" / "agent-starter-react" / "components" / "app" / "app.tsx"
)
MODERN_GLOBAL_STYLES = (
    ROOT / "viventium_v0_4" / "agent-starter-react" / "styles" / "globals.css"
)
CLASSIC_IDENTITY_ROUTE = (
    ROOT / "viventium_v0_4" / "agents-playground" / "src" / "pages" / "api" / "health.ts"
)
CLASSIC_NEXT_CONFIG = ROOT / "viventium_v0_4" / "agents-playground" / "next.config.js"


class _IdentityHandler(BaseHTTPRequestHandler):
    status = 200
    payload: object = {}

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        body = json.dumps(self.payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _verify(payload: object, *, variant: str, source_ref: str) -> subprocess.CompletedProcess[str]:
    _IdentityHandler.payload = payload
    _IdentityHandler.status = 200
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IdentityHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return subprocess.run(
            [
                "python3",
                str(VERIFIER),
                "--base-url",
                f"http://127.0.0.1:{server.server_port}",
                "--variant",
                variant,
                "--source-ref",
                source_ref,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _identity(variant: str, source_ref: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "product": "viventium-playground",
        "status": "ok",
        "surface": f"{variant}-playground",
        "variant": variant,
        "source_ref": source_ref,
    }


def test_playground_identity_accepts_the_exact_selected_variant_and_source() -> None:
    result = _verify(_identity("modern", "a" * 40), variant="modern", source_ref="a" * 40)

    assert result.returncode == 0, result.stderr


def test_playground_identity_rejects_a_stale_classic_listener() -> None:
    result = _verify(_identity("classic", "b" * 40), variant="modern", source_ref="a" * 40)

    assert result.returncode != 0
    assert "variant" in result.stderr.lower() or "surface" in result.stderr.lower()


def test_playground_identity_rejects_a_stale_source_commit() -> None:
    result = _verify(_identity("modern", "b" * 40), variant="modern", source_ref="a" * 40)

    assert result.returncode != 0
    assert "source" in result.stderr.lower()


def test_playground_identity_rejects_a_generic_healthy_http_service() -> None:
    result = _verify({"status": "ok"}, variant="modern", source_ref="a" * 40)

    assert result.returncode != 0


def test_both_playground_surfaces_publish_build_bound_versioned_identity() -> None:
    for route, config, variant in (
        (MODERN_IDENTITY_ROUTE, MODERN_NEXT_CONFIG, "modern"),
        (CLASSIC_IDENTITY_ROUTE, CLASSIC_NEXT_CONFIG, "classic"),
    ):
        content = route.read_text()
        config_content = config.read_text()
        assert "schema_version: 1" in content
        assert re.search(r"product:\s*['\"]viventium-playground['\"]", content)
        assert re.search(rf"variant:\s*['\"]{variant}['\"]", content)
        assert "source_ref: process.env.VIVENTIUM_PLAYGROUND_COMPILED_REF" in content
        assert "source_ref: process.env.VIVENTIUM_PLAYGROUND_BUILD_REF" not in content
        assert "VIVENTIUM_PLAYGROUND_COMPILED_REF" in config_content
        assert "VIVENTIUM_PLAYGROUND_BUILD_REF" in config_content
        assert "env:" in config_content


def test_launcher_never_reuses_an_unverified_playground_listener() -> None:
    content = START_SCRIPT.read_text()

    assert "playground_listener_matches_variant" in content
    assert "kill_known_playground_listeners" in content
    assert 'VIVENTIUM_PLAYGROUND_BUILD_REF="$PLAYGROUND_SOURCE_REF"' in content
    assert 'log_success "$PLAYGROUND_LABEL already running' not in content


def test_installed_start_and_doctor_enforce_locked_component_refs() -> None:
    content = CLI.read_text()
    start_case = content.split("\n  start)\n", 1)[1].split("\n  stop)\n", 1)[0]
    doctor_case = content.split("\n  doctor)\n", 1)[1].split("\n  status)\n", 1)[0]

    assert "bootstrap_components --prefer-existing-checkout-head" not in start_case
    assert "bootstrap_components" in start_case
    assert "--prefer-existing-checkout-head" not in doctor_case


def test_installer_requires_the_exact_playground_identity() -> None:
    content = CLI.read_text()
    health_function = content.split("\nall_user_surfaces_healthy() {\n", 1)[1].split("\n}\n", 1)[0]

    assert "playground_surface_healthy" in content
    assert 'playground_surface_healthy "$playground_port"' in health_function
    assert 'frontend_surface_healthy "$playground_port"' not in health_function


def test_launcher_exports_the_exact_playground_source_to_librechat() -> None:
    launcher = LAUNCHER.read_text()

    assert 'export VIVENTIUM_PLAYGROUND_SOURCE_REF="$PLAYGROUND_SOURCE_REF"' in launcher


def test_direct_modern_playground_explains_why_voice_cannot_start() -> None:
    content = MODERN_APP.read_text()

    assert "else if (!canStartCall)" in content
    assert (
        "Open Voice from a Viventium conversation. This page joins that conversation securely."
        in content
    )


def test_modern_playground_honors_the_reduced_motion_preference() -> None:
    content = MODERN_GLOBAL_STYLES.read_text()

    assert "@media (prefers-reduced-motion: reduce)" in content
    assert "animation-duration: 0s !important" in content
    assert "transition-duration: 0s !important" in content
    assert "scroll-behavior: auto !important" in content


def test_modern_playground_does_not_center_tall_content_above_the_narrow_viewport() -> None:
    content = MODERN_APP.read_text()

    assert content.count('className="grid min-h-svh grid-cols-1 place-content-center"') == 2
    assert 'className="grid h-svh grid-cols-1 place-content-center"' not in content
