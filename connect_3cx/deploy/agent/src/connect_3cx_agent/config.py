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
    runtime configuration fetched from Odoo (PBX URL, 3CX API client
    credentials) so the agent can boot even when Odoo is unreachable.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- Odoo ---------------------------------------------------------
    # Base URL of the paired Odoo. The agent appends
    # /3cx/webhook/* and /3cx/api/* paths to it.
    odoo_url: str

    # --- Shared secret between Odoo and this agent ---------------------
    # Must match connect.settings.threecx_api_key. Used in both
    # directions: agent -> Odoo webhooks and Odoo -> agent HTTP API.
    agent_token: str

    # --- 3CX PBX --------------------------------------------------------
    # Normally pulled from Odoo /3cx/api/config and cached; env vars act
    # as the bootstrap/override. client_id/client_secret belong to a 3CX
    # API client application (Admin Console -> Integrations -> API) with
    # BOTH the Call Control and the Configuration API scopes checked.
    # The agent must be the only consumer of that client application:
    # 3CX keeps a single active token per client, so a second consumer
    # would invalidate the agent's tokens (and vice versa).
    pbx_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    verify_tls: bool = True

    # --- Local HTTP server ----------------------------------------------
    http_bind_host: str = "127.0.0.1"
    http_bind_port: int = 8083

    # --- Recordings (XAPI poller) ---------------------------------------
    recordings_enabled: bool = True
    recording_poll_interval: float = 30.0
    recording_max_mb: int = 200

    # --- Event forwarding ----------------------------------------------
    event_batch_size: int = 50
    event_batch_window: float = 0.2

    # --- Loops ----------------------------------------------------------
    reconcile_interval: int = 60
    heartbeat_interval: int = 60
    participant_ttl: int = 21600

    # --- Local state ----------------------------------------------------
    state_path: str = "/var/lib/connect-3cx/state.json"

    # --- Logging --------------------------------------------------------
    log_level: str = "INFO"
    ws_trace: bool = False


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
        "pbx_url",
        "client_id",
        "client_secret",
        "recordings_enabled",
    )
