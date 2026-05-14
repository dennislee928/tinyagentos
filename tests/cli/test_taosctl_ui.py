from unittest.mock import patch

from click.testing import CliRunner

from taosctl.cli import cli


def test_ui_notify_posts_title_and_body():
    fake = {"notification_id": "ntf_xyz", "delivered": True}
    with patch("taosctl.http_client.post", return_value=fake) as p:
        result = CliRunner().invoke(
            cli, ["ui", "notify", "--title", "T", "--body", "B"]
        )
    assert result.exit_code == 0, result.output
    p.assert_called_once()
    call_args = p.call_args
    assert call_args.args[0] == "/api/ui/notify"
    assert call_args.kwargs["json"]["title"] == "T"
    assert call_args.kwargs["json"]["body"] == "B"
    # priority defaults to 'normal'
    assert call_args.kwargs["json"]["priority"] == "normal"
    assert "ntf_xyz" in result.output


def test_ui_notify_with_priority_high():
    with patch("taosctl.http_client.post", return_value={"delivered": True}) as p:
        result = CliRunner().invoke(
            cli, ["ui", "notify", "--title", "T", "--body", "B", "--priority", "high"]
        )
    assert result.exit_code == 0, result.output
    assert p.call_args.kwargs["json"]["priority"] == "high"


def test_ui_notify_with_app_origin():
    with patch("taosctl.http_client.post", return_value={"delivered": True}) as p:
        result = CliRunner().invoke(
            cli,
            ["ui", "notify", "--title", "T", "--body", "B", "--app-origin", "my-agent"],
        )
    assert result.exit_code == 0, result.output
    assert p.call_args.kwargs["json"]["app_origin"] == "my-agent"


def test_ui_notify_rejects_invalid_priority():
    """Click validates --priority client-side via Choice."""
    result = CliRunner().invoke(
        cli, ["ui", "notify", "--title", "T", "--body", "B", "--priority", "urgent"]
    )
    assert result.exit_code != 0
    assert "urgent" in result.output.lower() or "invalid" in result.output.lower()


def test_ui_notify_requires_title_and_body():
    """--title and --body are required."""
    result = CliRunner().invoke(cli, ["ui", "notify", "--body", "no title"])
    assert result.exit_code != 0
    assert "title" in result.output.lower()
