"""FastAPI app — accepts /firewall/sync from Odoo and exposes the JSON
API the Lit dashboard consumes.

Authentication: every request must carry either the Bearer token (Odoo →
service direction) or HTTP basic auth (admin browser → dashboard). We
check both and accept whichever matches.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import ipset_manager
from .config import ServiceSettings
from .constants import (
    IPSET_AUTHENTICATED,
    IPSET_BANNED,
    IPSET_BLACKLIST,
    IPSET_WHITELIST,
)
from .event_bus import EventBus
from .odoo_client import OdooClient
from .reconciler import Reconciler

logger = logging.getLogger(__name__)

# Where the dashboard's HTML/CSS/JS lives at runtime. Defaults to the
# /app/dashboard layout shipped by Dockerfile; override with the
# DASHBOARD_DIR env var for local development.
DASHBOARD_DIR = Path(os.environ.get("DASHBOARD_DIR", "/app/dashboard"))


def _check_bearer(request: Request, token: str) -> bool:
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(auth[7:].strip(), token)


def _check_basic(request: Request, user: str, password: str) -> bool:
    if not user or not password:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(auth[6:].strip()).decode("utf-8", "replace")
    except Exception:
        return False
    if ":" not in raw:
        return False
    u, p = raw.split(":", 1)
    return secrets.compare_digest(u, user) and secrets.compare_digest(p, password)


def build_app(
    settings: ServiceSettings,
    reconciler: Reconciler,
    odoo: OdooClient,
    event_bus: EventBus,
    started_at: float,
) -> FastAPI:
    app = FastAPI(title="connect-firewall-service")
    jinja = Environment(
        loader=FileSystemLoader(DASHBOARD_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    static_dir = DASHBOARD_DIR / "static"
    if static_dir.is_dir():
        app.mount(
            "/firewall/static",
            StaticFiles(directory=str(static_dir)),
            name="firewall-static",
        )

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        path = request.url.path
        if path in ("/healthz", "/firewall/healthz"):
            return await call_next(request)
        if _check_bearer(request, settings.agent_token):
            return await call_next(request)
        if _check_basic(request, settings.dashboard_user, settings.dashboard_password):
            return await call_next(request)
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="firewall"'},
        )

    # ------------------------------------------------------------------
    # Sync trigger from Odoo
    # ------------------------------------------------------------------

    @app.post("/firewall/sync")
    async def sync_endpoint(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scope = (payload or {}).get("scope", "all")
        reconciler.trigger(scope=scope)
        return {"status": "queued", "scope": scope}

    # ------------------------------------------------------------------
    # Health / heartbeat / JSON API
    # ------------------------------------------------------------------

    @app.get("/healthz")
    @app.get("/firewall/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/firewall/api/heartbeat")
    async def api_heartbeat():
        return {
            "version": getattr(settings, "version", None),
            "esl_connected": True,  # populated by ESL loop in v2
            "odoo_connected": odoo.last_call_ok,
            "uptime_seconds": int(time.time() - started_at),
            "last_sync_at": reconciler.last_sync_at,
            "last_sync_scope": reconciler.last_sync_scope,
            "last_sync_error": reconciler.last_sync_error,
        }

    def _entries_payload(name: str) -> list[dict]:
        return ipset_manager.list_entries(name)

    @app.get("/firewall/api/bans")
    async def api_bans():
        return _entries_payload(IPSET_BANNED)

    @app.get("/firewall/api/authenticated")
    async def api_authenticated():
        return _entries_payload(IPSET_AUTHENTICATED)

    @app.get("/firewall/api/whitelist")
    async def api_whitelist():
        return _entries_payload(IPSET_WHITELIST)

    @app.get("/firewall/api/blacklist")
    async def api_blacklist():
        return _entries_payload(IPSET_BLACKLIST)

    @app.delete("/firewall/api/bans/{ip}")
    async def api_unban(ip: str):
        ok = ipset_manager.del_entry(IPSET_BANNED, ip)
        odoo.enqueue_event({
            "event_type": "manual_unban_applied",
            "ip": ip,
            "details": "from dashboard",
        })
        event_bus.record({"type": "unban", "ip": ip})
        return {"removed": bool(ok)}

    @app.get("/firewall/api/attempts-per-minute")
    async def api_attempts():
        return event_bus.attempts_per_minute()

    @app.get("/firewall/api/top-ips")
    async def api_top_ips():
        return event_bus.top_ips()

    # ------------------------------------------------------------------
    # Server-Sent Events stream
    # ------------------------------------------------------------------

    @app.get("/firewall/events")
    async def sse_events():
        async def gen():
            try:
                async for event in event_bus.subscribe():
                    et = event.get("type", "message")
                    payload = json.dumps(event, default=str)
                    yield "event: {}\ndata: {}\n\n".format(et, payload)
            except asyncio.CancelledError:
                return
        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # Dashboard shell page
    # ------------------------------------------------------------------

    @app.get("/firewall/", response_class=HTMLResponse)
    @app.get("/firewall", response_class=HTMLResponse)
    async def dashboard_index():
        tpl = jinja.get_template("index.html")
        return tpl.render(version=getattr(settings, "version", ""))

    return app
