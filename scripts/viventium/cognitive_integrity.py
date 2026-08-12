#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report composed Viventium cognitive-system integrity without exposing private content."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve()
    backend = repo_root / "viventium_v0_4" / "prompt-workbench" / "backend"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from prompt_workbench.cognitive_integrity import cognitive_integrity_report

    report = cognitive_integrity_report(user_id="")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Cognitive integrity: {report['status']}")
        for key, value in report["checks"].items():
            print(f"- {key}: {value.get('status', 'unknown')}")
        if report["blockingChecks"]:
            print("Blocking checks: " + ", ".join(report["blockingChecks"]))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
