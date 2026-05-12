from click.testing import CliRunner

from taosctl.cli import cli


def test_taosctl_help_works():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "taosctl" in result.output.lower()
    assert "agents" in result.output
    assert "ui" in result.output
    assert "auth" in result.output


def test_taosctl_version_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    # Version follows semver
    assert "0." in result.output


def test_taosctl_no_args_shows_help_or_usage():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    # Click conventionally shows usage when called with no command
    output = result.output.lower()
    assert "usage" in output or "commands" in output


def test_taosctl_resolve_url_default():
    from taosctl.config import resolve_url
    import os
    saved = os.environ.pop("TAOS_URL", None)
    try:
        assert resolve_url() == "http://localhost:6969"
    finally:
        if saved is not None:
            os.environ["TAOS_URL"] = saved


def test_taosctl_resolve_url_from_env(monkeypatch):
    monkeypatch.setenv("TAOS_URL", "http://test.example:1234")
    from taosctl.config import resolve_url
    assert resolve_url() == "http://test.example:1234"


def test_taosctl_resolve_token_from_env(monkeypatch):
    monkeypatch.setenv("TAOS_TOKEN", "taos_agent_envtoken")
    from taosctl.config import resolve_token
    assert resolve_token() == "taos_agent_envtoken"


def test_taosctl_resolve_token_returns_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("TAOS_TOKEN", raising=False)
    monkeypatch.setattr("taosctl.config.CREDENTIALS_PATH", tmp_path / "no-such-file")
    from taosctl.config import resolve_token
    assert resolve_token() is None
