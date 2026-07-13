import logging
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import WebSocket

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from .odoo_client import OdooClient
from .serializer import AudioForkFrameSerializer

logger = logging.getLogger(__name__)


@dataclass
class CallState:
    call_uuid: str
    agent_id: int
    odoo: OdooClient
    transferred: bool = False
    hangup_sent: bool = False

    async def hangup_unless_transferred(self):
        if self.transferred or self.hangup_sent:
            return
        self.hangup_sent = True
        try:
            await self.odoo.hangup(self.call_uuid)
        except Exception:
            logger.exception('Could not hang up %s', self.call_uuid)


def _language(code: str) -> Language:
    try:
        return Language(code)
    except ValueError:
        return Language.EN


def _build_stt(config: dict[str, Any]):
    item = config['stt']
    language = _language(config['language'])
    if item['provider'] == 'openai':
        return OpenAISTTService(
            api_key=item['api_key'],
            settings=OpenAISTTService.Settings(
                model=item['model'], language=language,
            ),
        )
    if item['provider'] == 'deepgram':
        return DeepgramSTTService(
            api_key=item['api_key'], sample_rate=16000,
            settings=DeepgramSTTService.Settings(
                model=item['model'], language=language,
                smart_format=False, endpointing=300,
                utterance_end_ms=1000,
            ),
        )
    raise ValueError('Unsupported STT provider: {}'.format(item['provider']))


def _build_llm(config: dict[str, Any]):
    item = config['llm']
    instruction = config['system_prompt']
    if config.get('transfer', {}).get('enabled'):
        instruction += '\n\n' + config['transfer'].get('prompt', '')
        instruction += '\nUse transfer_to_human when a transfer is appropriate.'
    instruction += '\nUse end_call when the conversation is explicitly finished.'
    if item['provider'] == 'openai':
        return OpenAILLMService(
            api_key=item['api_key'],
            settings=OpenAILLMService.Settings(
                model=item['model'], system_instruction=instruction,
            ),
        )
    if item['provider'] == 'anthropic':
        return AnthropicLLMService(
            api_key=item['api_key'],
            settings=AnthropicLLMService.Settings(
                model=item['model'], system_instruction=instruction,
            ),
        )
    raise ValueError('Unsupported LLM provider: {}'.format(item['provider']))


def _build_tts(config: dict[str, Any]):
    item = config['tts']
    language = _language(config['language'])
    if item['provider'] == 'openai':
        return OpenAITTSService(
            api_key=item['api_key'],
            settings=OpenAITTSService.Settings(
                model=item['model'], voice=item['voice'], language=language,
            ),
        )
    if item['provider'] == 'elevenlabs':
        return ElevenLabsTTSService(
            api_key=item['api_key'], sample_rate=16000,
            settings=ElevenLabsTTSService.Settings(
                model=item['model'], voice=item['voice'], language=language,
            ),
        )
    if item['provider'] == 'deepgram':
        return DeepgramTTSService(
            api_key=item['api_key'], sample_rate=16000,
            settings=DeepgramTTSService.Settings(
                model=item['model'], voice=item['voice'], language=language,
            ),
        )
    raise ValueError('Unsupported TTS provider: {}'.format(item['provider']))


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(
            str(part.get('text', '')) for part in content
            if isinstance(part, dict) and part.get('type') == 'text'
        ).strip()
    return ''


def _transcript(messages: list[Any]) -> str:
    lines = []
    labels = {'user': 'Caller', 'assistant': 'Agent'}
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in labels:
            continue
        text = _content_text(message.get('content')).strip()
        if text:
            lines.append('{}: {}'.format(labels[message['role']], text))
    return '\n'.join(lines)


async def _summarize(config: dict[str, Any], transcript: str) -> str:
    if not transcript:
        return ''
    prompt = 'Summarize this phone call concisely. Include outcomes and next steps.\n\n' + transcript
    item = config['llm']
    async with httpx.AsyncClient(timeout=30.0) as client:
        if item['provider'] == 'openai':
            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': 'Bearer {}'.format(item['api_key'])},
                json={
                    'model': item['model'],
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.2,
                },
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        response = await client.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': item['api_key'],
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': item['model'], 'max_tokens': 700,
                'messages': [{'role': 'user', 'content': prompt}],
            },
        )
        response.raise_for_status()
        return ''.join(
            part.get('text', '') for part in response.json().get('content', [])
            if part.get('type') == 'text'
        ).strip()


async def run_call(
    websocket: WebSocket,
    call_uuid: str,
    agent_id: int,
    odoo: OdooClient,
):
    config = await odoo.get_agent(agent_id)
    for service_name in ('stt', 'llm', 'tts'):
        if not config[service_name].get('api_key'):
            raise RuntimeError('{} provider API key is not configured'.format(service_name))

    state = CallState(call_uuid=call_uuid, agent_id=agent_id, odoo=odoo)
    serializer = AudioForkFrameSerializer(on_disconnect=state.hangup_unless_transferred)
    transport = FastAPIWebsocketTransport(
        websocket,
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            audio_out_channels=1,
            audio_out_end_silence_secs=0,
            serializer=serializer,
            session_timeout=config.get('max_duration') or 1800,
            fixed_audio_packet_size=640,
            allowed_origins=[],
        ),
    )
    stt = _build_stt(config)
    llm = _build_llm(config)
    tts = _build_tts(config)

    async def transfer_to_human(params: FunctionCallParams, reason: str = ''):
        """Transfer the current caller to a human agent.

        Args:
            reason: Short reason why the caller needs a human.
        """
        if not config.get('transfer', {}).get('enabled'):
            await params.result_callback({'ok': False, 'error': 'transfer_not_configured'})
            return
        await state.odoo.transfer(state.call_uuid, state.agent_id)
        state.transferred = True
        await params.result_callback({'ok': True, 'reason': reason})
        await params.pipeline_worker.queue_frames([EndFrame()])

    async def end_call(params: FunctionCallParams):
        """End the call after the caller and agent have finished talking."""
        await state.hangup_unless_transferred()
        await params.result_callback({'ok': True})
        await params.pipeline_worker.queue_frames([EndFrame()])

    tools = [end_call]
    if config.get('transfer', {}).get('enabled'):
        tools.append(transfer_to_human)
    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline([
        transport.input(), stt, user_aggregator, llm, tts,
        transport.output(), assistant_aggregator,
    ])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=config.get('max_duration') or 1800,
    )

    @transport.event_handler('on_client_connected')
    async def on_client_connected(_transport, _client):
        greeting = (config.get('greeting') or '').strip()
        if greeting:
            context.add_message({'role': 'assistant', 'content': greeting})
            await worker.queue_frames([TTSSpeakFrame(greeting)])
        else:
            context.add_message({
                'role': 'developer',
                'content': 'Greet the caller briefly and ask how you can help.',
            })
            await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler('on_client_disconnected')
    async def on_client_disconnected(_transport, _client):
        await worker.cancel(reason='FreeSWITCH media WebSocket disconnected')

    @transport.event_handler('on_session_timeout')
    async def on_session_timeout(_transport, _client):
        await worker.queue_frames([EndFrame()])

    runner = WorkerRunner(handle_sigint=False)
    try:
        await runner.add_workers(worker)
        await runner.run()
    finally:
        transcript = _transcript(context.messages)
        try:
            summary = await _summarize(config, transcript)
        except Exception:
            logger.exception('Could not summarize call %s', call_uuid)
            summary = ''
        try:
            await odoo.post_call_result(call_uuid, transcript, summary)
        except Exception:
            logger.exception('Could not persist call result for %s', call_uuid)
