from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENCLAW_BRIDGE = ROOT / "viventium_v0_4" / "MCPs" / "openclaw-bridge"
OPENCLAW_VERSION = "2026.7.1-2"
OPENCLAW_INTEGRITY = (
    "sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g=="
)
OPENCLAW_LOCK_SHA256 = "e025a05ef3d268747dc293ef54876471d067f22644a8fa26a9139b7d1fe4fbc3"
SKYVERN_IMAGES = {
    "postgres@sha256:f1341c01408dc7278e9d365ed4f860cd3f87dd16b4464ac326fc0f422083a579",
    "public.ecr.aws/skyvern/skyvern@sha256:ad58d950f1c8cc3bc2d442228f701243b80b84494f11bbb066347ed034006e77",
    "public.ecr.aws/skyvern/skyvern-ui@sha256:fe43d2b11476e5d24b98b40ff9d88a1bdb89888f4ab8103336205fb204d5ef07",
}
LIVEKIT_IMAGE = (
    "livekit/livekit-server:v1.13.4@"
    "sha256:189f7c81b704a36642bc5c7e2d3e1ae83744627c11978a23a251bf19fbec64e0"
)
LIVEKIT_SOURCE_COMMIT = "0b3fd288e3ef3263ec475ba0d78cf3ad77459981"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == f"{name}() {{"),
        None,
    )
    if start is None:
        raise AssertionError(f"Missing shell function: {name}")
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def _livekit_startup_block() -> str:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    return launcher.split("# LiveKit server (Docker)", maxsplit=1)[1].split(
        "# Prepare the local LibreChat runtime files", maxsplit=1
    )[0]


def test_openclaw_reviewed_runtime_lock_is_exact() -> None:
    package_path = OPENCLAW_BRIDGE / "openclaw-runtime-lock" / "package.json"
    lock_path = OPENCLAW_BRIDGE / "openclaw-runtime-lock" / "package-lock.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    assert hashlib.sha256(lock_path.read_bytes()).hexdigest() == OPENCLAW_LOCK_SHA256
    assert package["version"] == OPENCLAW_VERSION
    assert package["overrides"] == {"fast-uri": "3.1.3"}
    assert package["dependencies"]["openclaw"].endswith(
        f"/openclaw-{OPENCLAW_VERSION}.tgz"
    )
    assert lock["packages"]["node_modules/openclaw"]["integrity"] == OPENCLAW_INTEGRITY
    assert lock["packages"]["node_modules/openclaw"]["version"] == OPENCLAW_VERSION
    assert lock["packages"]["node_modules/fast-uri"]["version"] == "3.1.3"


