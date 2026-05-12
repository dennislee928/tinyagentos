from tinyagentos.scope import scope_matches


def test_wildcard_matches_all():
    assert scope_matches(["*"], "agents.deploy") is True
    assert scope_matches(["*"], "anything.at.all") is True


def test_namespace_glob_matches():
    assert scope_matches(["agents.*"], "agents.deploy") is True
    assert scope_matches(["agents.*"], "agents.list") is True
    assert scope_matches(["agents.*"], "memory.read") is False


def test_exact_match():
    assert scope_matches(["agents.deploy", "ui.notify"], "ui.notify") is True
    assert scope_matches(["agents.deploy"], "ui.notify") is False


def test_empty_scope_denies_all():
    assert scope_matches([], "agents.deploy") is False


def test_unrelated_scope_returns_false():
    assert scope_matches(["files.read"], "agents.deploy") is False


def test_nested_glob():
    assert scope_matches(["agents.token.*"], "agents.token.issue") is True
    assert scope_matches(["agents.token.*"], "agents.list") is False
