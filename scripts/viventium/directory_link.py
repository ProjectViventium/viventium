#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a public Viventium instance under the viventium.ai vanity directory."
    )
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--directory-base-url", default="https://viventium.ai")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    return parser.parse_args()


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError("No remote-access state file exists yet. Start Viventium with public remote access first.")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Unable to read the remote-access state file: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Remote-access state is invalid.")
    return raw


def normalize_https_origin(value: str, *, label: str) -> str:
    try:
        parsed = urllib.parse.urlparse(value)
    except Exception as exc:
        raise RuntimeError(f"{label} must be a valid https:// URL") from exc
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError(f"{label} must be a valid https:// URL")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError(f"{label} must not include a path, query, or fragment")
    return f"https://{parsed.hostname}" + (f":{parsed.port}" if parsed.port and parsed.port != 443 else "")


def normalize_directory_base_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlparse(value)
    except Exception as exc:
        raise RuntimeError("directory_base_url must be a valid URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("directory_base_url must be a valid http:// or https:// URL")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("directory_base_url may only use http:// for localhost testing")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError("directory_base_url must not include a path, query, or fragment")
    return f"{parsed.scheme}://{parsed.hostname}" + (
        f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    )


def normalize_username(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise RuntimeError("username is required")
    if len(normalized) > 32:
        raise RuntimeError("username must be 32 characters or fewer")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if normalized[0] == "-" or normalized[-1] == "-":
        raise RuntimeError("username cannot start or end with a hyphen")
    if any(char not in allowed for char in normalized):
        raise RuntimeError("username may only contain lowercase letters, numbers, and hyphens")
    return normalized


def canonical_payload(payload: dict[str, str]) -> str:
    return "\n".join(
        [
            f"username={payload['username']}",
            f"targetOrigin={payload['targetOrigin']}",
            f"instanceId={payload['instanceId']}",
            f"publicKeyFingerprint={payload['publicKeyFingerprint']}",
            f"issuedAt={payload['issuedAt']}",
        ]
    )


def sign_payload(private_key_path: Path, payload_text: str) -> str:
    if not private_key_path.exists():
        raise RuntimeError(
            "The Viventium directory private key is missing. Restart Viventium with public remote access first."
        )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(payload_text)
        payload_path = Path(handle.name)
    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(private_key_path), str(payload_path)],
            check=False,
            capture_output=True,
        )
    finally:
        payload_path.unlink(missing_ok=True)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or b"").decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"Unable to sign the Viventium directory registration payload: {stderr}".strip())
    return base64.b64encode(result.stdout).decode("ascii")


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_file)
    state = load_state(state_path)

    username = normalize_username(args.username)
    target_origin = normalize_https_origin(str(state.get("public_client_url") or "").strip(), label="public_client_url")
    directory_base_url = normalize_directory_base_url(args.directory_base_url)
    instance_id = str(state.get("directory_instance_id") or "").strip()
    public_key_fingerprint = str(state.get("directory_public_key_fingerprint") or "").strip()
    if not instance_id or not public_key_fingerprint:
        raise RuntimeError(
            "This Viventium runtime is missing directory verification metadata. Restart Viventium after pulling the latest branch."
        )

    payload = {
        "username": username,
        "targetOrigin": target_origin,
        "instanceId": instance_id,
        "publicKeyFingerprint": public_key_fingerprint,
        "issuedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    signature = sign_payload(state_path.parent / "directory-identity" / "private.pem", canonical_payload(payload))

    request_payload = json.dumps({"payload": payload, "signature": signature}).encode("utf-8")
    request = urllib.request.Request(
        directory_base_url.rstrip("/") + "/api/viventium/directory/register",
        data=request_payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(int(args.timeout_seconds), 5)) as response:
            print(response.read().decode("utf-8", errors="ignore"))
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore").strip()
        raise RuntimeError(body or f"Directory registration failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Directory registration failed: {exc.reason}") from exc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