def test_every_openclaw_consumer_fails_closed_on_the_reviewed_runtime() -> None:
    dockerfile_path = "viventium_v0_4/MCPs/openclaw-bridge/Dockerfile"
    compose_path = "viventium_v0_4/MCPs/openclaw-bridge/docker-compose.yml"
    e2b_path = "viventium_v0_4/MCPs/openclaw-bridge/e2b_runtime.py"
    manager_path = "viventium_v0_4/MCPs/openclaw-bridge/openclaw_manager.py"
    launcher_path = "viventium_v0_4/viventium-openclaw-bridge-start.sh"
    guidance_paths = (
        "viventium_v0_4/MCPs/openclaw-bridge/README.md",
        "viventium_v0_4/MCPs/openclaw-bridge/validate.sh",
        "viventium_v0_4/MCPs/openclaw-bridge/tests/e2e_setup.py",
        "docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md",
    )
    relative_paths = (dockerfile_path, compose_path, e2b_path, manager_path, launcher_path)
    sources = {path: _read(path) for path in (*relative_paths, *guidance_paths)}
    combined = "\n".join(sources.values())

    assert "openclaw@latest" not in combined
    assert "2026.2.9" not in combined
    assert "npm install -g" not in combined

    dockerfile = sources[dockerfile_path]
    assert OPENCLAW_VERSION in dockerfile
    assert "OPENCLAW_DISABLE_BONJOUR=1" in dockerfile
    assert "FASTMCP_CHECK_FOR_UPDATES=off" in dockerfile
    assert "npm ci --omit=dev" in dockerfile
    assert "openclaw-runtime-lock" in dockerfile
    assert "COPY requirements.txt requirements.lock" in dockerfile
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    assert "e2b_runtime.py vm_registry.py vm_control.py" in dockerfile
    assert "22.23.1" in dockerfile
    assert "python:3.12.13-slim-bookworm@sha256:" in dockerfile

    compose = sources[compose_path]
    assert "OPENCLAW_RUNTIME=${OPENCLAW_RUNTIME:-e2b}" in compose
    assert "OPENCLAW_DISABLE_BONJOUR=1" in compose
    assert "FASTMCP_CHECK_FOR_UPDATES=off" in compose
    assert "127.0.0.1:${OPENCLAW_BRIDGE_PORT:-8086}:8086" in compose
    assert "OPENCLAW_BRIDGE_SECRET:?" in compose

    e2b = sources[e2b_path]
    assert OPENCLAW_VERSION in e2b
    assert OPENCLAW_LOCK_SHA256 in e2b
    assert "OPENCLAW_DISABLE_BONJOUR=1" in e2b
    assert 'OPENCLAW_E2B_RUNTIME_ROOT = "/opt/viventium/openclaw-runtime"' in e2b
    assert 'OPENCLAW_LOCK={shlex.quote(f"{OPENCLAW_E2B_RUNTIME_ROOT}/package-lock.json")}' in e2b
    assert 'OPENCLAW_BIN={shlex.quote(f"{OPENCLAW_E2B_RUNTIME_ROOT}/node_modules/.bin/openclaw")}' in e2b

    manager = sources[manager_path]
    assert OPENCLAW_VERSION in manager
    assert 'OPENCLAW_DISABLE_BONJOUR = "1"' in manager
    assert 'os.environ.get("OPENCLAW_RUNTIME", "e2b")' in manager
    assert "OPENCLAW_ALLOW_DIRECT_HOST_EXEC" in manager
    assert '"OPENCLAW_RUNTIME_ALLOW_FALLBACK", "false"' in manager
    assert 'raise ValueError("OPENCLAW_RUNTIME must be direct or e2b")' in manager

    launcher = sources[launcher_path]
    assert OPENCLAW_VERSION in launcher
    assert 'OPENCLAW_REQUIRED_NODE_VERSION="22.23.1"' in launcher
    assert "nodejs.org/dist/v${OPENCLAW_REQUIRED_NODE_VERSION}" in launcher
    assert "ef28d8fab2c0e4314522d4bb1b7173270aa3937e93b92cb7de79c112ac1fa953" in launcher
    assert "b8da981b8a0b1241b70249204916da76c63573ddf5814dbd2d1e41069105cb81" in launcher
    assert OPENCLAW_LOCK_SHA256 in launcher
    assert "export OPENCLAW_DISABLE_BONJOUR=1" in launcher
    assert "export FASTMCP_CHECK_FOR_UPDATES=off" in launcher
    assert "npm ci --omit=dev" in launcher
    assert "OPENCLAW_RUNTIME_LOCK_DIR" in launcher
    assert "OPENCLAW_PYTHON_LOCK_SHA256" in launcher
    assert "pip install --disable-pip-version-check --require-hashes" in launcher
    assert "pip3 install" not in launcher
    assert 'OPENCLAW_ISOLATION_TIER:-e2b' in launcher
    native_start = _extract_shell_function(launcher, "start_native")
    assert "ensure_bridge_secret" in native_start


def test_openclaw_launch_output_never_prints_secret_prefixes() -> None:
    launcher = _read("viventium_v0_4/viventium-openclaw-bridge-start.sh")
    manager = _read("viventium_v0_4/MCPs/openclaw-bridge/openclaw_manager.py")
    assert "ANTHROPIC_API_KEY:0:" not in launcher
    assert 'Anthropic Key:    ${GREEN}Configured${NC}' in launcher
    assert '" ".join(cmd)' not in manager


def test_voice_launcher_never_prints_secret_or_provider_key_prefixes() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")

    assert "_secret_mask" not in launcher
    assert "VIVENTIUM_CALL_SESSION_SECRET:0:" not in launcher
    for variable in (
        "OPENAI_API_KEY",
        "ELEVEN_API_KEY",
        "ELEVEN_API_KEY_FINAL",
        "XAI_API_KEY",
        "CARTESIA_API_KEY",
    ):
        assert f"${{{variable}:0:" not in launcher


