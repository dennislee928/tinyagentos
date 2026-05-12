"""Shared configuration: server URL + auth token resolution."""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_URL = "http://localhost:6969"
CREDENTIALS_PATH = Path.home() / ".config" / "taos" / "credentials"


def resolve_url() -> str:
    """Resolve the controller URL. Env wins over the default."""
    return os.environ.get("TAOS_URL", DEFAULT_URL)


def resolve_token() -> str | None:
    """Resolve the bearer token. Env wins over the credentials file. Returns
    None if neither is set."""
    token = os.environ.get("TAOS_TOKEN")
    if token:
        return token
    path = CREDENTIALS_PATH
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("token")
        except (json.JSONDecodeError, OSError):
            return None
    return None
