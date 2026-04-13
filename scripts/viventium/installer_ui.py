#!/usr/bin/env python3
from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    import questionary
    from questionary import Choice, Separator
except Exception:  # pragma: no cover - graceful fallback when bootstrap deps are absent
    questionary = None
    Choice = None
    Separator = None

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except Exception:  # pragma: no cover - graceful fallback when bootstrap deps are absent
    Console = None
    Panel = None
    Table = None
    Text = None


@dataclass(frozen=True)
class SelectOption:
    value: str
    label: str
    note: str = ""


@dataclass(frozen=True)
class CheckboxOption:
    group: str
    value: str
    label: str
    note: str = ""
    checked: bool = False


class InstallerUI:
    def __init__(self) -> None:
        self.interactive = bool(sys.stdin.isatty() and sys.stdout.isatty())
        self.rich_enabled = Console is not None
        self.questionary_enabled = questionary is not None and self.interactive
        self._questionary_fallback_notified = False
        self._password_fallback_notified = False
        self.console = Console() if self.rich_enabled else None

    def print_blank(self) -> None:
        print()

    def print_banner(self, subtitle: str = "Your second brain for real work") -> None:
        if self.console and Panel and Text:
            banner = Text()
            banner.append("VIVENTIUM", style="bold cyan")
            banner.append("\n")
            banner.append(subtitle, style="dim")
            self.console.print()
            self.console.print(Panel(banner, border_style="cyan", expand=False, padding=(1, 3)))
            self.console.print()
            return
        print()
        print("VIVENTIUM")
        print(subtitle)
        print()

    def print_section(self, title: str, message: str, style: str = "cyan") -> None:
        if self.console and Panel:
            self.console.print(Panel(message, title=title, border_style=style, expand=False))
            return
        print(f"{title}:")
        print(message)

    def print_note(self, message: str) -> None:
        if self.console:
            self.console.print(message, style="dim")
            return
        print(message)

    def print_success(self, message: str) -> None:
        if self.console:
            self.console.print(message, style="green")
            return
        print(message)

    def print_warning(self, message: str) -> None:
        if self.console:
            self.console.print(message, style="yellow")
            return
        print(message)

    def print_error(self, message: str) -> None:
        if self.console:
            self.console.print(message, style="red")
            return
        print(message, file=sys.stderr)

    def print_table(
        self,
        title: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[str]],
        style: str = "cyan",
    ) -> None:
        if self.console and Table:
            table = Table(title=title, header_style=f"bold {style}", expand=False)
            for column in columns:
                table.add_column(column)
            for row in rows:
                table.add_row(*[str(cell) for cell in row])
            self.console.print(table)
            return
        print(title)
        print(" | ".join(columns))
        for row in rows:
            print(" | ".join(str(cell) for cell in row))

    def select(self, prompt: str, options: Sequence[SelectOption], default: str | None = None) -> str:
        if not options:
            raise ValueError("select() requires at least one option")

        if self.questionary_enabled and Choice is not None:
            choices = [
                Choice(
                    title=f"{option.label}  ({option.note})" if option.note else option.label,
                    value=option.value,
                )
                for option in options
            ]
            answer, used_questionary = self._ask_questionary(
                lambda: questionary.select(
                    prompt,
                    choices=choices,
                    instruction="Use arrow keys and press Enter",
                    use_shortcuts=False,
                ),
            )
            if used_questionary:
                return str(answer)

        return self._plain_select(prompt, options, default)

    def confirm(self, prompt: str, default: bool = False) -> bool:
        if self.questionary_enabled:
            answer, used_questionary = self._ask_questionary(
                lambda: questionary.confirm(prompt, default=default, auto_enter=False),
            )
            if used_questionary:
                return bool(answer)

        suffix = "[Y/n]" if default else "[y/N]"
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes", "1", "true"}

    def text(self, prompt: str, default: str = "", allow_empty: bool = True) -> str:
        if self.questionary_enabled:
            answer, used_questionary = self._ask_questionary(
                lambda: questionary.text(
                    prompt,
                    default=default,
                    validate=(
                        lambda value: True if allow_empty or str(value).strip() else "Value required."
                    ),
                ),
            )
            if used_questionary:
                return str(answer).strip()

        while True:
            suffix = f" [{default}]" if default else ""
            raw = input(f"{prompt}{suffix}: ").strip()
            if raw:
                return raw
            if default:
                return default
            if allow_empty:
                return ""
            print("Value required.")

    def password(self, prompt: str, allow_empty: bool = False) -> str:
        if self.questionary_enabled:
            answer, used_questionary = self._ask_questionary(
                lambda: questionary.password(
                    prompt,
                    validate=(
                        lambda value: True if allow_empty or str(value).strip() else "Value required."
                    ),
                ),
            )
            if used_questionary:
                return str(answer).strip()

        while True:
            try:
                value = getpass.getpass(f"{prompt}: ").strip()
            except (EOFError, OSError):
                if not self._password_fallback_notified:
                    self.print_warning(
                        "Secure password input unavailable; falling back to visible input."
                    )
                    self._password_fallback_notified = True
                value = input(f"{prompt}: ").strip()
            if value or allow_empty:
                return value
            print("Value required.")

    def checkbox(self, prompt: str, options: Sequence[CheckboxOption]) -> list[str]:
        if self.questionary_enabled and Choice is not None and Separator is not None:
            choices: list[object] = []
            current_group = None
            for option in options:
                if option.group != current_group:
                    current_group = option.group
                    choices.append(Separator(f"--- {current_group} ---"))
                title = option.label
                if option.note:
                    title = f"{title}  ({option.note})"
                choices.append(Choice(title=title, value=option.value, checked=option.checked))
            answer, used_questionary = self._ask_questionary(
                lambda: questionary.checkbox(
                    prompt,
                    choices=choices,
                    instruction="Space toggles, Enter confirms",
                ),
            )
            if used_questionary:
                return [str(item) for item in (answer or [])]

        selected: list[str] = []
        current_group = None
        print(prompt)
        for option in options:
            if option.group != current_group:
                current_group = option.group
                print()
                print(f"{current_group}:")
            keep = self.confirm(
                f"Enable {option.label}" + (f" ({option.note})" if option.note else ""),
                default=option.checked,
            )
            if keep:
                selected.append(option.value)
        return selected

    def _plain_select(
        self,
        prompt: str,
        options: Sequence[SelectOption],
        default: str | None = None,
    ) -> str:
        indexed = list(options)
        default_index = 0
        if default:
            for index, option in enumerate(indexed, start=1):
                if option.value == default:
                    default_index = index - 1
                    break
        print(prompt)
        for index, option in enumerate(indexed, start=1):
            note = f" - {option.note}" if option.note else ""
            print(f"  {index}. {option.label}{note}")
        while True:
            raw = input(f"Choose an option [default: {default_index + 1}]: ").strip()
            if not raw:
                return indexed[default_index].value
            if raw.isdigit():
                choice_index = int(raw) - 1
                if 0 <= choice_index < len(indexed):
                    return indexed[choice_index].value
            normalized = raw.lower()
            for option in indexed:
                if normalized == option.value.lower():
                    return option.value
            print("Invalid choice. Try again.")

    def _disable_questionary(
        self,
        reason: str = "Interactive terminal UI unavailable; falling back to plain prompts.",
    ) -> None:
        self.questionary_enabled = False
        if self._questionary_fallback_notified:
            return
        self._questionary_fallback_notified = True
        self.print_note(reason)

    def _ask_questionary(self, build_prompt):
        try:
            answer = build_prompt().ask()
        except KeyboardInterrupt:
            raise
        except Exception:
            self._disable_questionary()
            return None, False
        if answer is None:
            raise KeyboardInterrupt
        return answer, True
