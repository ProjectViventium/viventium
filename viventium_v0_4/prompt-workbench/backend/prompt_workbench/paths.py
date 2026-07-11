from __future__ import annotations

import os
import sys
from pathlib import Path


WORKBENCH_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
LIBRECHAT_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat"
SOURCE_OF_TRUTH_ROOT = LIBRECHAT_ROOT / "viventium" / "source_of_truth"
PROMPTS_ROOT = SOURCE_OF_TRUTH_ROOT / "prompts"
SCHEDULING_CORTEX_ROOT = LIBRECHAT_ROOT / "viventium" / "MCPs" / "scheduling-cortex"
AGENTS_SOURCE_PATH = SOURCE_OF_TRUTH_ROOT / "local.viventium-agents.yaml"
LIBRECHAT_SOURCE_PATH = SOURCE_OF_TRUTH_ROOT / "local.librechat.yaml"
AGENT_SYNC_SCRIPT = LIBRECHAT_ROOT / "scripts" / "viventium-sync-agents.js"
EXACT_MODEL_EVAL_SCRIPT = REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "run-exact-model-evals.cjs"
ACTIVATION_MODEL_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-activation-model-evals.cjs"
)
PROMPT_BANK_PATH = REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "prompt-bank.json"
PROMPT_WORKBENCH_QA_COVERAGE_PATH = REPO_ROOT / "qa" / "prompt-workbench" / "prompt-coverage.yaml"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCHEDULING_CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_CORTEX_ROOT))


def private_user_data_root() -> Path:
    explicit = os.environ.get("VIVENTIUM_PRIVATE_USER_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / "Library" / "Application Support" / "Viventium" / "private-user-data"


def workbench_private_root() -> Path:
    root = private_user_data_root() / "prompt-workbench"
    root.mkdir(parents=True, exist_ok=True)
    return root


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path
