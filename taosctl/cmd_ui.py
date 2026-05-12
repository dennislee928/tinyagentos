"""taosctl ui — present things to the user.

Pass 1 ships notify. Pass 2 will add the multi-user store migration that
unblocks action_url + cross-device push, plus spawn_window, drop_file,
render_chart, and pin_widget primitives.
"""
from __future__ import annotations

import json

import click

from taosctl import http_client


@click.group(help="Render things in the user's desktop UI.")
def ui_group() -> None:
    """taosctl ui."""


@ui_group.command("notify", help="Send a notification to your agent's user.")
@click.option("--title", required=True, help="Short notification title (max 120 chars).")
@click.option("--body", required=True, help="Notification body text.")
@click.option(
    "--priority",
    type=click.Choice(["low", "normal", "high"]),
    default="normal",
    help="One of low/normal/high. Defaults to normal.",
)
@click.option(
    "--app-origin",
    "app_origin",
    help="Optional attribution shown to the user; defaults to the calling agent's name.",
)
@click.option("--json", "json_out", is_flag=True, help="Emit only the raw JSON response.")
def notify_cmd(title: str, body: str, priority: str, app_origin: str | None, json_out: bool) -> None:
    payload = {"title": title, "body": body, "priority": priority}
    if app_origin:
        payload["app_origin"] = app_origin
    result = http_client.post("/api/ui/notify", json=payload)
    click.echo(json.dumps(result, indent=2) if json_out else json.dumps(result, indent=2))