def test_voice_call_diagnostics_never_emit_user_or_session_payloads() -> None:
    route = _read("viventium_v0_4/LibreChat/api/server/routes/viventium/calls.js")
    service = _read(
        "viventium_v0_4/LibreChat/api/server/services/viventium/CallSessionService.js"
    )
    button = _read("viventium_v0_4/LibreChat/client/src/components/Viventium/CallButton.tsx")

    assert "console." not in route
    assert "console." not in button
    for forbidden in (
        "body: req.body",
        "userId: req.user",
        "Session created:",
        "Response:",
        "callSessionId=${callSessionId}",
        "newConversationId=${conversationId}",
        "conversationId to ${conversationId}",
    ):
        assert forbidden not in route
        assert forbidden not in service


def test_skyvern_runtime_images_are_immutable() -> None:
    compose = _read("viventium_v0_4/docker/skyvern/docker-compose.yml")
    for image in SKYVERN_IMAGES:
        assert f"image: {image}" in compose
    assert "postgres:14-alpine" not in compose
    assert "public.ecr.aws/skyvern/skyvern:latest" not in compose
    assert "public.ecr.aws/skyvern/skyvern-ui:latest" not in compose


def test_livekit_runtime_image_is_immutable_and_release_locked() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    manifest = json.loads(_read("release/optional-runtime-components.json"))
    livekit = manifest["livekit_server"]

    assert livekit["version"] == "v1.13.4"
    assert livekit["source_commit"] == LIVEKIT_SOURCE_COMMIT
    assert livekit["image"] == LIVEKIT_IMAGE
    assert livekit["publisher_signature"] == "not_provided"
    assert livekit["provenance"] == "slsa-v1-per-platform"
    assert LIVEKIT_IMAGE in launcher
    assert '"viventium.livekit.image=${LIVEKIT_SERVER_IMAGE}"' in launcher
    assert '"viventium.livekit.source=${LIVEKIT_SERVER_SOURCE_COMMIT}"' in launcher
    assert "docker image inspect livekit/livekit-server" not in launcher
    assert "elif ! docker image inspect" not in launcher
    assert "\n              livekit/livekit-server\n" not in launcher


def _run_legacy_voice_launcher(
    tmp_path: Path,
    *args: str,
    include_canonical: bool = True,
) -> subprocess.CompletedProcess[str]:
    launcher_dir = tmp_path / "viventium_v0_4"
    launcher_dir.mkdir(exist_ok=True)
    legacy_launcher = launcher_dir / "viventium-start-all.sh"
    legacy_launcher.write_text(
        _read("viventium_v0_4/viventium-start-all.sh"),
        encoding="utf-8",
    )
    legacy_launcher.chmod(0o755)

    capture_path = tmp_path / "canonical-args.txt"
    capture_path.unlink(missing_ok=True)
    canonical_launcher = launcher_dir / "viventium-librechat-start.sh"
    if include_canonical:
        canonical_launcher.write_text(
            "#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$VIVENTIUM_LEGACY_LAUNCHER_CAPTURE\"\n",
            encoding="utf-8",
        )
        canonical_launcher.chmod(0o755)

    return subprocess.run(
        [str(legacy_launcher), *args],
        cwd=tmp_path,
        env={
            **os.environ,
            "VIVENTIUM_LEGACY_LAUNCHER_CAPTURE": str(capture_path),
        },
        check=False,
        capture_output=True,
        text=True,
    )


def test_legacy_voice_launcher_delegates_to_locked_modern_runtime(tmp_path: Path) -> None:
    launcher = _read("viventium_v0_4/viventium-start-all.sh")

    completed = _run_legacy_voice_launcher(tmp_path)
    captured = (tmp_path / "canonical-args.txt").read_text(encoding="utf-8").splitlines()

    assert completed.returncode == 0, completed.stderr
    assert captured == ["--modern-playground"]

    completed = _run_legacy_voice_launcher(tmp_path, "--no-playground")
    captured = (tmp_path / "canonical-args.txt").read_text(encoding="utf-8").splitlines()

    assert completed.returncode == 0, completed.stderr
    assert captured == ["--modern-playground", "--skip-playground"]
    assert "viventium-librechat-start.sh" in launcher
    assert "livekit/livekit-server" not in launcher
    assert "docker run" not in launcher
    assert "npm install" not in launcher
    assert "npm ci" not in launcher
    assert "cat >>" not in launcher
    assert "pkill" not in launcher
    assert "LiveKit Agents Playground" not in launcher


