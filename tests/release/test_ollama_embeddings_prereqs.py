from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"{name}() {{":
            start = index
            break
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


def test_ensure_ollama_embedding_model_for_rag_pulls_missing_model(tmp_path: Path) -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    function_names = [
        "ollama_embeddings_enabled_for_rag",
        "ollama_host_base_url",
        "ollama_tags_json",
        "ollama_embedding_model_name",
        "ollama_model_present",
        "ollama_pull_model",
        "ensure_ollama_embedding_model_for_rag",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    tags_path = tmp_path / "tags.json"
    tags_path.write_text('{"models":[]}\n', encoding="utf-8")
    curl_log = tmp_path / "curl.log"
    pull_log = tmp_path / "pull.log"
    curl_path = fake_bin / "curl"
    curl_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"TAGS_PATH='{tags_path}'",
                f"CURL_LOG='{curl_log}'",
                f"PULL_LOG='{pull_log}'",
                "printf '%s\\n' \"$*\" >> \"$CURL_LOG\"",
                "case \"$*\" in",
                "  *'/api/tags'*)",
                "    cat \"$TAGS_PATH\"",
                "    exit 0",
                "    ;;",
                "  *'/api/pull'*)",
                "    payload=\"$*\"",
                "    printf '%s\\n' \"$payload\" >> \"$PULL_LOG\"",
                "    model=$(printf '%s' \"$payload\" | sed -n 's/.*\"name\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p')",
                "    printf '{\"models\":[{\"name\":\"%s:latest\"}]}' \"$model\" > \"$TAGS_PATH\"",
                "    printf '{\"status\":\"success\"}'",
                "    exit 0",
                "    ;;",
                "esac",
                "exit 1",
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
                f"PATH='{fake_bin}:/usr/bin:/bin'\n"
                f"PYTHON_BIN='{sys.executable}'\n"
                "EMBEDDINGS_PROVIDER='ollama'\n"
                "EMBEDDINGS_MODEL='all-minilm'\n"
                "OLLAMA_BASE_URL='http://host.docker.internal:11434'\n"
                "log_info() { printf 'INFO:%s\\n' \"$1\"; }\n"
                "log_error() { printf 'ERR:%s\\n' \"$1\" >&2; }\n"
                "log_success() { printf 'OK:%s\\n' \"$1\"; }\n"
                f"{defs}"
                "ensure_ollama_embedding_model_for_rag\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "OK:Ollama embedding model ready: all-minilm" in completed.stdout
    assert "all-minilm" in pull_log.read_text(encoding="utf-8")
    curl_calls = curl_log.read_text(encoding="utf-8")
    assert "http://localhost:11434/api/tags" in curl_calls
    assert "http://localhost:11434/api/pull" in curl_calls


def test_start_rag_api_checks_embedding_model_before_booting_rag() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "if ! ensure_ollama_embedding_model_for_rag; then" in script_text


def test_ensure_librechat_env_persists_retrieval_embeddings_contract(tmp_path: Path) -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ensure_librechat_env")
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PYTHON_BIN='{sys.executable}'\n"
                f"LIBRECHAT_RUNTIME_ENV_FILE='{env_file}'\n"
                "VIVENTIUM_LOCAL_MONGO_PORT='27117'\n"
                "VIVENTIUM_LOCAL_MONGO_DB='LibreChatViventium'\n"
                "VIVENTIUM_RAG_API_PORT='8110'\n"
                "VIVENTIUM_LOCAL_MEILI_PORT='7700'\n"
                "LC_API_PORT='3180'\n"
                "LC_FRONTEND_URL='http://localhost:3190'\n"
                "LC_API_URL='http://localhost:3180/api'\n"
                "CODE_INTERPRETER_PORT='3210'\n"
                "SEARXNG_PORT='8080'\n"
                "FIRECRAWL_PORT='3002'\n"
                "SKYVERN_BASE_URL='http://localhost:8001'\n"
                "SKYVERN_APP_URL='http://localhost:8002'\n"
                "DEFAULT_VIVENTIUM_OPENAI_MODELS='gpt-5.4'\n"
                "DEFAULT_VIVENTIUM_ASSISTANTS_MODELS='gpt-5.4'\n"
                "VIVENTIUM_PRIVATE_CURATED_DIR=''\n"
                "VIVENTIUM_PRIVATE_MIRROR_DIR=''\n"
                "LIBRECHAT_CANONICAL_ENV_FILE=''\n"
                "START_RAG_API='true'\n"
                "SKIP_LIBRECHAT='false'\n"
                "VIVENTIUM_GOOGLE_PROVIDER_ENABLED='false'\n"
                "EMBEDDINGS_PROVIDER='ollama'\n"
                "EMBEDDINGS_MODEL='qwen3-embedding:0.6b'\n"
                "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER='ollama'\n"
                "VIVENTIUM_RAG_EMBEDDINGS_MODEL='qwen3-embedding:0.6b'\n"
                "VIVENTIUM_RAG_EMBEDDINGS_PROFILE='medium'\n"
                "OLLAMA_BASE_URL='http://host.docker.internal:11434'\n"
                "resolve_local_meili_master_key() { printf 'meili-master\\n'; }\n"
                "merge_allowed_hosts_csv() { printf '\\n'; }\n"
                "port_in_use() { return 1; }\n"
                "is_librechat_default_secret() { return 1; }\n"
                "first_existing_path() { return 1; }\n"
                "log_warn() { :; }\n"
                "log_info() { :; }\n"
                "generate_hex_secret() {\n"
                "  local bytes=\"${1:-16}\"\n"
                "  \"$PYTHON_BIN\" - \"$bytes\" <<'PY'\n"
                "import sys\n"
                "size = int(sys.argv[1])\n"
                "print('a' * (size * 2))\n"
                "PY\n"
                "}\n"
                "read_env_kv() {\n"
                "  local file=\"$1\"\n"
                "  local key=\"$2\"\n"
                "  \"$PYTHON_BIN\" - \"$file\" \"$key\" <<'PY'\n"
                "from pathlib import Path\n"
                "import sys\n"
                "path = Path(sys.argv[1])\n"
                "key = sys.argv[2]\n"
                "if not path.exists():\n"
                "    raise SystemExit(1)\n"
                "for line in path.read_text().splitlines():\n"
                "    if line.startswith(f'{key}='):\n"
                "        print(line.split('=', 1)[1])\n"
                "        raise SystemExit(0)\n"
                "raise SystemExit(1)\n"
                "PY\n"
                "}\n"
                "upsert_env_kv() {\n"
                "  local file=\"$1\"\n"
                "  local key=\"$2\"\n"
                "  local value=\"${3-}\"\n"
                "  \"$PYTHON_BIN\" - \"$file\" \"$key\" \"$value\" <<'PY'\n"
                "from pathlib import Path\n"
                "import sys\n"
                "path = Path(sys.argv[1])\n"
                "key = sys.argv[2]\n"
                "value = sys.argv[3]\n"
                "lines = path.read_text().splitlines() if path.exists() else []\n"
                "updated = False\n"
                "for index, line in enumerate(lines):\n"
                "    if line.startswith(f'{key}='):\n"
                "        lines[index] = f'{key}={value}'\n"
                "        updated = True\n"
                "        break\n"
                "if not updated:\n"
                "    lines.append(f'{key}={value}')\n"
                "path.write_text('\\n'.join(lines) + ('\\n' if lines else ''), encoding='utf-8')\n"
                "PY\n"
                "}\n"
                "remove_env_kv() {\n"
                "  local file=\"$1\"\n"
                "  local key=\"$2\"\n"
                "  \"$PYTHON_BIN\" - \"$file\" \"$key\" <<'PY'\n"
                "from pathlib import Path\n"
                "import sys\n"
                "path = Path(sys.argv[1])\n"
                "key = sys.argv[2]\n"
                "if not path.exists():\n"
                "    raise SystemExit(0)\n"
                "lines = [line for line in path.read_text().splitlines() if not line.startswith(f'{key}=')]\n"
                "path.write_text('\\n'.join(lines) + ('\\n' if lines else ''), encoding='utf-8')\n"
                "PY\n"
                "}\n"
                f"{function_def}"
                "ensure_librechat_env\n"
                f"cat '{env_file}'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    contents = completed.stdout
    assert "EMBEDDINGS_PROVIDER=ollama" in contents
    assert "EMBEDDINGS_MODEL=qwen3-embedding:0.6b" in contents
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER=ollama" in contents
    assert "VIVENTIUM_RAG_EMBEDDINGS_MODEL=qwen3-embedding:0.6b" in contents
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROFILE=medium" in contents
    assert "OLLAMA_BASE_URL=http://host.docker.internal:11434" in contents
