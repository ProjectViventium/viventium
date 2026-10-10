"""A plain start adopts the Viventium-managed Meilisearch container instead of refusing its port.

The activation launcher runs Meilisearch as a Docker container carrying this stack's own labels,
while the native stack expects a native `meilisearch --db-path` process on the same port. Without
adoption, `bin/viventium start --restart` refused the port as "owned by a foreign process or
persistence path" and could not restart its own runtime.
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin" / "viventium"


def _extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == f"{name}() {{")
    depth = 0
    collected: list[str] = []
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


_LABELLED_DOCKER_STUB = """
docker() {
  local args="$*"
  case "$args" in
    *"label=viventium.stack=viventium_v0_4"*"label=viventium.service=meilisearch"*"publish=7700"*)
      printf 'viventium-meilisearch-isolated\\n'
      ;;
    *)
      :
      ;;
  esac
}
"""


def _run(stub: str, port: str, *, path_override: str | None = None) -> subprocess.CompletedProcess[str]:
    function = _extract_shell_function(BIN.read_text(encoding="utf-8"), "viventium_meilisearch_container_owns_port")
    with tempfile.TemporaryDirectory() as temporary:
        docker = Path(temporary) / "docker"
        docker.write_text("#!/bin/bash\n" + stub + '\ndocker "$@"\n', encoding="utf-8")
        docker.chmod(0o700)
        selected_path = path_override if path_override is not None else temporary + os.pathsep + os.environ.get("PATH", "")
        prefix = f"PATH={shlex.quote(selected_path)}\nREPO_ROOT={shlex.quote(str(ROOT))}\nPYTHON_BIN={shlex.quote(sys.executable)}\n"
        script = f"set -uo pipefail\n{prefix}{function}\nviventium_meilisearch_container_owns_port {port}\n"
        process = subprocess.Popen(["/bin/bash", "-c", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=6)
            return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        finally:
            # Only this test's isolated fake CLI group; no Docker daemon or user process.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def test_adopts_only_a_labelled_container_publishing_the_port() -> None:
    assert _run(_LABELLED_DOCKER_STUB, "7700").returncode == 0
    assert _run(_LABELLED_DOCKER_STUB, "7701").returncode != 0


def test_ignores_unlabelled_containers_and_missing_docker() -> None:
    assert _run("docker() { :; }", "7700").returncode != 0
    assert _run("", "7700", path_override="/nonexistent").returncode != 0


def test_start_skips_native_meilisearch_when_the_container_owns_the_port() -> None:
    source = BIN.read_text(encoding="utf-8")
    start_block = source.split('if [[ "${VIVENTIUM_INSTALL_MODE:-docker}" == "native" ]]; then', 1)[1]
    start_block = start_block.split('"$REPO_ROOT/scripts/viventium/native_stack.sh" start', 1)[0]
    adoption = 'elif viventium_meilisearch_container_owns_port "${VIVENTIUM_LOCAL_MEILI_PORT:-7700}"; then'
    assert adoption in start_block
    after_adoption = start_block.split(adoption, 1)[1]
    assert "NATIVE_STACK_SKIP_MEILI=1" in after_adoption.split("fi", 1)[0]
    assert 'VIVENTIUM_NATIVE_STACK_SKIP_MEILI="$NATIVE_STACK_SKIP_MEILI"' in start_block


def test_stalled_docker_query_is_bounded_and_not_adopted() -> None:
    started = time.monotonic()
    result = _run('docker() { exec /bin/sleep 20; }', "7700")
    assert result.returncode != 0
    assert time.monotonic() - started < 5


def test_timed_out_partial_name_does_not_claim_ownership() -> None:
    result = _run("docker() { printf 'owned-name\\n'; exec /bin/sleep 20; }", "7700")
    assert result.returncode != 0


def test_failed_query_with_name_does_not_claim_ownership() -> None:
    result = _run("docker() { printf 'owned-name\\n'; return 1; }", "7700")
    assert result.returncode != 0
