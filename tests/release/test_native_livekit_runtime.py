from __future__ import annotations

import hashlib
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

from test_native_stack_helpers import extract_shell_function


ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "scripts/viventium/native_stack.sh"


def shell(definitions: str, setup: str, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + setup + "\n" + definitions + command],
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("system,arch,version", [("Linux", "arm64", "26.0"), ("Darwin", "x86_64", "26.0"), ("Darwin", "arm64", "14.0")])
def test_native_livekit_refuses_unsupported_platform_before_artifact_or_listener_access(system, arch, version):
    source = NATIVE.read_text()
    definitions = "".join(extract_shell_function(source, name) for name in (
        "native_livekit_start_requested", "validate_native_livekit_startup"))
    setup = f'''VOICE_ENABLED=true
NATIVE_STACK_SKIP_LIVEKIT=0
VIVENTIUM_LIVEKIT_RUNTIME=native
VIVENTIUM_NATIVE_LIVEKIT_LATE_START=1
uname() {{ if [[ $1 == -s ]]; then echo {system}; else echo {arch}; fi; }}
sw_vers() {{ echo {version}; }}
'''
    result = shell(definitions, setup, "validate_native_livekit_startup\n")
    assert result.returncode == 1
    assert "requires macOS 15 or newer on ARM64" in result.stderr


@pytest.mark.parametrize("valid", [True, False])
def test_native_livekit_cached_artifact_is_verified_without_path_adoption_or_network(tmp_path, valid):
    binary = tmp_path / "pinned" / "livekit-server"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\nprintf 'livekit-server version 1.13.4\\n'\n")
    binary.chmod(0o755)
    expected = hashlib.sha256(binary.read_bytes()).hexdigest() if valid else "0" * 64
    definition = extract_shell_function(NATIVE.read_text(), "prepare_pinned_livekit_binary")
    setup = "\n".join(f"{k}={shlex.quote(str(v))}" for k, v in {
        "LIVEKIT_NATIVE_BINARY": binary,
        "LIVEKIT_NATIVE_BINARY_SHA256": expected,
        "LIVEKIT_NATIVE_BOTTLE_SHA256": "unused-for-cached-artifact",
    }.items())
    result = shell(definition, setup, "prepare_pinned_livekit_binary\n")
    assert result.returncode == (0 if valid else 1)
    if valid:
        assert result.stdout.strip() == str(binary)
    else:
        assert "cache identity failed" in result.stderr
        assert binary.read_text().startswith("#!/bin/sh")


@pytest.mark.parametrize("receipt_matches", [True, False])
def test_native_livekit_reuses_only_matching_receipt_without_restarting(receipt_matches):
    definition = extract_shell_function(NATIVE.read_text(), "start_livekit")
    setup = f'''NATIVE_STACK_SKIP_LIVEKIT=0
VOICE_ENABLED=true
validate_native_livekit_startup() {{ return 0; }}
prepare_pinned_livekit_binary() {{ echo /synthetic/pinned/livekit-server; }}
managed_livekit_listener_pid() {{ echo 4242; }}
livekit_meta_matches_expected() {{ return {0 if receipt_matches else 1}; }}
nohup() {{ echo SHOULD_NOT_START; return 1; }}
stop_livekit() {{ echo SHOULD_NOT_STOP; return 1; }}
'''
    result = shell(definition, setup, "start_livekit\n")
    assert result.returncode == (0 if receipt_matches else 1)
    assert "SHOULD_NOT" not in result.stdout
    assert "VIVENTIUM_NATIVE_LIVEKIT_STARTED=0" in result.stdout if receipt_matches else "receipt differs" in result.stderr


def test_native_livekit_refuses_unowned_port_without_stopping_it():
    definition = extract_shell_function(NATIVE.read_text(), "start_livekit")
    result = shell(definition, '''NATIVE_STACK_SKIP_LIVEKIT=0
VOICE_ENABLED=true
LIVEKIT_HTTP_PORT=17888
LIVEKIT_TCP_PORT=17889
validate_native_livekit_startup() { return 0; }
prepare_pinned_livekit_binary() { echo /synthetic/pinned/livekit-server; }
managed_livekit_listener_pid() { return 1; }
port_listening() { return 0; }
stop_livekit() { echo SHOULD_NOT_STOP; }
''', "start_livekit\n")
    assert result.returncode == 1
    assert "unowned listener" in result.stderr
    assert "SHOULD_NOT_STOP" not in result.stdout


@pytest.mark.parametrize("runtime", ["docker", "native"])
def test_native_livekit_limits_host_candidates_and_listener_scope_without_losing_public_mapping(tmp_path, runtime):
    source = (ROOT / "viventium_v0_4/viventium-librechat-start.sh").read_text()
    definitions = "".join(extract_shell_function(source, name) for name in (
        "livekit_public_node_ip_configured", "write_livekit_config"))
    target = tmp_path / "livekit.yaml"
    setup = f'''VIVENTIUM_LIVEKIT_RUNTIME={runtime}
LIVEKIT_NODE_IP=1.1.1.1
LIVEKIT_HTTP_PORT=17888
LIVEKIT_TCP_PORT=17889
LIVEKIT_UDP_PORT=17890
LIVEKIT_TURN_DOMAIN=voice.example.test
LIVEKIT_TURN_TLS_PORT=15349
LIVEKIT_API_KEY=synthetic
LIVEKIT_API_SECRET=synthetic
native_livekit_lan_ip() {{ echo 192.168.50.10; }}
'''
    result = shell(definitions, setup, f"write_livekit_config {shlex.quote(str(target))} /synthetic/turn.crt /synthetic/turn.key\n")
    assert result.returncode == 0, result.stderr
    config = yaml.safe_load(target.read_text())
    assert config["rtc"]["use_external_ip"] is True
    assert config["rtc"]["advertise_internal_ip"] is True
    if runtime == "native":
        assert config["bind_addresses"] == ["127.0.0.1", "::1"]
        assert config["rtc"]["ips"]["includes"] == ["192.168.50.10/32"]
        assert config["rtc"]["enable_loopback_candidate"] is False
        assert config["turn"]["bind_addresses"] == ["192.168.50.10"]
        assert config["turn"]["allow_restricted_peer_cidrs"] == []
    else:
        assert "bind_addresses" not in config
        assert "ips" not in config["rtc"]
        assert config["rtc"]["enable_loopback_candidate"] is True
        assert "bind_addresses" not in config["turn"]


@pytest.mark.parametrize("configured,expected", [("", "192.168.50.10"), ("192.168.50.10", "192.168.50.10"), ("192.168.50.11", None), ("127.0.0.1", None), ("169.254.1.10", None), ("2001:db8::1", None)])
def test_native_livekit_reuses_edge_address_detection_and_rejects_stale_or_non_lan_address(tmp_path, configured, expected):
    edge = tmp_path / "edge.py"
    edge.write_text('def detect_lan_ipv4(): return "192.168.50.10"\ndef assigned_local_ipv4s(): return {"192.168.50.10"}\n')
    source = (ROOT / "viventium_v0_4/viventium-librechat-start.sh").read_text()
    definition = extract_shell_function(source, "native_livekit_lan_ip")
    setup = f"VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT={shlex.quote(str(edge))}\nVIVENTIUM_LAN_IP={shlex.quote(configured)}\n"
    result = shell(definition, setup, "native_livekit_lan_ip\n")
    if expected:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected
    else:
        assert result.returncode != 0
        assert "Native LiveKit LAN address" in result.stderr
