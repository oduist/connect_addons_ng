"""Agent configuration: env vars + optional JSON runtime cache."""
import json
import logging
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AgentSettings(BaseSettings):
    """All knobs the agent needs to start.

    Secrets live in env vars only; the JSON cache holds the last-known
    runtime configuration fetched from Odoo (AMI credentials, event
    filter) so the agent can boot even when Odoo is unreachable.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- Odoo ---------------------------------------------------------
    # Base URL of the paired Odoo. The agent appends
    # /asterisk/webhook/* and /asterisk/api/* paths to it.
    odoo_url: str

    # --- Shared secret between Odoo and this agent ---------------------
    # Must match connect.settings.asterisk_agent_token. Used in both
    # directions: agent -> Odoo webhooks and Odoo -> agent HTTP API.
    # The agent fails fast at boot if unset.
    agent_token: str

    # --- Asterisk AMI ---------------------------------------------------
    # Normally pulled from Odoo /asterisk/api/config and cached; env vars
    # act as the bootstrap/override.
    ami_host: str = "127.0.0.1"
    ami_port: int = 5038
    ami_user: str = "connect-agent"
    ami_password: str = ""
    ami_ping_interval: float = 30.0

    # --- Local HTTP server ----------------------------------------------
    http_bind_host: str = "127.0.0.1"
    http_bind_port: int = 8082

    # --- Recordings -----------------------------------------------------
    recordings_enabled: bool = True
    recording_paths: str = "/var/spool/asterisk/monitor"
    recording_upload_delay: float = 5.0
    recording_max_mb: int = 200
    recording_retry_hours: int = 24
    recording_delete_after_upload: bool = False

    # --- Event forwarding ----------------------------------------------
    event_batch_size: int = 50
    event_batch_window: float = 0.2
    events: str = ""  # comma-separated override; empty = DEFAULT_EVENTS

    # --- Loops ----------------------------------------------------------
    reconcile_interval: int = 60
    heartbeat_interval: int = 60
    call_state_ttl: int = 21600

    # --- Local state ----------------------------------------------------
    state_path: str = "/var/lib/connect-asterisk/state.json"

    # --- Logging --------------------------------------------------------
    log_level: str = "INFO"
    ami_trace: bool = False


def load_runtime_cache(path: str) -> Optional[dict]:
    """Read the runtime cache from disk if it exists."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as exc:
        logger.warning("Cannot read runtime cache %s: %s", path, exc)
        return None


def save_runtime_cache(path: str, data: dict) -> None:
    """Persist runtime cache to disk, creating parent dirs as needed."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, sort_keys=True))
    except Exception as exc:
        logger.warning("Cannot write runtime cache %s: %s", path, exc)


def apply_cache_to_settings(settings: AgentSettings, cache: dict) -> None:
    """Mutate settings in-place with values from the runtime cache."""
    for key, value in cache.items():
        if hasattr(settings, key):
            try:
                setattr(settings, key, value)
            except Exception:
                pass


def runtime_cache_keys() -> tuple[str, ...]:
    """Settings that get persisted in the JSON cache."""
    return (
        "ami_host",
        "ami_port",
        "ami_user",
        "ami_password",
        "events",
        "recordings_enabled",
    )
