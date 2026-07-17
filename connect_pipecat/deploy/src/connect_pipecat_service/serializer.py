import json
from collections.abc import Awaitable, Callable

from loguru import logger

from pipecat.audio.utils import create_stream_resampler
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer


class AudioForkFrameSerializer(FrameSerializer):
    """Translate Pipecat frames to W1ck3dZA mod_audio_fork's wire protocol."""

    class InputParams(FrameSerializer.InputParams):
        audio_fork_sample_rate: int = 16000
        sample_rate: int | None = None

    def __init__(
        self,
        params: InputParams | None = None,
        on_disconnect: Callable[[], Awaitable[None]] | None = None,
    ):
        params = params or self.InputParams()
        super().__init__(params)
        self._params = params
        self._wire_rate = params.audio_fork_sample_rate
        self._pipeline_rate = 0
        self._input_resampler = create_stream_resampler(
            clear_after_secs=params.resampler_clear_after_secs,
        )
        self._output_resampler = create_stream_resampler(
            clear_after_secs=params.resampler_clear_after_secs,
        )
        self._on_disconnect = on_disconnect
        self._disconnect_notified = False

    async def setup(self, frame: StartFrame):
        self._pipeline_rate = self._params.sample_rate or frame.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, InterruptionFrame):
            logger.info('Sending killAudio to FreeSWITCH for caller barge-in')
            return json.dumps({'type': 'killAudio'})
        if isinstance(frame, AudioRawFrame):
            audio = await self._output_resampler.resample(
                frame.audio, frame.sample_rate, self._wire_rate,
            )
            return bytes(audio) if audio else None
        if isinstance(frame, (EndFrame, CancelFrame)):
            if self._on_disconnect and not self._disconnect_notified:
                self._disconnect_notified = True
                await self._on_disconnect()
            return json.dumps({'type': 'disconnect'})
        if isinstance(frame, (OutputTransportMessageFrame,
                              OutputTransportMessageUrgentFrame)):
            if not self.should_ignore_frame(frame):
                return json.dumps(frame.message)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            audio = await self._input_resampler.resample(
                data, self._wire_rate, self._pipeline_rate,
            )
            if not audio:
                return None
            return InputAudioRawFrame(
                audio=bytes(audio), sample_rate=self._pipeline_rate,
                num_channels=1,
            )
        try:
            message = json.loads(data)
        except (TypeError, json.JSONDecodeError):
            logger.warning('Ignoring invalid mod_audio_fork text frame')
            return None
        message_type = message.get('type') or message.get('event')
        if message_type in ('mark', 'clearMarks', 'connect'):
            logger.debug('mod_audio_fork event: {}', message_type)
        else:
            logger.debug('Ignoring mod_audio_fork message: {}', message_type)
        return None
