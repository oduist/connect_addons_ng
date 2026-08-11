"""FastAPI app — the Odoo → agent direction.

Endpoints:
  POST /originate    — click-to-call via Call Control makecall
  POST /sync         — nudge the reconciler (config/participants)
  GET  /api/status   — version, WS/token/Odoo health, counters
  GET  /healthz      — liveness (unauthenticated, always 200)
  GET  /3cx/healthz  — readiness (503 unless the Call Control WS is up)

Everything except the health probes requires ``Authorization: Bearer
<threecx_api_key>`` (the shared Odoo⇄agent secret, ADR-015 pattern).
"""
from __future__ import annotations

import logging
import secrets
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from . import __version__
from .config import AgentSettings
from .handler import CallControlHandler
from .odoo_client import OdooClient
from .recordings import RecordingPoller
from .reconciler import Reconciler
from .tcx_api import ThreeCXClient
from .ws import CallControlWS

logger = logging.getLogger(__name__)


def _check_bearer(request: Request, token: str) -> bool:
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(auth[7:].strip(), token)


def build_app(
    settings: AgentSettings,
    tcx: ThreeCXClient,
    odoo: OdooClient,
    handler: CallControlHandler,
    ws: CallControlWS,
    recordings: RecordingPoller | None,
    reconciler: Reconciler,
    started_at: float,
) -> FastAPI:
    app = FastAPI(title="connect-3cx-agent")

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path in ("/healthz", "/3cx/healthz"):
            return await call_next(request)
        if _check_bearer(request, settings.agent_token):
            return await call_next(request)
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/3cx/healthz")
    async def readiness():
        if not ws.is_connected:
            return JSONResponse(
                {"status": "degraded", "ws_connected": False},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return {"status": "ok", "ws_connected": True}

    @app.get("/api/status")
    async def api_status():
        return {
            "version": __version__,
            "ws_connected": ws.is_connected,
            "token_ok": tcx.last_token_ok,
            "pbx_configured": tcx.configured(),
            "odoo_ok": odoo.last_call_ok,
            "uptime_seconds": int(time.time() - started_at),
            "outbox_depth": odoo.outbox_depth(),
            "events_forwarded": handler.forwarded_count,
            "events_dropped": handler.dropped_count,
            "recordings_uploaded": recordings.uploaded_count
                                   if recordings else 0,
            "recordings_failed": recordings.failed_count
                                 if recordings else 0,
        }

    @app.post("/sync")
    async def sync_endpoint(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scope = (payload or {}).get("scope", "all")
        reconciler.trigger(scope=scope)
        return {"status": "queued", "scope": scope}

    @app.post("/originate")
    async def originate(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        dn = str((payload or {}).get("dn") or "").strip()
        destination = str((payload or {}).get("destination") or "").strip()
        if not dn or not destination:
            return JSONResponse({"error": "bad_request"}, status_code=400)
        timeout = int((payload or {}).get("timeout") or 30)
        device_id = str((payload or {}).get("device_id") or "")
        try:
            response = await tcx.makecall(
                dn, destination, timeout=timeout, device_id=device_id)
        except Exception as exc:
            logger.warning("Originate %s -> %s failed: %s",
                           dn, destination, exc)
            return JSONResponse({"error": str(exc)}, status_code=502)
        return {"response": response}

    return app
