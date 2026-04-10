from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "viventium" / "doctor.sh"


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"{name}() {{":
            start = index
            break
    if start is None:
        raise AssertionError(f"Missing shell function: {name}")

    depth = 0
    collected: list[str] = []
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break

    return "\n".join(collected) + "\n"


def test_doctor_config_flag_loader_emits_shell_assignments(tmp_path: Path) -> None:
    doctor_text = DOCTOR_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(doctor_text, "load_doctor_config_flags")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
install:
  mode: native
voice:
  mode: local
integrations:
  telegram:
    enabled: true
  google_workspace:
    enabled: false
runtime:
  personalization:
    default_conversation_recall: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PYTHON_BIN='{sys.executable}'\n"
                f"{function_def}"
                f"load_doctor_config_flags '{config_path}' '{REPO_ROOT}'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "INSTALL_MODE=native" in completed.stdout
    assert "VOICE_MODE=local" in completed.stdout
    assert "ENABLE_TELEGRAM=1" in completed.stdout
    assert "ENABLE_GOOGLE_WORKSPACE=0" in completed.stdout
    assert "ENABLE_CONVERSATION_RECALL=1" in completed.stdout
    assert "RETRIEVAL_EMBEDDINGS_PROVIDER=ollama" in completed.stdout
    assert "RETRIEVAL_EMBEDDINGS_MODEL=qwen3-embedding:0.6b" in completed.stdout
    assert "RETRIEVAL_OLLAMA_BASE_URL=http://host.docker.internal:11434" in completed.stdout


def test_doctor_check_ollama_embeddings_model_warns_when_model_missing(tmp_path: Path) -> None:
    doctor_text = DOCTOR_PATH.read_text(encoding="utf-8")
    normalize_def = extract_shell_function(doctor_text, "doctor_normalize_ollama_base_url")
    function_def = extract_shell_function(doctor_text, "doctor_check_ollama_embeddings_model")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    curl_log = tmp_path / "curl.log"
    curl_path = fake_bin / "curl"
    curl_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"printf '%s\\n' \"$*\" >> '{curl_log}'",
                "printf '%s' '{\"models\":[{\"name\":\"embeddinggemma\"}]}'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    curl_path.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PATH='{fake_bin}'\n"
                f"PYTHON_BIN='{sys.executable}'\n"
                "ENABLE_CONVERSATION_RECALL=1\n"
                "RETRIEVAL_EMBEDDINGS_PROVIDER=ollama\n"
                "RETRIEVAL_EMBEDDINGS_MODEL='qwen3-embedding:0.6b'\n"
                "RETRIEVAL_OLLAMA_BASE_URL='http://host.docker.internal:11434'\n"
                f"{normalize_def}"
                f"{function_def}"
                "doctor_check_ollama_embeddings_model\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "first start will pull it" in completed.stdout
    assert "http://localhost:11434/api/tags" in curl_log.read_text(encoding="utf-8")