def test_active_voice_guide_names_the_modern_playground_as_the_default() -> None:
    voice_guide = _read("viventium_v0_4/docs/VOICE_CALLS.md")

    assert "Viventium Modern Playground (`agent-starter-react`)" in voice_guide
    assert "The Viventium Modern Playground connects" in voice_guide
    assert "design intentionally opens the LiveKit Agents Playground" not in voice_guide
    assert "The LiveKit Agents Playground connects" not in voice_guide


def test_active_feature_docs_name_modern_playground_as_default() -> None:
    no_response = _read("docs/requirements_and_learnings/21_No_Response_Feature.md")
    citations = _read("docs/requirements_and_learnings/08_Citation_Rendering.md")

    assert "Viventium Modern Playground (`agent-starter-react`)" in no_response
    assert "LiveKit Agents Playground" not in no_response
    assert "LiveKit Playground UI" not in no_response
    assert "Modern playground sanitization (`agent-starter-react`, default)" in citations
    assert (
        "Classic playground sanitization (`agents-playground`, explicit opt-in fallback)"
        in citations
    )
    assert "Viventium Modern Playground chat display (default browser voice UI)" in citations


def test_legacy_voice_launcher_rejects_dependency_mutation_flags(tmp_path: Path) -> None:
    for flag in ("--build", "--clean", "--install-deps"):
        completed = _run_legacy_voice_launcher(tmp_path, flag)

        assert completed.returncode != 0
        assert "no longer supported" in completed.stderr
        assert "viventium-librechat-start.sh" in completed.stderr
        assert not (tmp_path / "canonical-args.txt").exists()


def test_legacy_voice_launcher_fails_closed_on_unknown_option_or_missing_owner(
    tmp_path: Path,
) -> None:
    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    completed = _run_legacy_voice_launcher(unknown_root, "--classic-playground")

    assert completed.returncode != 0
    assert "unknown legacy launcher option" in completed.stderr
    assert not (unknown_root / "canonical-args.txt").exists()

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    completed = _run_legacy_voice_launcher(missing_root, include_canonical=False)

    assert completed.returncode != 0
    assert "canonical Viventium launcher is missing or not executable" in completed.stderr
    assert not (missing_root / "canonical-args.txt").exists()


def test_native_livekit_never_executes_an_unverified_path_binary() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    native_stack = _read("scripts/viventium/native_stack.sh")
    cli = _read("bin/viventium")
    startup = _livekit_startup_block()

    assert "livekit_native_binary_path" not in launcher
    assert "start_native_livekit_fallback" not in launcher
    assert "command -v livekit-server" not in launcher
    assert "command -v livekit" not in launcher
    assert "ensure_livekit_binary" not in native_stack
    assert "command -v livekit-server" not in native_stack
    assert "command -v livekit" not in native_stack
    assert "Native LiveKit startup is not a verified release path" in native_stack
    native_start_case = native_stack.split('  start)', maxsplit=1)[1].split(
        "    ;;", maxsplit=1
    )[0]
    assert native_start_case.index("validate_native_livekit_startup") < native_start_case.index(
        "start_mongo"
    )
    assert "VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT=1" in cli
    assert "VIVENTIUM_INSTALL_MODE" not in startup
    assert "require_cmd docker" in startup
    assert '"$LIVEKIT_SERVER_IMAGE"' in startup
    assert "using external LiveKit if available" not in startup
    assert "refusing to treat it as LiveKit" in startup
    assert "Configured LiveKit endpoint did not respond" in startup
    assert startup.index("Configured LiveKit endpoint did not respond") < startup.index(
        "require_cmd docker"
    )
    assert (
        "Voice needs the exact Viventium LiveKit Docker runtime or a deliberately configured "
        "external LiveKit endpoint."
    ) in launcher
    assert "Use --skip-livekit to start without Voice." in launcher


