"""Config loading tests."""
from connect_livekit_agent.config import AgentSettings


def test_defaults():
    s = AgentSettings(odoo_url="https://odoo.example.com", agent_token="tok")
    assert s.odoo_url == "https://odoo.example.com"
    assert s.agent_token == "tok"
    assert s.livekit_url == "ws://livekit:7880"
    assert s.egress_out_dir == "/out"


def test_env_override(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://lk.example.com")
    monkeypatch.setenv("POLL_INTERVAL", "10")
    s = AgentSettings(odoo_url="x", agent_token="y")
    assert s.livekit_url == "wss://lk.example.com"
    assert s.poll_interval == 10.0
