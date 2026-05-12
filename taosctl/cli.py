"""taosctl — root command + subgroup wiring."""
from __future__ import annotations

import click

from taosctl import __version__
from taosctl.cmd_agents import agents_group
from taosctl.cmd_auth import auth_group
from taosctl.cmd_ui import ui_group


@click.group()
@click.version_option(__version__, prog_name="taosctl")
def cli() -> None:
    """taosctl — control taOS programmatically.

    Set TAOS_TOKEN (or run `taosctl auth login`) and TAOS_URL (default
    http://localhost:6969) to point at your controller.
    """


cli.add_command(agents_group, name="agents")
cli.add_command(ui_group, name="ui")
cli.add_command(auth_group, name="auth")
