"""Module entry: ``python -m tinyagentos``.

Honours ``TAOS_HOST`` / ``TAOS_PORT`` env vars (used by the Mac launcher
to bind to a private 127.0.0.1 port) and falls back to ``data/config.yaml``
when they are unset (preserves the existing console-script behaviour).
"""
from __future__ import annotations

import os

from tinyagentos.app import PROJECT_DIR, create_app, load_config


def main() -> None:
    import uvicorn

    env_host = os.environ.get("TAOS_HOST")
    env_port = os.environ.get("TAOS_PORT")

    if env_host or env_port:
        host = env_host or "127.0.0.1"
        port = int(env_port) if env_port else 6969
    else:
        config = load_config(PROJECT_DIR / "data" / "config.yaml")
        host = config.server.get("host", "0.0.0.0")
        port = config.server.get("port", 6969)

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
