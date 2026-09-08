"""The `stop` owner record must not outlive the stopping process.

`write_stack_owner_state` names the live process that owns the stack. `start` wraps its record in
an owner transition with an EXIT trap so the record is removed or the prior live owner restored when
the process exits. `stop` wrote its record without that transition, so after an activation the
record kept claiming `command: stop` while a detached launch was running the stack.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin" / "viventium"


def _stop_case() -> str:
    source = BIN.read_text(encoding="utf-8")
    return source.rsplit("  stop)\n", 1)[1].split("    ;;", 1)[0]


def test_stop_case_wraps_its_owner_record_in_a_transition() -> None:
    stop_case = _stop_case()
    write_index = stop_case.index('write_stack_owner_state "$COMMAND"')
    assert stop_case.index("capture_stack_owner_state_for_transition") < write_index
    assert stop_case.index("STACK_OWNER_TRANSITION_ACTIVE=1") < write_index
    assert stop_case.index("trap start_owner_transition_exit_cleanup EXIT") < write_index
    assert stop_case.index("trap 'exit 143' TERM") < write_index


def test_stop_owner_record_is_reconciled_when_the_stop_process_exits(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    launcher = repo_root / "viventium_v0_4" / "viventium-librechat-start.sh"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    native_stack = repo_root / "scripts" / "viventium" / "native_stack.sh"
    native_stack.parent.mkdir(parents=True)
    native_stack.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    native_stack.chmod(0o755)
    record = tmp_path / "stack-owner.json"
    order_log = tmp_path / "order.log"

    script = f"""set -euo pipefail
acquire_cli_lock() {{ :; }}
set_helper_runtime_intent() {{ :; }}
prepare_runtime_exports() {{ :; }}
load_selected_runtime_environment_for_children() {{ :; }}
value_is_true() {{ [[ "${{1:-}}" == "true" || "${{1:-}}" == "1" ]]; }}
capture_stack_owner_state_for_transition() {{ printf 'capture\\n' >> {shlex.quote(str(order_log))}; }}
write_stack_owner_state() {{ printf 'write %s\\n' "$1" >> {shlex.quote(str(order_log))}; printf '{{"command":"%s"}}\\n' "$1" > {shlex.quote(str(record))}; }}
start_owner_transition_exit_cleanup() {{
  [[ "${{STACK_OWNER_TRANSITION_ACTIVE:-0}}" == "1" ]] || return 0
  printf 'cleanup\\n' >> {shlex.quote(str(order_log))}
  rm -f {shlex.quote(str(record))}
}}
COMMAND=stop
REPO_ROOT={shlex.quote(str(repo_root))}
GENERATED_ENV={shlex.quote(str(tmp_path / 'missing.env'))}
VIVENTIUM_DEV_ENV_SCOPE_ACTIVE=false
set --
{_stop_case()}
"""
    completed = subprocess.run(["/bin/bash", "-c", script], text=True, capture_output=True, check=False)

    assert completed.returncode == 0, completed.stderr
    assert order_log.read_text(encoding="utf-8").splitlines() == ["capture", "write stop", "cleanup"]
    assert not record.exists()


def test_detached_owner_holder_watches_the_recorded_launch_process_group() -> None:
    # The stack runs in the launcher's recorded process group, not the holder's own; the holder must
    # keep the live-owner record while that group runs.
    body = (ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    start = body.index("hold_detached_runtime_owner() {")
    end = body.index("\n}\n", start)
    loop = body[start:end]
    assert 'detached_owner_process_group_has_live_peer "$$" || detached_launch_process_group_running' in loop
