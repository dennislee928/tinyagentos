"""taosctl ui — UI primitives. Subcommands land in Task 25."""
from __future__ import annotations

import click


@click.group(help="UI primitives (notify, ...).")
def ui_group() -> None:
    """taosctl ui."""