def test_native_no_docker_path_fails_before_path_livekit_can_run(tmp_path: Path) -> None:
    marker = tmp_path / "path-livekit-ran"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_livekit = fake_bin / "livekit-server"
    fake_livekit.write_text(
        f"#!/bin/sh\ntouch '{marker}'\n",
        encoding="utf-8",
    )
    fake_livekit.chmod(0o755)
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=true
LIVEKIT_API_HOST_WAS_CONFIGURED=true
LIVEKIT_API_HOST=http://127.0.0.1:17880
wait_for_http() {{ return 1; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not marker.exists()
    assert "Voice needs the exact Viventium LiveKit Docker runtime" in completed.stdout
    assert "Use --skip-livekit to start without Voice" in completed.stdout


def test_skip_docker_rejects_an_implicit_default_livekit_listener(tmp_path: Path) -> None:
    probe_marker = tmp_path / "endpoint-probed"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=true
LIVEKIT_API_HOST_WAS_CONFIGURED=false
LIVEKIT_API_HOST=http://127.0.0.1:17880
wait_for_http() {{ touch '{probe_marker}'; return 0; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not probe_marker.exists()
    assert "No external LiveKit endpoint was configured" in completed.stdout


def test_unhealthy_configured_livekit_fails_before_docker_fallback(tmp_path: Path) -> None:
    docker_marker = tmp_path / "docker-ran"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=false
LIVEKIT_API_HOST_WAS_CONFIGURED=true
LIVEKIT_API_HOST=http://127.0.0.1:17880
curl() {{ return 1; }}
docker() {{ touch '{docker_marker}'; return 1; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not docker_marker.exists()
    assert "Configured LiveKit endpoint did not respond" in completed.stdout
    assert "refusing an implicit runtime fallback" in completed.stdout


def test_unconfigured_livekit_port_collision_is_preserved_and_rejected(tmp_path: Path) -> None:
    listener_marker = tmp_path / "unrelated-listener"
    listener_marker.write_text("preserve", encoding="utf-8")
    docker_log = tmp_path / "docker.log"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=false
LIVEKIT_API_HOST_WAS_CONFIGURED=false
LIVEKIT_API_HOST=http://127.0.0.1:17880
VIVENTIUM_RUNTIME_PROFILE=isolated
LIVEKIT_HTTP_PORT=17880
require_cmd() {{ :; }}
docker_daemon_ready() {{ return 0; }}
docker() {{ printf '%s\n' "$*" >>'{docker_log}'; }}
port_in_use() {{ return 0; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
log_warn() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert listener_marker.read_text(encoding="utf-8") == "preserve"
    assert "refusing to treat it as LiveKit" in completed.stdout
    assert "run -d" not in docker_log.read_text(encoding="utf-8")


def test_stale_managed_livekit_container_is_never_silently_reused() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    assert "livekit_managed_container_matches_release" in launcher
    assert "Replacing stale managed LiveKit container" in launcher
    assert 'docker rm -f "$EXISTING"' in launcher


def test_livekit_release_identity_requires_image_and_source_labels() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    function_def = _extract_shell_function(
        launcher, "livekit_managed_container_matches_release"
    )
    script = f"""
set -euo pipefail
LIVEKIT_SERVER_IMAGE='{LIVEKIT_IMAGE}'
LIVEKIT_SERVER_SOURCE_COMMIT='{LIVEKIT_SOURCE_COMMIT}'
MOCK_SOURCE='{LIVEKIT_SOURCE_COMMIT}'
docker() {{
  case "$3" in
    *Config.Image*) printf '%s\\n' "$LIVEKIT_SERVER_IMAGE" ;;
    *viventium.livekit.image*) printf '%s\\n' "$LIVEKIT_SERVER_IMAGE" ;;
    *viventium.livekit.source*) printf '%s\\n' "$MOCK_SOURCE" ;;
    *) return 1 ;;
  esac
}}
{function_def}
livekit_managed_container_matches_release exact && printf 'exact\\n'
MOCK_SOURCE='stale-source'
if livekit_managed_container_matches_release stale; then
  printf 'unsafe-reuse\\n'
else
  printf 'rejected\\n'
fi
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == ["exact", "rejected"]


def test_optional_launchers_reference_existing_owning_docs() -> None:
    for relative in (
        "viventium_v0_4/viventium-openclaw-bridge-start.sh",
        "viventium_v0_4/viventium-skyvern-start.sh",
        "viventium_v0_4/docker/skyvern/docker-compose.yml",
    ):
        source = _read(relative)
        for line in source.splitlines():
            if "Documentation: docs/" not in line:
                continue
            target = line.split("Documentation:", 1)[1].strip()
            assert (ROOT / target).is_file(), f"{relative} points to missing {target}"
