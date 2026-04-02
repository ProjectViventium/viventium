from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ensure_python_module_retries_with_break_system_packages(tmp_path: Path) -> None:
    marker = tmp_path / "yaml-installed"
    fake_base_python = tmp_path / "python3.12"
    fake_base_python.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

MARKER="{marker}"
if [[ "${{1:-}}" == "-" ]]; then
  payload="$(cat)"
  if [[ "$payload" == *'find_spec("yaml")'* ]]; then
    if [[ -f "$MARKER" ]]; then
      exit 0
    fi
    exit 1
  fi
  exit 0
fi

if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
  root="${{3:-}}"
  mkdir -p "$root/bin"
  cat >"$root/bin/python3" <<'PYEOF'
#!/usr/bin/env bash
set -euo pipefail
MARKER="{marker}"
if [[ "${{1:-}}" == "-" ]]; then
  payload="$(cat)"
  if [[ "$payload" == *'find_spec("yaml")'* && -f "$MARKER" ]]; then
    exit 0
  fi
  if [[ "$payload" == *'find_spec("yaml")'* ]]; then
    exit 1
  fi
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "--version" ]]; then
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" && "${{4:-}}" == "PyYAML" ]]; then
  echo "externally-managed-environment" >&2
  exit 1
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" && "${{4:-}}" == "--break-system-packages" && "${{5:-}}" == "PyYAML" ]]; then
  touch "$MARKER"
  exit 0
fi
exit 0
PYEOF
  chmod +x "$root/bin/python3"
  exit 0
fi

exit 0
""",
        encoding="utf-8",
    )
    fake_base_python.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_python_module '{fake_base_python}' yaml PyYAML"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(tmp_path / "bootstrap-python"),
        },
    )

    assert completed.returncode == 0
    assert marker.exists()


def test_ensure_python_requirements_file_recreates_unusable_bootstrap_python(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    bogus_python = bootstrap_root / "bin" / "python3"
    bogus_python.parent.mkdir(parents=True, exist_ok=True)
    bogus_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"pip\" && \"${3:-}\" == \"--version\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"-\" ]]; then\n"
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    bogus_python.chmod(0o755)

    marker = tmp_path / "venv-created"
    fake_base_python = tmp_path / "python3.12"
    fake_base_python.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
  root="${{3:-}}"
  mkdir -p "$root/bin"
  touch "{marker}"
  cat >"$root/bin/python3" <<'PYEOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "-" ]]; then
  cat >/dev/null
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "--version" ]]; then
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" ]]; then
  exit 0
fi
exit 0
PYEOF
  chmod +x "$root/bin/python3"
  exit 0
fi

exit 0
""",
        encoding="utf-8",
    )
    fake_base_python.chmod(0o755)

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("PyYAML==6.0.2\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_python_requirements_file '{fake_base_python}' '{requirements}'"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        },
    )

    assert completed.returncode == 0
    assert marker.exists()
    assert completed.stdout.strip() == str(bootstrap_root / "bin" / "python3")
