"""taosctl auth — token management. Subcommands land in Task 23."""
from __future__ import annotations

import click


@click.group(help="Authentication: log in, check status, identify the token bearer.")
def auth_group() -> None:
    """taosctl auth."""
