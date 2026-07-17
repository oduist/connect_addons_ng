"""FreeSWITCH mod_audio_fork frame serializer.

Wire protocol (W1ck3dZA mod_audio_fork, bidirectional streaming mode):

- FreeSWITCH -> Dograh: binary WebSocket frames of raw L16 PCM mono at
  the rate given in the ``uuid_audio_fork`` dialplan arguments (16 kHz).
- Dograh -> FreeSWITCH: binary frames of raw L16 PCM at the
  ``bidirectionalAudio_stream_samplerate`` (16 kHz), plus JSON text
  frames: ``{"type": "killAudio"}`` flushes the module's playback
  buffer (barge-in).

There is no JSON wrapper or base64 encoding around audio in either
direction. On EndFrame/CancelFrame the serializer delegates the channel
hangup to a strategy (Odoo owns FreeSWITCH call control).
"""

import json

from loguru import logger

from pipecat.audio.utils import create_stream_resampler
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    StartFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.serializers.call_strategies import HangupStrategy


class FreeswitchFrameSerializer(FrameSerializer):
    """Serializer for FreeSWITCH mod_audio_fork WebSocket audio streaming."""

    class InputParams(FrameSerializer.InputParams):
        """Configuration parameters for FreeswitchFrameSerializer.

        Parameters:
            freeswitch_sample_rate: Wire rate used by mod_audio_fork (16 kHz).
            sample_rate: Optional override for the pipeline input sample rate.
            auto_hang_up: Whether to terminate the channel on EndFrame.
        """

        freeswitch_sample_rate: int = 16000
        sample_rate: int | None = None
        auto_hang_up: bool = True

    def __init__(
        self,
        call_uuid: str,
        odoo_url: str,
        service_token: str,
        hangup_strategy: "HangupStrategy | None" = None,
        params: InputParams | None = None,
    ):
        """Initialize the FreeswitchFrameSerializer.

        Args:
            call_uuid: FreeSWITCH channel UUID of the caller leg.
            odoo_url: Odoo base URL for call-control callbacks.
            service_token: Bearer token for Odoo /dograh/api/* endpoints.
            hangup_strategy: Strategy executed on EndFrame/CancelFrame.
            params: Configuration parameters.
        """
        params = params or FreeswitchFrameSerializer.InputParams()
        super().__init__(params)
        self._params: FreeswitchFrameSerializer.InputParams = params

        self._call_uuid = call_uuid
        self._odoo_url = odoo_url
        self._service_token = service_token
        self._hangup_strategy = hangup_strategy

        self._wire_rate = self._params.freeswitch_sample_rate
        self._sample_rate = 0  # Pipeline input rate, set in setup()

        self._input_resampler = create_stream_resampler()
        self._output_resampler = create_stream_resampler()
        self._hangup_attempted = False

    async def setup(self, frame: StartFrame):
        """Set up the serializer with pipeline configuration."""
        self._sample_rate = self._params.sample_rate or frame.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        """Serialize a Pipecat frame to the mod_audio_fork wire format."""
        if isinstance(frame, (EndFrame, CancelFrame)):
            if self._params.auto_hang_up and not self._hangup_attempted:
                self._hangup_attempted = True
                if self._hangup_strategy:
                    context = {
                        "call_uuid": self._call_uuid,
                        "odoo_url": self._odoo_url,
                        "service_token": self._service_token,
                    }
                    success = await self._hangup_strategy.execute_hangup(context)
                    if not success:
                        logger.error(
                            f"Hangup strategy failed for call {self._call_uuid}"
                        )
                else:
                    logger.warning(
                        f"No hangup strategy configured for call {self._call_uuid}"
                    )
            return None
        elif isinstance(frame, InterruptionFrame):
            # Flush mod_audio_fork's playback buffer for barge-in.
            return json.dumps({"type": "killAudio"})
        elif isinstance(frame, AudioRawFrame):
            audio = await self._output_resampler.resample(
                frame.audio, frame.sample_rate, self._wire_rate
            )
            if not audio:
                return None
            # mod_audio_fork expects raw binary L16 bytes.
            return bytes(audio)

        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        """Deserialize mod_audio_fork WebSocket data to Pipecat frames."""
        if isinstance(data, bytes):
            audio = await self._input_resampler.resample(
                data, self._wire_rate, self._sample_rate
            )
            if not audio:
                return None
            return InputAudioRawFrame(
                audio=bytes(audio),
                num_channels=1,  # mod_audio_fork is attached in mono mode
                sample_rate=self._sample_rate,
            )
        # Text message = JSON control event from the module.
        try:
            message = json.loads(data)
            event = message.get("type") or message.get("event")
            logger.debug(f"mod_audio_fork event: {event} - {message}")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON message from mod_audio_fork: {data}")
        return None
