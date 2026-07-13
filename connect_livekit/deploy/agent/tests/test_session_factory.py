"""Plugin cascade wiring tests (constructors only, no network)."""
from connect_livekit_agent.config import AgentSettings
from connect_livekit_agent import session_factory


def _settings():
    return AgentSettings(odoo_url="x", agent_token="y")


def test_build_stt_openai_without_language():
    # An unset agent language must fall back to the plugin default:
    # openai.STT(language=None) crashes inside LanguageCode().
    config = {"stt_provider": "openai", "language": "",
              "keys": {"openai": "sk-test"}}
    assert session_factory.build_stt(config, _settings()) is not None


def test_build_stt_openai_with_language():
    config = {"stt_provider": "openai", "language": "de",
              "keys": {"openai": "sk-test"}}
    assert session_factory.build_stt(config, _settings()) is not None


def test_build_stt_deepgram_without_language():
    config = {"stt_provider": "deepgram", "language": "",
              "keys": {"deepgram": "dg-test"}}
    assert session_factory.build_stt(config, _settings()) is not None
