#!/usr/bin/env python3
"""Compatibility entrypoint for the Viventium workflow adapter package."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_suffix("") / "cli.py"), run_name="__main__")
