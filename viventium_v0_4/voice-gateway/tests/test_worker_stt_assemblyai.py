# === VIVENTIUM START ===
# Feature: Selectable AssemblyAI streaming STT model (Universal-3 Pro / u3-rt-pro) in the modern
#   playground "Listening" picker.
# Added: 2026-05-29
# Why: Regression coverage for the bug where the AssemblyAI engine variant was cosmetic — the model
#   was never passed to the plugin, the catalog advertised an invalid "universal-streaming" id, and
#   the selected variant was dropped in _apply_requested_voice_route. These tests pin: the proven
#   u3-rt-pro default, the real plugin-valid variant set surfaced in the capability catalog, that a
#   picked variant is applied and normalized, and that build_stt_selection actually hands the model
#   to livekit-plugins-assemblyai.
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (  # noqa: E402
    ASSEMBLYAI_DEFAULT_STT_MODEL,
    ASSEMBLYAI_STT_MODELS,
    HAS_ASSEMBLYAI,
    _apply_requested_voice_route,
    _assemblyai_stt_model_variants,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _normalize_assemblyai_stt_model,
    build_stt_selection,
    load_env,
)

_VALID_MODEL_IDS = {model_id for model_id, _label in ASSEMBLYAI_STT_MODELS}


def _assemblyai_stt_capability(env):
    for capability in _build_voice_capability_catalog(env):
        if capability.get("modality") == "stt" and capability.get("id") == "assemblyai":
            return capability
    raise AssertionError("AssemblyAI STT capability missing from catalog")


def _assemblyai_env(**overrides):
    # AssemblyAI availability + selection are read from os.environ at call time (load_env,
    # capability catalog, and build_stt_selection all use os.getenv), so the patch must wrap the
    # whole exercise — not just load_env() — or the key disappears and the worker falls back.
    base = {
        "VIVENTIUM_VOICE_STT_PROVIDER": "assemblyai",
        "ASSEMBLYAI_API_KEY": "test-assemblyai-key",
    }
    base.update(overrides)
    return base


class TestAssemblyAISttModelNormalization(unittest.TestCase):
    """Pure-function behavior — no runtime/env needed."""

    def test_default_constant(self):
        self.assertEqual(ASSEMBLYAI_DEFAULT_STT_MODEL, "u3-rt-pro")

    def test_normalizer_handles_alias_and_junk(self):
        self.assertEqual(_normalize_assemblyai_stt_model("u3-pro"), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model(""), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model("  garbage  "), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model("u3-rt-pro"), "u3-rt-pro")
        self.assertEqual(
            _normalize_assemblyai_stt_model("universal-streaming-english"),
            "universal-streaming-english",
        )

    def test_variants_helper_puts_selected_first(self):
        variants = _assemblyai_stt_model_variants("universal-streaming-multilingual")
        ids = [variant_id for variant_id, _label in variants]
        self.assertEqual(ids[0], "universal-streaming-multilingual")
        self.assertEqual(set(ids), _VALID_MODEL_IDS)

    def test_variants_helper_defaults_unknown_first_entry(self):
        ids = [variant_id for variant_id, _label in _assemblyai_stt_model_variants("bogus")]
        self.assertEqual(ids[0], "u3-rt-pro")


class TestAssemblyAISttModelSelection(unittest.TestCase):
    def test_default_model_is_u3_rt_pro(self):
        with patch.dict(os.environ, _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL=""), clear=False):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "u3-rt-pro")

    def test_env_var_selects_valid_model(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="universal-streaming-multilingual"),
            clear=False,
        ):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "universal-streaming-multilingual")

    def test_unknown_env_model_normalizes_to_default(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="totally-made-up"),
            clear=False,
        ):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "u3-rt-pro")

    def test_catalog_lists_u3_rt_pro_and_drops_legacy_id(self):
        with patch.dict(os.environ, _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL=""), clear=False):
            capability = _assemblyai_stt_capability(load_env())
        variant_ids = [variant["id"] for variant in capability["variants"]]
        labels = {variant["id"]: variant["label"] for variant in capability["variants"]}
        self.assertEqual(variant_ids[0], "u3-rt-pro")
        self.assertIn("universal-streaming-english", variant_ids)
        self.assertIn("universal-streaming-multilingual", variant_ids)
        # The old cosmetic/invalid id must not resurface in the picker.
        self.assertNotIn("universal-streaming", variant_ids)
        self.assertEqual(labels["u3-rt-pro"], "Universal-3 Pro streaming (u3-rt-pro)")

    def test_build_kwargs_includes_selected_model(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            kwargs = _build_assemblyai_stt_kwargs(load_env())
        self.assertEqual(kwargs["model"], "u3-rt-pro")

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_apply_requested_route_applies_selected_variant(self):
        requested = {
            "stt": {"provider": "assemblyai", "variant": "universal-streaming-multilingual"}
        }
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            applied = _apply_requested_voice_route(env, requested, capabilities)
        self.assertEqual(applied.stt_provider, "assemblyai")
        self.assertEqual(applied.assemblyai_stt_model, "universal-streaming-multilingual")

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_apply_requested_route_normalizes_unknown_variant(self):
        requested = {"stt": {"provider": "assemblyai", "variant": "nonexistent-engine"}}
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            applied = _apply_requested_voice_route(env, requested, capabilities)
        # Never hand the provider an invalid model string; fall back to a valid catalog model.
        self.assertIn(applied.assemblyai_stt_model, _VALID_MODEL_IDS)

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_build_stt_selection_passes_model_to_plugin(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            stt_impl, provider = build_stt_selection(load_env(), vad=None)
        self.assertEqual(provider, "assemblyai")
        # The plugin exposes the resolved model via the .model property.
        self.assertEqual(getattr(stt_impl, "model", None), "u3-rt-pro")


if __name__ == "__main__":
    unittest.main()
# === VIVENTIUM END ===
