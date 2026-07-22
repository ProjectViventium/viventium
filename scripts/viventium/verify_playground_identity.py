#!/usr/bin/env python3
"""Verify that a playground listener is the exact Viventium surface requested."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


MAX_IDENTITY_BYTES = 64 * 1024


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def read_identity(base_url: str, timeout: float) -> dict[str, object]:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("playground base URL must be an absolute HTTP(S) URL")
    identity_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", "api/health")
    request = urllib.request.Request(
        identity_url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache"},
    )
    opener = urllib.request.build_opener(_NoRedirects())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"playground identity returned HTTP {response.status}")
        body = response.read(MAX_IDENTITY_BYTES + 1)
    if len(body) > MAX_IDENTITY_BYTES:
        raise ValueError("playground identity response is too large")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("playground identity is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("playground identity must be a JSON object")
    return payload


def verify_identity(payload: dict[str, object], variant: str, source_ref: str) -> None:
    expected_surface = f"{variant}-playground"
    expected = {
        "schema_version": 1,
        "product": "viventium-playground",
        "status": "ok",
        "surface": expected_surface,
        "variant": variant,
        "source_ref": source_ref,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(
                f"playground identity {key} mismatch: expected {expected_value!r}, "
                f"received {payload.get(key)!r}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--variant", required=True, choices=("modern", "classic"))
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--timeout", type=float, default=2.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = read_identity(args.base_url, args.timeout)
        verify_identity(payload, args.variant, args.source_ref)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f"playground identity verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
