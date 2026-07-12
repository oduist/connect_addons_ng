"""FreeSWITCH implementation of the TelephonyProvider interface.

FreeSWITCH is not driven directly: an Odoo instance running the Oduist
Connect modules (connect_freeswitch + connect_dograh) owns the
FreeSWITCH XML-RPC control plane. The contract is:

- Inbound: Odoo's per-call dialplan handler POSTs a JSON webhook marked
  ``provider=freeswitch`` to ``/api/v1/telephony/inbound/run`` with the
  shared service token as Bearer auth. ``start_inbound_stream`` answers
  with JSON carrying the media WebSocket URL; Odoo renders a dialplan
  that attaches mod_audio_fork to it.
- Outbound: ``initiate_call`` POSTs Odoo's ``/dograh/api/originate``,
  which originates through the customer's outbound routes and connects
  the answered leg to the same media WebSocket.
- Hangup: the frame serializer's hangup strategy POSTs Odoo's
  ``/dograh/api/hangup`` (uuid_kill).
"""

import hmac
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiohttp
from fastapi import HTTPException
from loguru import logger

from api.services.telephony.base import (
    CallInitiationResult,
    NormalizedInboundData,
    TelephonyProvider,
)

if TYPE_CHECKING:
    from fastapi import WebSocket


class FreeswitchProvider(TelephonyProvider):
    """FreeSWITCH (Oduist Connect / Odoo) implementation of TelephonyProvider."""

    PROVIDER_NAME = "freeswitch"
    WEBHOOK_ENDPOINT = None  # Odoo posts to the shared /inbound/run dispatcher

    def __init__(self, config: Dict[str, Any]):
        """Initialize FreeswitchProvider with configuration.

        Args:
            config: Dictionary containing:
                - account_id: Identifier Odoo stamps on inbound webhooks
                - odoo_url: Odoo base URL (e.g., https://odoo.example.com)
                - service_token: Shared secret for both webhook directions
                - from_numbers: List of caller ID numbers (optional)
        """
        self.account_id = config.get("account_id", "")
        self.odoo_url = (config.get("odoo_url") or "").rstrip("/")
        self.service_token = config.get("service_token", "")
        self.from_numbers = config.get("from_numbers", [])

        if isinstance(self.from_numbers, str):
            self.from_numbers = [self.from_numbers]

    def _odoo_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.service_token}"}

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        from_number: Optional[str] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        """Initiate an outbound call through Odoo/FreeSWITCH.

        Odoo originates the destination leg over the customer's outbound
        routes and, once answered, attaches mod_audio_fork to the media
        WebSocket of ``workflow_run_id``.
        """
        from api.utils.common import get_backend_endpoints

        if not self.validate_config():
            raise ValueError("FreeSWITCH provider not properly configured")

        workflow_id = kwargs.get("workflow_id")
        organization_id = kwargs.get("organization_id")
        if not (workflow_id and organization_id and workflow_run_id):
            raise ValueError(
                "FreeSWITCH outbound calls need workflow_id, "
                "organization_id and workflow_run_id"
            )

        # Call-control style (like Telnyx): build the media WebSocket URL
        # here and let Odoo attach mod_audio_fork to it on answer.
        _, wss_backend_endpoint = await get_backend_endpoints()
        websocket_url = (
            f"{wss_backend_endpoint}/api/v1/telephony/ws/"
            f"{workflow_id}/{organization_id}/{workflow_run_id}"
        )

        endpoint = f"{self.odoo_url}/dograh/api/originate"
        payload = {
            "to_number": to_number,
            "from_number": from_number,
            "workflow_run_id": workflow_run_id,
            "websocket_url": websocket_url,
        }

        logger.info(
            f"[FreeSWITCH] Initiating call to {to_number} "
            f"via {endpoint}, workflow_run_id={workflow_run_id}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=self._odoo_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    logger.error(
                        f"[FreeSWITCH] Originate failed: "
                        f"HTTP {response.status} - {response_text}"
                    )
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to originate FreeSWITCH call: {response_text}",
                    )

                response_data = json.loads(response_text)
                call_uuid = response_data.get("call_uuid", "")

                return CallInitiationResult(
                    call_id=call_uuid,
                    status=response_data.get("status", "originated"),
                    caller_number=response_data.get("from_number") or from_number,
                    provider_metadata={"call_id": call_uuid},
                    raw_response=response_data,
                )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Call status polling is not exposed by the Odoo control plane."""
        return {"call_id": call_id, "status": "unknown"}

    async def get_available_phone_numbers(self) -> List[str]:
        """Return configured caller ID numbers."""
        return self.from_numbers

    def validate_config(self) -> bool:
        """Validate FreeSWITCH provider configuration."""
        return bool(self.odoo_url and self.service_token and self.account_id)

    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        """Status callbacks carry the Bearer token; verified in routes."""
        return True

    async def get_webhook_response(
        self, workflow_id: int, organization_id: int, workflow_run_id: int
    ) -> str:
        """Unused: inbound responses are built by start_inbound_stream."""
        logger.warning(
            "get_webhook_response called for FreeSWITCH - this should not happen."
        )
        return ""

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        """FreeSWITCH does not provide call cost information."""
        return {
            "cost_usd": 0.0,
            "duration": 0,
            "status": "unknown",
            "error": "FreeSWITCH does not support cost retrieval",
        }

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an Odoo-sent status callback into the generic format."""
        return {
            "call_id": data.get("call_uuid") or data.get("call_id", ""),
            "status": data.get("status", ""),
            "from_number": data.get("from_number"),
            "to_number": data.get("to_number"),
            "duration": data.get("duration"),
            "extra": data,
        }

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        scope_id: int,
        workflow_run_id: int,
    ) -> None:
        """Handle the WebSocket connection from mod_audio_fork.

        mod_audio_fork starts streaming binary L16 audio immediately
        after the WebSocket handshake; there is no JSON preamble.

        ``scope_id`` is ``organization_id`` on current Dograh and
        ``user_id`` on <= 1.41.0 (pre organization-scoping refactor);
        both callers pass it positionally, and the pipeline entry point
        is introspected so this package runs on either base image.
        """
        import inspect

        from api.db import db_client
        from api.services.pipecat.run_pipeline import run_pipeline_telephony

        scope_kwarg = (
            "organization_id"
            if "organization_id"
            in inspect.signature(run_pipeline_telephony).parameters
            else "user_id"
        )

        workflow_run = await db_client.get_workflow_run(
            workflow_run_id, **{scope_kwarg: scope_id}
        )
        call_uuid = ""
        if workflow_run and workflow_run.gathered_context:
            call_uuid = workflow_run.gathered_context.get("call_id", "")

        logger.info(
            f"[FreeSWITCH] Starting pipeline for workflow_run {workflow_run_id}, "
            f"call={call_uuid}"
        )

        await run_pipeline_telephony(
            websocket,
            provider_name=self.PROVIDER_NAME,
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            call_id=call_uuid,
            transport_kwargs={"call_uuid": call_uuid},
            **{scope_kwarg: scope_id},
        )

    # ======== INBOUND CALL METHODS ========

    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        """Odoo marks its webhooks with an explicit provider field."""
        return webhook_data.get("provider") == cls.PROVIDER_NAME

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]) -> NormalizedInboundData:
        """Parse the Odoo inbound webhook into normalized format."""
        return NormalizedInboundData(
            provider=FreeswitchProvider.PROVIDER_NAME,
            call_id=webhook_data.get("call_id", ""),
            from_number=webhook_data.get("from_number", ""),
            to_number=webhook_data.get("to_number", ""),
            direction=webhook_data.get("direction", "inbound"),
            call_status=webhook_data.get("call_status", "ringing"),
            account_id=webhook_data.get("account_id"),
            raw_data=webhook_data,
        )

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        """Match the webhook's account_id against the stored credential."""
        return bool(
            webhook_account_id
            and config_data.get("account_id") == webhook_account_id
        )

    async def verify_inbound_signature(
        self,
        url: str,
        webhook_data: Dict[str, Any],
        headers: Dict[str, str],
        body: str = "",
    ) -> bool:
        """Verify the shared service token on inbound webhooks.

        Odoo sends ``Authorization: Bearer <service_token>``. Fail closed:
        a missing or mismatching token rejects the webhook.
        """
        if not self.service_token:
            return False
        authorization = ""
        for key, value in headers.items():
            if key.lower() == "authorization":
                authorization = value
                break
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not token:
            return False
        return hmac.compare_digest(token, self.service_token)

    async def start_inbound_stream(
        self,
        *,
        websocket_url: str,
        workflow_run_id: int,
        normalized_data,
        backend_endpoint: str,
    ):
        """Return the media WebSocket URL to the Odoo webhook caller.

        Odoo embeds the URL into the rendered dialplan's uuid_audio_fork
        action, so FreeSWITCH connects straight to the workflow run's
        media WebSocket.
        """
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {
                "websocket_url": websocket_url,
                "workflow_run_id": workflow_run_id,
            }
        )

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        """Generate a generic JSON error response."""
        from fastapi import Response

        return Response(
            content=json.dumps({"error": error_type, "message": message}),
            media_type="application/json",
        )

    @staticmethod
    def generate_validation_error_response(error_type) -> tuple:
        """Generate JSON error response for validation failures."""
        from fastapi import Response

        from api.errors.telephony_errors import TELEPHONY_ERROR_MESSAGES, TelephonyError

        message = TELEPHONY_ERROR_MESSAGES.get(
            error_type, TELEPHONY_ERROR_MESSAGES[TelephonyError.GENERAL_AUTH_FAILED]
        )

        return Response(
            content=json.dumps({"error": str(error_type), "message": message}),
            media_type="application/json",
        )

    # ======== CALL TRANSFER METHODS ========

    def supports_transfers(self) -> bool:
        """Transfers are not supported yet (needs Odoo-mediated leg + bridge)."""
        return False

    async def transfer_call(
        self,
        destination: str,
        transfer_id: str,
        conference_name: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """FreeSWITCH provider does not support call transfers yet."""
        raise NotImplementedError(
            "FreeSWITCH provider does not support call transfers"
        )
