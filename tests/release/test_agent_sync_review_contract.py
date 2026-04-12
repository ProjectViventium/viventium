from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = ROOT / "AGENTS.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
KEY_PRINCIPLES_MD = ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md"
SYNC_SCRIPT = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-sync-agents.js"


def test_agent_sync_docs_require_live_vs_source_review_before_push() -> None:
    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    principles_text = KEY_PRINCIPLES_MD.read_text(encoding="utf-8")

    assert "viventium-sync-agents.js compare --env=<env>" in agents_text
    assert "A: current live user-level agent config" in agents_text
    assert "Treat live user edits to instructions, conversation starters, tools, model/provider" in agents_text
    assert "interface.webSearch" in agents_text
    assert "--compare-reviewed" in agents_text
    assert "do not add regex or keyword matching in runtime code" in agents_text.lower()

    assert "viventium-sync-agents.js compare --env=<env>" in claude_text
    assert "A = live user-level bundle" in claude_text
    assert "Do not treat the tracked scaffold as automatically authoritative over live user edits" in claude_text
    assert "interface.webSearch" in claude_text
    assert "--compare-reviewed" in claude_text
    assert "do not add regex or keyword matching in runtime code" in claude_text.lower()

    assert "always run a live-vs-source comparison" in principles_text
    assert "A = current live user-level agent bundle" in principles_text
    assert "Treat live user edits as protected state" in principles_text
    assert "Do not blindly overwrite live instructions or conversation starters either" in principles_text
    assert "interface.webSearch" in principles_text
    assert "--compare-reviewed" in principles_text
    assert "CRITICAL RULE: No Hardcoded NLU in Runtime Code" in principles_text


def test_sync_script_help_exposes_compare_review_workflow() -> None:
    result = subprocess.run(
        ["node", str(SYNC_SCRIPT), "--help"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    help_text = result.stdout
    assert "node scripts/viventium-sync-agents.js compare" in help_text
    assert "--compare-reviewed" in help_text
    assert "--source=..." in help_text
    assert "--live=..." in help_text
    assert "review A/B/C drift" in help_text
