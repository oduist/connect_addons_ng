"""FreeSWITCH-specific call operation strategies.

FreeSWITCH call control belongs to the Odoo instance (mod_xml_rpc
credentials never leave it), so strategies call Odoo's Bearer-token
control endpoints instead of talking to FreeSWITCH directly.
"""

from typing import Any, Dict

from loguru import logger
from pipecat.serializers.call_strategies import HangupStrategy


class OdooHangupStrategy(HangupStrategy):
    """Hang up the FreeSWITCH channel through Odoo (uuid_kill)."""

    async def execute_hangup(self, context: Dict[str, Any]) -> bool:
        """POST /dograh/api/hangup on the configured Odoo instance."""
        try:
            import aiohttp

            call_uuid = context.get("call_uuid")
            odoo_url = (context.get("odoo_url") or "").rstrip("/")
            service_token = context.get("service_token")

            if not call_uuid or not odoo_url or not service_token:
                logger.warning(
                    "Cannot hang up FreeSWITCH call: missing "
                    "call_uuid, odoo_url or service_token"
                )
                return False

            endpoint = f"{odoo_url}/dograh/api/hangup"
            headers = {"Authorization": f"Bearer {service_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json={"call_uuid": call_uuid},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status in (200, 204):
                        logger.info(f"Hung up FreeSWITCH call {call_uuid} via Odoo")
                        return True
                    elif response.status == 404:
                        # Channel already gone (caller hung up first).
                        logger.debug(f"FreeSWITCH call {call_uuid} already terminated")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to hang up FreeSWITCH call {call_uuid}: "
                            f"HTTP {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.exception(f"Failed to hang up FreeSWITCH call: {e}")
            return False
