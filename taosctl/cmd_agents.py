"""taosctl agents — manage agents. Subcommands land in Task 24."""
from __future__ import annotations

import click


@click.group(help="Manage taOS agents (list, deploy, start, stop, tokens, ...).")
def agents_group() -> None:
    """taosctl agents."""
