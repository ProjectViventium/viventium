from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from prompt_registry import build_prompt_bundle
except ModuleNotFoundError:  # pragma: no cover - used when imported as a package in tests.
    from scripts.viventium.prompt_registry import build_prompt_bundle


def _private_user_data_root() -> Path:
    import os

    explicit = os.environ.get("VIVENTIUM_PRIVATE_USER_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / "Library" / "Application Support" / "Viventium" / "private-user-data"


def _default_logs_root() -> Path:
    return _private_user_data_root() / "prompt-observability" / "frame-logs"


PUBLIC_DECISION_STATE_KEYS = frozenset(
    {
        "status",
        "decision",
        "reason_code",
        "confidence",
        "should_respond",
        "should_follow_up",
        "no_response",
        "activation_count",
        "activated_count",
        "visible_insight_count",
        "silent_count",
        "error_count",
    }
)


def _summarize_decision_state(decision: Any, *, include_private_details: bool) -> dict[str, Any]:
    if not isinstance(decision, dict):
        return {}
    if include_private_details:
        return decision
    public: dict[str, Any] = {}
    for key in sorted(PUBLIC_DECISION_STATE_KEYS):
        value = decision.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            public[key] = value
    return public


def _read_frame_log_summary(
    logs_root: Path,
    limit: int = 200,
    *,
    include_private_details: bool = False,
) -> list[dict[str, Any]]:
    if not logs_root.exists():
        return []
    files = sorted(logs_root.rglob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    frames: list[dict[str, Any]] = []
    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if len(frames) >= limit:
                return frames
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(frame, dict):
                frames.append(
                    {
                        "time": frame.get("time") or frame.get("timestamp") or "",
                        "surface": frame.get("surface") or "unknown",
                        "family": frame.get("prompt_family") or "unknown",
                        "model": frame.get("model") or "unknown",
                        "provider": frame.get("provider") or "unknown",
                        "layer_hashes": frame.get("layer_hashes") or {},
                        "layer_tokens": frame.get("layer_token_estimates") or {},
                        "decision": _summarize_decision_state(
                            frame.get("decision_state"),
                            include_private_details=include_private_details,
                        ),
                    }
                )
    return frames


def _prompt_rows(bundle: dict[str, Any], *, include_private_text: bool) -> str:
    rows = []
    for prompt_id, prompt in sorted((bundle.get("prompts") or {}).items()):
        metadata = prompt.get("metadata") or {}
        body = str(prompt.get("body") or "")
        text_cell = (
            f"<details><summary>view text</summary><pre>{html.escape(body)}</pre></details>"
            if include_private_text
            else "<span class=\"muted\">hidden in public-safe mode</span>"
        )
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(prompt_id)}</code></td>"
            f"<td>{html.escape(str(metadata.get('owner_layer') or ''))}</td>"
            f"<td>{html.escape(str(metadata.get('target') or ''))}</td>"
            f"<td>{html.escape(str(metadata.get('version') or ''))}</td>"
            f"<td><code>{html.escape(str(prompt.get('content_hash') or ''))}</code></td>"
            f"<td>{text_cell}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _frame_rows(frames: list[dict[str, Any]]) -> str:
    rows = []
    for frame in frames:
        layer_count = len(frame.get("layer_hashes") or {})
        token_total = sum(int(v or 0) for v in (frame.get("layer_tokens") or {}).values())
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(frame.get('surface') or ''))}</td>"
            f"<td>{html.escape(str(frame.get('family') or ''))}</td>"
            f"<td>{html.escape(str(frame.get('provider') or ''))}</td>"
            f"<td>{html.escape(str(frame.get('model') or ''))}</td>"
            f"<td>{layer_count}</td>"
            f"<td>{token_total}</td>"
            f"<td><code>{html.escape(json.dumps(frame.get('decision') or {}, sort_keys=True))}</code></td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_dashboard(
    *,
    output: Path,
    logs_root: Path,
    include_private_text: bool = False,
    allow_public_output: bool = False,
) -> None:
    bundle = build_prompt_bundle()
    frames = _read_frame_log_summary(
        logs_root,
        include_private_details=include_private_text,
    )
    resolved_output = output.expanduser().resolve()
    try:
        output_in_repo = resolved_output.is_relative_to(Path(__file__).resolve().parents[2])
    except AttributeError:
        output_in_repo = str(resolved_output).startswith(
            str(Path(__file__).resolve().parents[2].resolve())
        )
    if include_private_text and output_in_repo:
        raise ValueError(
            "Refusing to write private prompt-text dashboard into the public repo. "
            "Write private prompt dashboards outside the public repository."
        )
    if frames and not include_private_text and output_in_repo and not allow_public_output:
        raise ValueError(
            "Refusing to write private frame-log summaries into the public repo without "
            "--allow-public-output."
        )
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mode = "private full-text" if include_private_text else "public-safe"
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Viventium Prompt Observatory</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #1d2430; }}
    header {{ padding: 22px 28px; background: #111827; color: white; }}
    main {{ padding: 24px 28px 40px; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 18px; }}
    .metric {{ background: white; border: 1px solid #d7dce3; border-radius: 8px; padding: 14px; }}
    .metric strong {{ display: block; font-size: 24px; margin-top: 4px; }}
    section {{ background: white; border: 1px solid #d7dce3; border-radius: 8px; margin-top: 18px; overflow: hidden; }}
    h2 {{ font-size: 18px; margin: 0; padding: 14px 16px; border-bottom: 1px solid #d7dce3; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #edf0f4; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f8; position: sticky; top: 0; z-index: 1; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ white-space: pre-wrap; max-height: 420px; overflow: auto; background: #0f172a; color: #e5e7eb; padding: 12px; border-radius: 6px; }}
    .muted {{ color: #64748b; }}
    .toolbar {{ display: flex; gap: 12px; align-items: center; padding: 12px 16px; border-bottom: 1px solid #edf0f4; }}
    .wrap-off pre {{ white-space: pre; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #0b1020; color: #e5e7eb; }}
      section, .metric {{ background: #111827; border-color: #263244; }}
      th {{ background: #172033; }}
      th, td, h2, .toolbar {{ border-color: #263244; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Viventium Prompt Observatory</h1>
    <div>Generated {html.escape(generated_at)} · Mode: {html.escape(mode)}</div>
  </header>
  <main id="page">
    <div class="grid">
      <div class="metric">Managed prompts<strong>{bundle.get("prompt_count", 0)}</strong></div>
      <div class="metric">Recent prompt frames<strong>{len(frames)}</strong></div>
      <div class="metric">Bundle schema<strong>{bundle.get("schema_version", "")}</strong></div>
    </div>
    <section>
      <h2>Prompt Tree</h2>
      <div class="toolbar"><label><input type="checkbox" id="wrapToggle" checked /> Word wrap</label></div>
      <table>
        <thead><tr><th>Prompt ID</th><th>Owner</th><th>Target</th><th>Version</th><th>Hash</th><th>Text</th></tr></thead>
        <tbody>{_prompt_rows(bundle, include_private_text=include_private_text)}</tbody>
      </table>
    </section>
    <section>
      <h2>Recent Frame Logs</h2>
      <table>
        <thead><tr><th>Surface</th><th>Family</th><th>Provider</th><th>Model</th><th>Layers</th><th>Tokens</th><th>Decision</th></tr></thead>
        <tbody>{_frame_rows(frames)}</tbody>
      </table>
    </section>
  </main>
  <script>
    const page = document.getElementById('page');
    const toggle = document.getElementById('wrapToggle');
    toggle.addEventListener('change', () => page.classList.toggle('wrap-off', !toggle.checked));
  </script>
</body>
</html>
"""
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(html_text, encoding="utf-8")
    if include_private_text:
        resolved_output.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local Viventium prompt dashboard.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--logs-root", default=str(_default_logs_root()))
    parser.add_argument("--include-private-text", action="store_true")
    parser.add_argument(
        "--allow-public-output",
        action="store_true",
        help="Allow sanitized frame summaries in the public repo; private prompt text is still refused.",
    )
    args = parser.parse_args()

    render_dashboard(
        output=Path(args.output).expanduser(),
        logs_root=Path(args.logs_root).expanduser(),
        include_private_text=args.include_private_text,
        allow_public_output=args.allow_public_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
