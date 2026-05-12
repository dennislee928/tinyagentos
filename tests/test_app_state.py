from tinyagentos.stores.agent_tokens_store import AgentTokensStore


def test_app_state_has_agent_tokens_store(app):
    """app.state.agent_tokens_store is set up eagerly (available in tests without lifespan)."""
    store = getattr(app.state, "agent_tokens_store", None)
    assert isinstance(store, AgentTokensStore)
