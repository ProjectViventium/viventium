#!/usr/bin/env python3
"""Shared local power-budget checks for Viventium maintenance jobs."""

from __future__ import annotations

import subprocess
import sys


DISABLED_VALUES = {"0", "false", "no", "off"}
ENABLED_VALUES = {"1", "true", "yes", "on"}


def bool_env_disabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in DISABLED_VALUES


def bool_env_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in ENABLED_VALUES


def running_on_battery_power() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        completed = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except Exception:
        return False
    return "Battery Power" in (getattr(completed, "stdout", "") or "")


def thermal_state_constrained() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        completed = subprocess.run(
            ["pmset", "-g", "therm"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except Exception:
        return False
    output = getattr(completed, "stdout", "") or ""
    if "No thermal warning level has been recorded" in output and "No performance warning level has been recorded" in output:
        return False
    return "thermal warning" in output.lower() or "performance warning" in output.lower()


def skip_reason(
    *,
    env: dict[str, str],
    gate_env_name: str,
    ignore_power_gate: bool = False,
    override_env_name: str | None = None,
    running_on_battery: bool | None = None,
    thermal_constrained: bool | None = None,
) -> str | None:
    if bool_env_disabled(env.get(gate_env_name)):
        return None
    override_allowed = bool_env_enabled(env.get(override_env_name)) if override_env_name else True
    if ignore_power_gate and override_allowed:
        return None
    battery = running_on_battery if running_on_battery is not None else running_on_battery_power()
    thermal = thermal_constrained if thermal_constrained is not None else thermal_state_constrained()
    if battery:
        return "on_battery_power"
    if thermal:
        return "thermal_or_performance_warning"
    return None
