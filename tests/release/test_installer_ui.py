from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_UI_SPEC = importlib.util.spec_from_file_location(
    "viventium_installer_ui",
    REPO_ROOT / "scripts/viventium/installer_ui.py",
)
assert INSTALLER_UI_SPEC and INSTALLER_UI_SPEC.loader


def load_installer_ui_module():
    module = importlib.util.module_from_spec(INSTALLER_UI_SPEC)
    sys.modules[INSTALLER_UI_SPEC.name] = module
    INSTALLER_UI_SPEC.loader.exec_module(module)
    return module


class _FailingPrompt:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def ask(self):
        raise self.exc


def test_select_falls_back_to_plain_prompt_when_questionary_select_raises(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()
    installer_ui.questionary = types.SimpleNamespace(
        select=lambda *args, **kwargs: _FailingPrompt(OSError(22, "Invalid argument")),
    )
    installer_ui.Choice = lambda **kwargs: kwargs

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = True

    monkeypatch.setattr(ui, "_plain_select", lambda *_args, **_kwargs: "advanced")

    result = ui.select(
        "How would you like to set up Viventium?",
        [
            installer_ui.SelectOption("easy", "Easy Install"),
            installer_ui.SelectOption("advanced", "Advanced Setup"),
        ],
        default="easy",
    )

    assert result == "advanced"
    assert ui.questionary_enabled is False
    assert "falling back to plain prompts" in capsys.readouterr().out.lower()


def test_confirm_falls_back_to_plain_prompt_when_questionary_confirm_raises(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()
    installer_ui.questionary = types.SimpleNamespace(
        confirm=lambda *args, **kwargs: _FailingPrompt(OSError(22, "Invalid argument")),
    )

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = True

    monkeypatch.setattr("builtins.input", lambda _prompt="": "")

    result = ui.confirm("Enable feature?", default=True)

    assert result is True
    assert ui.questionary_enabled is False
    assert "falling back to plain prompts" in capsys.readouterr().out.lower()


def test_text_falls_back_to_plain_prompt_when_questionary_text_raises(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()
    installer_ui.questionary = types.SimpleNamespace(
        text=lambda *args, **kwargs: _FailingPrompt(OSError(22, "Invalid argument")),
    )

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = True

    monkeypatch.setattr("builtins.input", lambda _prompt="": "typed value")

    result = ui.text("Enter value", allow_empty=False)

    assert result == "typed value"
    assert ui.questionary_enabled is False
    assert "falling back to plain prompts" in capsys.readouterr().out.lower()


def test_password_falls_back_to_plain_prompt_when_questionary_password_raises(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()
    installer_ui.questionary = types.SimpleNamespace(
        password=lambda *args, **kwargs: _FailingPrompt(OSError(22, "Invalid argument")),
    )

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = True

    monkeypatch.setattr(installer_ui.getpass, "getpass", lambda _prompt="": "secret-value")

    result = ui.password("Enter secret")

    assert result == "secret-value"
    assert ui.questionary_enabled is False
    assert "falling back to plain prompts" in capsys.readouterr().out.lower()


def test_password_falls_back_to_visible_input_when_getpass_cannot_attach(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = False

    monkeypatch.setattr(installer_ui.getpass, "getpass", lambda _prompt="": (_ for _ in ()).throw(EOFError()))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "visible-secret")

    result = ui.password("Enter secret")

    assert result == "visible-secret"
    assert "secure password input unavailable" in capsys.readouterr().out.lower()


def test_questionary_is_disabled_when_term_is_dumb(monkeypatch) -> None:
    installer_ui = load_installer_ui_module()

    monkeypatch.setenv("TERM", "dumb")
    ui = installer_ui.InstallerUI()

    assert ui.interactive is False
    assert ui.questionary_enabled is False


def test_checkbox_falls_back_to_plain_prompts_when_questionary_checkbox_raises(monkeypatch, capsys) -> None:
    installer_ui = load_installer_ui_module()
    installer_ui.questionary = types.SimpleNamespace(
        checkbox=lambda *args, **kwargs: _FailingPrompt(OSError(22, "Invalid argument")),
    )
    installer_ui.Choice = lambda **kwargs: kwargs
    installer_ui.Separator = lambda title: title

    ui = installer_ui.InstallerUI()
    ui.questionary_enabled = True

    answers = iter([True, False])
    monkeypatch.setattr(ui, "confirm", lambda *_args, **_kwargs: next(answers))

    result = ui.checkbox(
        "Choose features",
        [
            installer_ui.CheckboxOption("Core", "memory", "Memory"),
            installer_ui.CheckboxOption("Core", "recall", "Conversation Recall"),
        ],
    )

    assert result == ["memory"]
    assert ui.questionary_enabled is False
    assert "falling back to plain prompts" in capsys.readouterr().out.lower()
