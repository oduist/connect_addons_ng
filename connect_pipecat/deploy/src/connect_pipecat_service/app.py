import base64
import binascii
import logging
import secrets

from fastapi import FastAPI, WebSocket

from . import __version__
from .bot import run_call
from .config import ServiceSettings
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)


def _basic_auth_valid(websocket: WebSocket, expected: str) -> bool:
    auth = websocket.headers.get('authorization', '')
    if not auth.lower().startswith('basic '):
        return False
    try:
        decoded = base64.b64decode(auth[6:].strip(), validate=True).decode('utf-8')
        username, password = decoded.split(':', 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    return username == 'pipecat' and secrets.compare_digest(password, expected)


def build_app(settings: ServiceSettings) -> FastAPI:
    app = FastAPI(title='Connect Pipecat Service', version=__version__)

    @app.get('/health')
    async def health():
        # FastAPI does not bind arbitrary headers without Header(), so read the
        # request in middleware-free form through a dedicated dependency below.
        return {'status': 'ok', 'version': __version__}

    @app.middleware('http')
    async def bearer_auth(request, call_next):
        if request.url.path == '/health':
            auth = request.headers.get('authorization', '')
            if (not auth.lower().startswith('bearer ') or not secrets.compare_digest(
                    auth[7:].strip(), settings.pipecat_service_token)):
                from starlette.responses import JSONResponse
                return JSONResponse({'error': 'unauthorized'}, status_code=401)
        return await call_next(request)

    @app.websocket('/ws')
    async def websocket_endpoint(websocket: WebSocket):
        if not _basic_auth_valid(websocket, settings.pipecat_service_token):
            await websocket.close(code=4401)
            return
        call_uuid = websocket.query_params.get('call_uuid', '').strip()
        raw_agent_id = websocket.query_params.get('agent_id', '').strip()
        try:
            agent_id = int(raw_agent_id)
        except ValueError:
            await websocket.close(code=4400)
            return
        if not call_uuid:
            await websocket.close(code=4400)
            return
        await websocket.accept(subprotocol='audio.drachtio.org')
        odoo = OdooClient(settings.odoo_url, settings.pipecat_service_token)
        try:
            await run_call(websocket, call_uuid, agent_id, odoo)
        except Exception:
            logger.exception('Call %s failed', call_uuid)
            try:
                await websocket.close(code=1011)
            except RuntimeError:
                pass
        finally:
            await odoo.close()

    return app
