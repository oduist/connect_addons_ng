"""Agent configuration: env vars only (secrets)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Everything the sidecar needs to start.

    Per-agent AI configuration (instructions, models, tool token) is
    pulled from Odoo at dispatch time; these are the process-level
    secrets and endpoints. AI vendor keys are the fallback used when the
    Odoo agent-config payload does not carry one.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # Base URL of the paired Odoo. The worker appends /livekit/api/* and
    # /livekit/webhook/* paths to it.
    odoo_url: str = ""
    # Must match connect.settings.livekit_agent_token.
    agent_token: str = ""

    # LiveKit server (the worker connects as a participant).
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # AI vendor keys (fallback; Odoo normally supplies them per agent).
    openai_api_key: str = ""
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Uploader (upload-recordings command).
    egress_out_dir: str = "/out"
    state_dir: str = "/state"
    upload_delay: float = 5.0
    poll_interval: float = 5.0

    log_level: str = "INFO"
