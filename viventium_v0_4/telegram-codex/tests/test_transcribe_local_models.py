from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

import pytest


_fake_pywhispercpp = types.ModuleType("pywhispercpp")
_fake_pywhispercpp_model = types.ModuleType("pywhispercpp.model")


class _FakeModel:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


_fake_pywhispercpp_model.Model = _FakeModel
_fake_pywhispercpp.model = _fake_pywhispercpp_model
sys.modules.setdefault("pywhispercpp", _fake_pywhispercpp)
sys.modules.setdefault("pywhispercpp.model", _fake_pywhispercpp_model)

from app import transcribe_local


def test_local_whisper_corrupt_cache_redownloads_exact_selected_model(tmp_path, monkeypatch):
    good_content = b"correct selected model"
    expected_sha1 = hashlib.sha1(good_content).hexdigest()
    model_path = tmp_path / "ggml-large-v3-turbo.bin"
    model_path.write_bytes(b"corrupt cached model")

    def fake_urlretrieve(_url: str, destination: Path) -> None:
        Path(destination).write_bytes(good_content)

    monkeypatch.setitem(transcribe_local._MODEL_SHA1, "ggml-large-v3-turbo.bin", expected_sha1)
    monkeypatch.setattr(transcribe_local.urllib.request, "urlretrieve", fake_urlretrieve)

    resolved = transcribe_local._ensure_model_file("large-v3-turbo", tmp_path)

    assert resolved == model_path.resolve()
    assert model_path.read_bytes() == good_content


def test_local_whisper_download_checksum_mismatch_keeps_existing_cache(tmp_path, monkeypatch):
    good_content = b"correct selected model"
    expected_sha1 = hashlib.sha1(good_content).hexdigest()
    model_path = tmp_path / "ggml-large-v3-turbo.bin"
    existing_content = b"existing corrupt model"
    model_path.write_bytes(existing_content)

    def fake_urlretrieve(_url: str, destination: Path) -> None:
        Path(destination).write_bytes(b"wrong downloaded model")

    monkeypatch.setitem(transcribe_local._MODEL_SHA1, "ggml-large-v3-turbo.bin", expected_sha1)
    monkeypatch.setattr(transcribe_local.urllib.request, "urlretrieve", fake_urlretrieve)

    with pytest.raises(RuntimeError, match="failed checksum"):
        transcribe_local._ensure_model_file("large-v3-turbo", tmp_path)

    assert model_path.read_bytes() == existing_content
    assert list(tmp_path.glob(".ggml-large-v3-turbo.bin.*.download")) == []


def test_legacy_large_alias_is_not_supported():
    with pytest.raises(ValueError, match="Unsupported local whisper.cpp model"):
        transcribe_local._ensure_model_file("large", Path("/tmp/unused"))


def test_every_supported_model_has_checksum():
    missing = [
        filename
        for filename in transcribe_local._MODEL_MAP.values()
        if filename not in transcribe_local._MODEL_SHA1
    ]

    assert missing == []


def test_resolve_model_path_honors_shared_cache_override(tmp_path, monkeypatch):
    settings = types.SimpleNamespace(model_path="", model_name="large-v3-turbo")
    monkeypatch.setenv("VIVENTIUM_WHISPER_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(transcribe_local, "_ensure_model_file", lambda model_name, cache_dir: cache_dir / model_name)

    transcriber = transcribe_local.LocalWhisperTranscriber(settings)

    assert transcriber._resolve_model_path() == tmp_path / "large-v3-turbo"
