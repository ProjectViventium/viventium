"""Exercise Native's terminal producer against Core's actual strict marker consumer."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "viventium_v0_4/xPerfect/runtime_phase1"
CORE = ROOT / "viventium_v0_4/LibreChat"


def test_native_terminal_part_identity_matches_core_consumer(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    node = shutil.which("node")
    if not node or not (NATIVE / "src").is_dir() or not (CORE / "node_modules/typescript").is_dir():
        pytest.skip("Native source and Core Node dependencies are required")
    monkeypatch.syspath_prepend(str(NATIVE / "src"))
    # Reuse the Native suite's synthetic store/authority fixture. Its real stream producer
    # runs without a service, inference, credentials or network connection.
    spec = importlib.util.spec_from_file_location(
        "native_speech_fixture", NATIVE / "tests/test_conversation_provider.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    cases = []
    for name, options, expected in [
        ("primary", {}, ["run-a:0"]),
        ("fallback", {"fallback": True}, ["run-fallback:0"]),
        ("prior-parts", {"text": "abcDEF217", "prior_text": "abcDEF",
                         "prior_parts": ((0, 3), (2, 6))}, ["run-a:0", "run-a:2", "run-a:3"]),
        ("already-sealed", {"prior_text": "217", "prior_parts": ((0, 3),)}, ["run-a:0"]),
        ("retracted", {"text": "changed", "prior_text": "217", "prior_parts": ((0, 3),)},
         ["run-a:0"]),
    ]:
        chunks, _ = fixture._canonical_terminal_speech_chunks(monkeypatch, **options)
        cases.append({"name": name, "chunks": chunks, "expected": expected})
    payload = tmp_path / "synthetic-native-stream.json"
    payload.write_text(json.dumps(cases))
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const [sourcePath, fixturePath] = process.argv.slice(1);
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText;
const source = {exports: {}};
// These imports serve unrelated delivery methods, not the local strict marker validator.
vm.runInNewContext(compiled, {module: source, exports: source.exports,
  require: name => name === 'node:crypto' ? require(name) : {},
}, {filename: sourcePath});
for (const item of JSON.parse(fs.readFileSync(fixturePath, 'utf8'))) {
  const observed = [];
  for (const chunk of item.chunks) {
    const marker = chunk.choices?.[0]?.delta?.provider_specific_fields?.viventium?.public_part_complete;
    const parsed = source.exports.inspectProviderPublicPartCompletion(chunk);
    if (!marker) { assert.equal(parsed, null); continue; }
    assert.equal(JSON.stringify(parsed), JSON.stringify(marker));
    observed.push(parsed.part_id);
    const invalid = structuredClone(chunk);
    invalid.choices[0].delta.provider_specific_fields.viventium.public_part_complete.part_id =
      `${marker.run_id}:terminal`;
    assert.equal(source.exports.inspectProviderPublicPartCompletion(invalid), null);
  }
  assert.deepEqual(observed, item.expected, item.name);
  assert.equal(new Set(observed).size, observed.length);
}
"""
    subprocess.run([node, "-e", script, str(CORE / "packages/api/src/channels/deliveryDisposition.ts"),
                    str(payload)], cwd=CORE, check=True, capture_output=True, text=True, timeout=30)
