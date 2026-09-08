"""Native inventory consumes the browser producer's shipped, pruned metadata."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]

def load():
    sys.path.insert(0, str(ROOT / "scripts/viventium"))
    spec = importlib.util.spec_from_file_location("native_browser_compliance_test", ROOT / "scripts/viventium/generate_native_compliance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize("role,provenance", [("license", "exact-upstream-revision"), ("license-declaration", "exact-package-revision")])
@pytest.mark.parametrize("failure", [None, "source-hash", "provenance", "lock", "source-identity", "privacy-hash", "missing-adapter"])
def test_native_curated_adapter_inventory(tmp_path, role, provenance, failure):
    module = load()
    root = tmp_path / "runtime/librechat"
    client = root / "client"
    closure = client / "dist-compliance"
    def write(path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    def record(path, body):
        write(closure / path, body)
        return {"path": path, "sha256": hashlib.sha256(body.encode()).hexdigest()}
    source = {"id": "synthetic-license", "repository": "https://github.com/example/synthetic",
        "revision": "a" * 40, "sourcePath": "LICENSE", "localFile": "LICENSE.txt",
        "sha256": hashlib.sha256(b"Synthetic notice").hexdigest(), "contentRole": role, "provenance": provenance}
    write(client / "third_party/browser-compliance/LICENSE.txt", "Synthetic notice")
    adapter = {"id": "synthetic", "name": "Synthetic adapter", "lockPath": "node_modules/synthetic-adapter",
        "upstreamPackage": "synthetic-adapter", "upstreamVersion": "1.0", "resolved": "https://registry.npmjs.org/synthetic-adapter/-/synthetic-adapter-1.0.tgz",
        "integrity": "sha512-synthetic", "license": "MIT", "modified": True,
        "sourceFile": "src/adapter.ts", "sourceSha256": "b" * 64,
        "noticeSha256": hashlib.sha256(b"Adapter notice").hexdigest(), "legalSourceIds": [source["id"]]}
    legal = record("vendored/synthetic/LICENSE.curated.txt", "Synthetic notice")
    legal["provenance"] = {"sourceId": source["id"], "sourceSha256": source["sha256"], **{key: source[key] for key in ("repository", "revision", "sourcePath", "contentRole", "provenance")}}
    component = {key: adapter[key] for key in ("id", "name", "upstreamPackage", "upstreamVersion", "license", "modified")}
    component.update({"upstreamResolved": adapter["resolved"], "upstreamIntegrity": adapter["integrity"],
        "sourceIdentity": {"path": adapter["sourceFile"], "sha256": adapter["sourceSha256"]},
        "packageMetadata": record("vendored/synthetic/package.json", json.dumps({"name": "synthetic-adapter", "version": "1.0"})),
        "notice": record("vendored/synthetic/NOTICE.md", "Adapter notice"), "legalFiles": [legal],
        "runtimePrivacyNotice": record("vendored/synthetic/RUNTIME_PRIVACY_NOTICE.md", "No telemetry")})
    locked = {"version": adapter["upstreamVersion"], "resolved": adapter["resolved"], "integrity": adapter["integrity"]}
    if failure == "source-hash": write(client / "third_party/browser-compliance/LICENSE.txt", "changed")
    elif failure == "provenance": legal["provenance"]["revision"] = "c" * 40
    elif failure == "lock": locked["resolved"] += "-other"
    elif failure == "source-identity": component["sourceIdentity"]["sha256"] = "c" * 64
    elif failure == "privacy-hash": write(closure / component["runtimePrivacyNotice"]["path"], "changed")
    overrides = {"schemaVersion": 1, "sources": [source], "packageOverrides": [], "supplementalNotices": [], "vendoredAdapters": [adapter]}
    write(root / "package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {adapter["lockPath"]: locked}}))
    write(client / "third_party/browser-compliance/overrides.json", json.dumps(overrides))
    write(closure / "module-closure.json", json.dumps({"schemaVersion": 1, "packageLockPaths": []}))
    write(closure / "manifest.json", json.dumps({"schemaVersion": 1, "packages": [], "vendoredComponents": [] if failure == "missing-adapter" else [component]}))
    assert not (root / "node_modules").exists()
    assert not (client / "src").exists()
    if failure:
        with pytest.raises(module.ComplianceError): module.browser_inventory(tmp_path)
    else:
        result = module.browser_inventory(tmp_path)
        assert result[0]["name"] == "Synthetic adapter"
        assert len(result[0]["notices"]) == 3
