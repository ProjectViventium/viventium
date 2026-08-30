from __future__ import annotations

import re


_CREDENTIAL_NAMES = (
    "workbench_token|access_token|refresh_token|id_token|api_key|apikey|client_secret"
)
_ASSIGNED_CREDENTIAL = re.compile(
    rf"\b({_CREDENTIAL_NAMES})\s*=\s*[^&\s#]+",
    re.IGNORECASE,
)
_JSON_CREDENTIAL = re.compile(
    rf"([\"'](?:{_CREDENTIAL_NAMES})[\"']\s*:\s*[\"'])[^\"']*([\"'])",
    re.IGNORECASE,
)


def redact_credential_assignments(value: str) -> str:
    value = _ASSIGNED_CREDENTIAL.sub(r"\1=<redacted>", value)
    return _JSON_CREDENTIAL.sub(r"\1<redacted>\2", value)
