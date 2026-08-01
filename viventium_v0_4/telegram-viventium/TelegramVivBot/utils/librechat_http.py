from __future__ import annotations

import urllib.parse
from typing import Any


def async_client_options_for_url(url: str) -> dict[str, Any]:
    """Keep plain-HTTP loopback clients out of unused TLS and proxy setup."""
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return {}
    if parsed.scheme.lower() == "http" and (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        # Plain HTTP cannot use certificate verification. HTTPX does not
        # follow redirects unless asked, so this policy cannot cross into an
        # HTTPS hop. Remote HTTP and every HTTPS URL retain HTTPX defaults.
        return {"trust_env": False, "verify": False}
    return {}
