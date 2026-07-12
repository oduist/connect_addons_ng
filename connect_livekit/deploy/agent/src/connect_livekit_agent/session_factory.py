"""Build a livekit-agents AgentSession from an Odoo agent-config payload.

Kept separate from agent.py so the model/plugin wiring can be unit
tested without the LiveKit worker runtime. The plugin cascade mirrors
the per-agent choices made in Odoo (ADR-037).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _key(config: dict, provider: str, fallback: str = "") -> str:
    return (config.get("keys") or {}).get(provider) or fallback


def build_stt(config: dict, settings):
    from livekit.plugins import deepgram, openai
    provider = config.get("stt_provider") or "openai"
    language = config.get("language") or None
    if provider == "deepgram":
        return deepgram.STT(
            model=config.get("stt_model") or "nova-3",
            language=language or "multi",
            api_key=_key(config, "deepgram", settings.deepgram_api_key),
        )
    return openai.STT(
        model=config.get("stt_model") or "whisper-1",
        language=language,
        api_key=_key(config, "openai", settings.openai_api_key),
    )


def build_llm(config: dict, settings):
    from livekit.plugins import openai
    return openai.LLM(
        model=config.get("llm_model") or "gpt-4o-mini",
        api_key=_key(config, "openai", settings.openai_api_key),
    )


def build_tts(config: dict, settings):
    from livekit.plugins import elevenlabs, openai
    provider = config.get("tts_provider") or "openai"
    if provider == "elevenlabs":
        kwargs = {
            "api_key": _key(config, "elevenlabs", settings.elevenlabs_api_key),
        }
        if config.get("tts_model"):
            kwargs["model"] = config["tts_model"]
        if config.get("voice"):
            kwargs["voice_id"] = config["voice"]
        return elevenlabs.TTS(**kwargs)
    return openai.TTS(
        model=config.get("tts_model") or "tts-1",
        voice=config.get("voice") or "alloy",
        api_key=_key(config, "openai", settings.openai_api_key),
    )


def build_realtime_llm(config: dict, settings):
    from livekit.plugins import openai
    kwargs = {"api_key": _key(config, "openai", settings.openai_api_key)}
    if config.get("voice"):
        kwargs["voice"] = config["voice"]
    if config.get("llm_model"):
        kwargs["model"] = config["llm_model"]
    return openai.realtime.RealtimeModel(**kwargs)


def build_session(config: dict, settings):
    """Return a configured AgentSession (pipeline or realtime)."""
    from livekit.agents import AgentSession
    if config.get("mode") == "realtime":
        return AgentSession(llm=build_realtime_llm(config, settings))
    from livekit.plugins import silero
    return AgentSession(
        vad=silero.VAD.load(),
        stt=build_stt(config, settings),
        llm=build_llm(config, settings),
        tts=build_tts(config, settings),
    )
