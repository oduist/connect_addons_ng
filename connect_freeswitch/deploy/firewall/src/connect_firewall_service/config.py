"""Service configuration: env vars + optional JSON cache."""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ServiceSettings(BaseSettings):
    """All knobs the service needs to start.

    Secrets live in env vars only; the JSON cache holds the last-known
    runtime configuration fetched from Odoo (ports, timeouts, etc.) so
    we can boot the firewall even when Odoo is unreachable.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- Odoo ---------------------------------------------------------
    # Base URL of the paired Odoo. The service appends
    # /freeswitch/firewall/api/* paths to it.
    odoo_url: str

    # --- Shared secret between Odoo and this service ------------------
    # Required. Authenticates the service against Odoo's
    # /freeswitch/firewall/api/* controllers and is also accepted on
    # /firewall/sync coming from Odoo. Must match
    # connect.settings.firewall_service_token. The service fails fast
    # at boot if unset.
    agent_token: str

    # --- FreeSWITCH ESL -----------------------------------------------
    fs_esl_host: str = "127.0.0.1"
    fs_esl_port: int = 8021
    # Required. Must match the password configured in the paired
    # FreeSWITCH container (event_socket.conf.xml, populated from
    # FS_ESL_PASSWORD). The service fails fast at boot if unset.
    fs_esl_password: str

    # --- Local HTTP server --------------------------------------------
    http_bind_host: str = "127.0.0.1"
    http_bind_port: int = 8081

    # --- Dashboard basic auth -----------------------------------------
    dashboard_user: str = "admin"
    dashboard_password: str = ""

    # --- Local state --------------------------------------------------
    config_cache_path: str = "/var/lib/connect-firewall/config.json"

    # --- Logging ------------------------------------------------------
    log_level: str = "INFO"

    # Runtime values fetched from Odoo (mirrored into the JSON cache).
    firewall_enabled: bool = False
    firewall_heartbeat_interval: int = 60
    firewall_tcp_ports: str = "5060,5061,5080,5081"
    firewall_udp_ports: str = "5060,5061,5080,5081"
    firewall_banned_timeout: int = 86400
    firewall_authenticated_timeout: int = 604800
    firewall_expire_short_timeout: int = 30
    firewall_expire_long_timeout: int = 86400


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


def apply_cache_to_settings(settings: ServiceSettings, cache: dict) -> None:
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
        "firewall_enabled",
        "firewall_heartbeat_interval",
        "firewall_tcp_ports",
        "firewall_udp_ports",
        "firewall_banned_timeout",
        "firewall_authenticated_timeout",
        "firewall_expire_short_timeout",
        "firewall_expire_long_timeout",
    )
