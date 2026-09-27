from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
SEED_FUNCTIONS = (
    "detect_compiled_viventium_agents_bundle",
    "detect_viventium_release_agents_bundle",
    "detect_viventium_agents_bundle",
    "ensure_viventium_agents_seeded",
)
# The seed refuses any bundle other than the one a pending migration targets, then consumes it.
SEED_STUB = r"""
log_info() { :; }
log_warn() { printf 'warn:%s\n' "$*" >>"$CALLS"; }
log_error() { printf 'error:%s\n' "$*" >>"$CALLS"; }
log_success() { :; }
ensure_librechat_server_packages_ready() { return 0; }
node() {
  local arg="" bundle="" state=""
  for arg in "$@"; do
    case "$arg" in
      --bundle=*) bundle="${arg#--bundle=}" ;;
      --managed-migration-state=*) state="${arg#--managed-migration-state=}" ;;
    esac
  done
  if [[ -e "$state" ]]; then
    if [[ "$bundle" != "$(cat "$state")" ]]; then
      echo "Managed migration state targets a different agent bundle." >&2
      return 1
    fi
    rm -f "$state"
    printf 'seed:%s:migration\n' "$bundle" >>"$CALLS"
    return 0
  fi
  printf 'seed:%s\n' "$bundle" >>"$CALLS"
}
"""


def extract_shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    collected: list[str] = []
    depth = 0
    for line in source[start:].splitlines():
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


@pytest.fixture
def install(tmp_path: Path) -> dict[str, Path]:
    librechat = tmp_path / "librechat"
    tracked = librechat / "viventium" / "source_of_truth" / "local.viventium-agents.yaml"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("mainAgent: {id: agent_main, model: tracked}\n", encoding="utf-8")
    (librechat / "scripts").mkdir()
    (librechat / "scripts" / "viventium-seed-agents.js").write_text("", encoding="utf-8")
    compiled = tmp_path / "support" / "runtime" / "viventium-agents.yaml"
    compiled.parent.mkdir(parents=True)
    compiled.write_text("mainAgent: {id: agent_main, model: configured}\n", encoding="utf-8")
    curated = tmp_path / "curated" / "local.viventium-agents.yaml"
    curated.parent.mkdir()
    curated.write_text("mainAgent: {id: agent_main, model: curated}\n", encoding="utf-8")
    return {
        "root": tmp_path,
        "librechat": librechat,
        "tracked": tracked,
        "compiled": compiled,
        "curated": curated,
        "pending": tmp_path / "support" / "state" / "runtime" / "agent-managed-migration-pending.json",
        "calls": tmp_path / "calls.txt",
    }


def seed(install: dict[str, Path], *, mode: str = "native", curated: bool = False) -> tuple[int, list[str]]:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    functions = "".join(extract_shell_function(launcher, name) for name in SEED_FUNCTIONS)
    root = install["root"]
    env = {
        **os.environ,
        "CALLS": str(install["calls"]),
        "LIBRECHAT_DIR": str(install["librechat"]),
        "LOG_DIR": str(root / "logs"),
        "VIVENTIUM_APP_SUPPORT_ROOT": str(root / "support"),
        "VIVENTIUM_RUNTIME_DIR": str(install["compiled"].parent),
        "VIVENTIUM_STATE_ROOT": str(root / "support" / "state"),
        "VIVENTIUM_BASE_STATE_DIR": str(root / "support" / "state"),
        "VIVENTIUM_INSTALL_MODE": mode,
    }
    env.pop("LIBRECHAT_AGENTS_BUNDLE_FILE", None)
    if curated:
        env["LIBRECHAT_AGENTS_BUNDLE_FILE"] = str(install["curated"])
    (root / "logs").mkdir(exist_ok=True)
    result = subprocess.run(
        ["bash", "-c", functions + SEED_STUB + "ensure_viventium_agents_seeded"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = install["calls"].read_text(encoding="utf-8").splitlines() if install["calls"].exists() else []
    return result.returncode, calls


def pend_migration(install: dict[str, Path]) -> None:
    install["pending"].parent.mkdir(parents=True, exist_ok=True)
    install["pending"].write_text(str(install["tracked"]), encoding="utf-8")


def test_native_start_seeds_the_compiled_agent_routes(install: dict[str, Path]) -> None:
    assert seed(install) == (0, [f"seed:{install['compiled']}"])


def test_explicit_curated_bundle_stays_authoritative(install: dict[str, Path]) -> None:
    assert seed(install, curated=True) == (0, [f"seed:{install['curated']}"])


def test_pending_migration_finishes_on_its_release_bundle_before_compiled_routes(
    install: dict[str, Path],
) -> None:
    pend_migration(install)

    assert seed(install) == (
        0,
        [f"seed:{install['tracked']}:migration", f"seed:{install['compiled']}"],
    )
    assert not install["pending"].exists()


def test_pending_migration_without_its_release_bundle_fails_before_seeding(
    install: dict[str, Path],
) -> None:
    pend_migration(install)
    install["tracked"].unlink()

    returncode, calls = seed(install)

    assert returncode == 1
    assert calls == ["error:The pending managed-agent migration needs its release agent bundle"]
    assert install["pending"].exists()


def test_docker_mode_ignores_a_stale_compiled_bundle(install: dict[str, Path]) -> None:
    assert seed(install, mode="docker") == (0, [f"seed:{install['tracked']}"])


def test_symlinked_compiled_bundle_is_not_seeded(install: dict[str, Path]) -> None:
    target = install["root"] / "elsewhere.yaml"
    install["compiled"].replace(target)
    install["compiled"].symlink_to(target)

    assert seed(install) == (0, [f"seed:{install['tracked']}"])
