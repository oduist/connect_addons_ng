import pytest

from connect_3cx_agent.config import AgentSettings


@pytest.fixture
def settings(tmp_path):
    return AgentSettings(
        odoo_url="http://odoo.test",
        agent_token="test-agent-token-0123456789abcdef",
        pbx_url="https://pbx.test",
        client_id="agent-client",
        client_secret="agent-secret",
        state_path=str(tmp_path / "state.json"),
        recording_poll_interval=0.01,
    )
