"""FreeSWITCH (mod_audio_fork) transport factory."""

from fastapi import WebSocket
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.audio_mixer import build_audio_out_mixer
from api.services.pipecat.transport_params import realtime_param_overrides
from api.services.telephony.factory import load_credentials_for_transport

from .serializers import FreeswitchFrameSerializer
from .strategies import OdooHangupStrategy


async def create_transport(
    websocket: WebSocket,
    workflow_run_id: int,
    audio_config: AudioConfig,
    organization_id: int,
    *,
    ambient_noise_config: dict | None = None,
    telephony_configuration_id: int | None = None,
    is_realtime: bool = False,
    call_uuid: str,
):
    """Create a transport for FreeSWITCH mod_audio_fork connections."""
    config = await load_credentials_for_transport(
        organization_id, telephony_configuration_id, expected_provider="freeswitch"
    )

    odoo_url = config.get("odoo_url")
    service_token = config.get("service_token")

    if not odoo_url or not service_token:
        raise ValueError(
            f"Incomplete FreeSWITCH configuration for organization "
            f"{organization_id}. Required: odoo_url, service_token"
        )

    serializer = FreeswitchFrameSerializer(
        call_uuid=call_uuid,
        odoo_url=odoo_url,
        service_token=service_token,
        hangup_strategy=OdooHangupStrategy(),
        params=FreeswitchFrameSerializer.InputParams(
            freeswitch_sample_rate=audio_config.transport_in_sample_rate,
            sample_rate=audio_config.pipeline_sample_rate,
        ),
    )

    mixer = await build_audio_out_mixer(
        audio_config.transport_out_sample_rate, ambient_noise_config
    )

    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=audio_config.transport_in_sample_rate,
            audio_out_sample_rate=audio_config.transport_out_sample_rate,
            audio_out_mixer=mixer,
            serializer=serializer,
            **realtime_param_overrides(is_realtime),
        ),
    )
