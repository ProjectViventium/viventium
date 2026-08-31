from __future__ import annotations

import os
import subprocess
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = ROOT / "AGENTS.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
LIBRECHAT_AGENTS_MD = ROOT / "viventium_v0_4" / "LibreChat" / "AGENTS.md"
KEY_PRINCIPLES_MD = ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md"
SYNC_SCRIPT = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-sync-agents.js"


def test_agent_sync_docs_require_live_vs_source_review_before_push() -> None:
    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    librechat_agents_text = LIBRECHAT_AGENTS_MD.read_text(encoding="utf-8")
    principles_text = KEY_PRINCIPLES_MD.read_text(encoding="utf-8")

    assert "viventium_v0_4/LibreChat/AGENTS.md" in agents_text
    assert "do not add regex or keyword matching in runtime code" in agents_text.lower()

    assert claude_text.splitlines()[0] == "@AGENTS.md"
    assert "interface.webSearch" not in claude_text
    assert "--compare-reviewed" not in claude_text

    assert "scripts/viventium-sync-agents.js compare --env=<env>" in librechat_agents_text
    assert "A: current live user-level agent config" in librechat_agents_text
    assert "Treat live user edits to instructions, conversation starters, tools, model/provider" in librechat_agents_text
    assert "interface.webSearch" in librechat_agents_text
    assert "--compare-reviewed" in librechat_agents_text

    assert "always run a live-vs-source comparison" in principles_text
    assert "A = current live user-level agent bundle" in principles_text
    assert "Treat live user edits as protected state" in principles_text
    assert "Do not blindly overwrite live instructions or conversation starters either" in principles_text
    assert "interface.webSearch" in principles_text
    assert "--compare-reviewed" in principles_text
    assert "CRITICAL RULE: No Hardcoded NLU in Runtime Code" in principles_text


def test_sync_script_help_exposes_compare_review_workflow_without_built_api(
    tmp_path: Path,
) -> None:
    require_blocker = tmp_path / "forbid-built-api.cjs"
    require_blocker.write_text(
        """const Module = require('module');
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === '@librechat/api') {
    throw new Error('QA forbids loading the built API for --help');
  }
  return originalLoad.call(this, request, parent, isMain);
};
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(SYNC_SCRIPT), "--help"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={
            **os.environ,
            "NODE_OPTIONS": f"--require={require_blocker}",
        },
    )

    help_text = result.stdout
    assert "node scripts/viventium-sync-agents.js compare" in help_text
    assert "--compare-reviewed" in help_text
    assert "--source=..." in help_text
    assert "--live=..." in help_text
    assert "review A/B/C drift" in help_text


def test_agent_sync_compare_reviews_user_visible_sequential_output_policy() -> None:
    script = """
const { compareBundlesByAgent } = require('./viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js');
const left = { mainAgent: { id: 'main', hide_sequential_outputs: false } };
const right = { mainAgent: { id: 'main', hide_sequential_outputs: true } };
process.stdout.write(
  JSON.stringify(compareBundlesByAgent({ leftBundle: left, rightBundle: right })),
  () => process.exit(0),
);
"""
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    payload = json.loads(result.stdout)
    assert payload["diffCount"] == 1
    assert payload["diffs"][0]["changedFields"] == ["hide_sequential_outputs"]
