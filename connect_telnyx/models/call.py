# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from odoo.addons.connect.models.call import CALL_END_STATUSES

from .texml_response import VoiceResponse
from .utils import format_telnyx_debug_payload

logger = logging.getLogger(__name__)

# Telnyx ends an AI conversation with a reason instead of an error code, and
# a failed conversation still reports the call itself as completed. Without
# this mapping such a call is only a suspiciously short entry in the history.
AI_CONVERSATION_ERROR_MESSAGES = {
    'greeting_error': (
        'The AI assistant could not generate its greeting audio, so the call '
        'ended immediately. Telnyx usually rejects the configured voice or a '
        'speaking speed the voice does not support.'
    ),
}


class Call(models.Model):
    _inherit = 'connect.call'

    telnyx_ai_assistant = fields.Many2one(
        'connect.telnyx.ai_assistant', string='Telnyx AI Assistant',
        ondelete='set null', readonly=True,
    )
    telnyx_ai_conversation_id = fields.Char(
        string='Telnyx AI Conversation', readonly=True, copy=False, index=True,
    )
    telnyx_ai_last_sync_at = fields.Datetime(readonly=True, copy=False)

    @api.model
    def telnyx_on_call_action(self, params):
        debug(
            self,
            'On call action: %s' % format_telnyx_debug_payload(params),
        )
        response = VoiceResponse()
        response.hangup()
        return response.to_xml()

    telnyx_call_sid = fields.Char(
        string='Telnyx Call SID', readonly=True,
        help='Telnyx TeXML CallSid for fetching cost information'
    )
    telnyx_price = fields.Float(
        string='Telnyx Call Price', readonly=True, digits=(10, 3)
    )
    telnyx_price_unit = fields.Char(
        string='Telnyx Price Unit', readonly=True,
        help='The currency unit for call price (e.g., USD)'
    )
    telnyx_is_price_fetched = fields.Boolean(
        string='Telnyx Price Fetched', default=False, readonly=True,
        help='Indicates if call price has been fetched from Telnyx detail records'
    )

    @api.model
    def on_telnyx_call_status(self, params):
        """Telnyx TeXML webhook adapter: map params, delegate to core."""
        self = self.sudo()
        # Channel processing via Telnyx adapter → core
        channel = self.env['connect.channel'].on_telnyx_call_status(params)
        if not channel:
            logger.error('No channel returned from on_telnyx_call_status!')
            return False

        # Extract Telnyx-specific error data
        error_data = None
        if params.get('ErrorCode'):
            error_data = {
                'error_code': params.get('ErrorCode'),
                'error_message': params.get('ErrorMessage'),
            }
        else:
            error_data = self._telnyx_ai_conversation_error(params)

        # Core call processing
        call_id = self.process_call_event(channel, error_data)

        conversation_id = params.get('ConversationId')
        if channel.call and conversation_id:
            channel.call.write({
                'telnyx_ai_conversation_id': conversation_id,
                'telnyx_ai_last_sync_at': fields.Datetime.now(),
            })

        # Desktop notification for incoming SIP calls
        if (channel.call
                and channel.call.direction == 'incoming'
                and params.get('CallStatus') == 'initiated'
                and params.get('To', '').startswith('sip:')):
            channel.telnyx_connect_notify()

        # Cost fetching on call end
        if params.get('CallStatus') in CALL_END_STATUSES:
            if self.env['connect.settings'].sudo().get_param(
                'telnyx_fetch_call_prices'
            ):
                self.save_telnyx_call_price(channel.call, params)

        # Error notification to caller
        if error_data and channel.call:
            user = channel.caller_user or channel.call.caller_user
            if channel.call.direction == 'outgoing' and user:
                self.env['connect.settings'].connect_notify(
                    notify_uid=user.id,
                    title="Call Error",
                    message=error_data.get('error_message') or '',
                    warning=True,
                )

        return call_id

    @api.model
    def _telnyx_ai_conversation_error(self, params):
        """Turn a failed AI conversation into call error data.

        Telnyx reports the outcome of an assistant conversation as
        `CallStatus=conversation_ended` with a `Reason`, and reports the
        call leg itself as a normal `completed` afterwards. Only failure
        reasons become call errors; a caller who simply hung up is not an
        error. The reason list is not documented, so unknown failures are
        recognized by their name and reported verbatim rather than
        silently dropped.
        """
        if params.get('CallStatus') != 'conversation_ended':
            return None
        reason = (params.get('Reason') or '').strip()
        if not reason:
            return None
        if not (reason.endswith('_error') or reason.startswith('error')
                or 'fail' in reason):
            return None
        message = AI_CONVERSATION_ERROR_MESSAGES.get(
            reason,
            "The AI conversation ended with '{}'.".format(reason),
        )
        voice = ' '.join(part for part in (
            params.get('TtsProvider'),
            params.get('TtsModelId'),
            params.get('TtsVoiceId'),
        ) if part)
        if voice:
            message = '{} Voice: {}.'.format(message, voice)
        return {'error_code': reason, 'error_message': message}

    @api.model
    def on_telnyx_vm_recording_status(self, params):
        debug(
            self.sudo(),
            'On recording status: %s' % format_telnyx_debug_payload(params),
        )
        channel = self.sudo().env['connect.channel'].search(
            [('sid', '=', params['CallSid'])]
        )
        if channel and channel.call:
            channel.call.write(
                {
                    'voicemail_url': params.get('RecordingUrl'),
                    'voicemail_duration': int(
                        params.get('RecordingDuration')
                    ),
                }
            )
        return True

    def save_telnyx_call_price(self, call, params):
        """Mark call as needing cost fetch (processed by the cron job)."""
        try:
            call_sid = params.get('CallSid')
            if not call_sid:
                debug(
                    self,
                    'No CallSid in webhook params, cannot store for price fetching',
                )
                return
            call.write(
                {
                    'telnyx_call_sid': call_sid,
                    'telnyx_is_price_fetched': False,
                }
            )
            debug(
                self,
                'Marked call {} (CallSid: {}) for price fetching by cron job'.format(
                    call.id, call_sid
                ),
            )
        except Exception as e:
            logger.error('Error in save_telnyx_call_price: %s', e)

    def _fetch_telnyx_call_price(self, call, call_sid):
        """Fetch call cost from Telnyx detail records (best effort,
        ADR-032). TeXML status callbacks carry no cost data."""
        try:
            client = self.env['connect.settings'].get_telnyx_client()
            records = client.detail_records.list(
                filter={
                    'record_type': 'voice',
                    'leg_id': call_sid,
                },
                page_size=1,
            )
            for record in records:
                cost = getattr(record, 'cost', None)
                currency = getattr(record, 'currency', None) or 'USD'
                if cost in (None, ''):
                    continue
                try:
                    price_value = round(abs(float(cost)), 3)
                except ValueError as e:
                    logger.error(
                        'Error converting call cost %s to float: %s', cost, e)
                    return False
                call.write(
                    {
                        'telnyx_price': price_value,
                        'telnyx_price_unit': currency,
                    }
                )
                debug(
                    self,
                    'Saved call cost: {:.3f} {} for call {}'.format(
                        price_value, currency, call.id
                    ),
                )
                return True
            debug(
                self,
                'Call cost not yet available for {}, will be available later'.format(
                    call_sid
                ),
            )
        except Exception as e:
            logger.error(
                'Error fetching call cost from detail records for %s: %s',
                call_sid, e
            )
        return False

    @api.model
    def telnyx_fetch_call_prices_batch(self):
        """Cron job method to fetch costs for calls that don't have them yet"""
        if not self.env['connect.settings'].sudo().get_param(
            'telnyx_fetch_call_prices'
        ):
            debug(self, 'Telnyx call price fetching is disabled in settings')
            return
        calls_to_fetch = self.search(
            [
                ('telnyx_is_price_fetched', '=', False),
                ('telnyx_call_sid', '!=', False),
                ('status', 'in', CALL_END_STATUSES),
                (
                    'create_date',
                    '>=',
                    fields.Datetime.now() - timedelta(days=30),
                ),
            ]
        )
        debug(
            self,
            'Found {} calls needing cost fetch'.format(len(calls_to_fetch)),
        )
        for call in calls_to_fetch:
            try:
                success = self._fetch_telnyx_call_price(call, call.telnyx_call_sid)
                if success:
                    call.write({'telnyx_is_price_fetched': True})
            except Exception as e:
                logger.error(
                    'Error fetching cost for call %s: %s', call.id, e
                )
        debug(self, 'Batch cost fetch completed')

    @api.model
    def telnyx_link_ai_conversation(self, payload):
        """Link the assistant initialization event to the TeXML call ledger."""
        self = self.sudo()
        assistant_sid = payload.get('assistant_id')
        call_control_id = payload.get('call_control_id')
        conversation_id = (
            payload.get('telnyx_conversation_id')
            or payload.get('conversation_id')
        )
        assistant = self.env['connect.telnyx.ai_assistant'].search(
            [('sid', '=', assistant_sid)], limit=1)
        channel = self.env['connect.channel'].search(
            [('sid', '=', call_control_id)], limit=1)
        call = channel.call
        if call:
            call.write({
                'telnyx_ai_assistant': assistant.id,
                'telnyx_ai_conversation_id': conversation_id or False,
                'telnyx_ai_last_sync_at': fields.Datetime.now(),
            })
        return call

    @api.model
    def _telnyx_ai_transcript(self, messages):
        lines = []
        for message in messages:
            role = (message.get('role') or 'unknown').upper()
            text = message.get('text') or message.get('content') or ''
            if isinstance(text, list):
                text = ' '.join(
                    item.get('text', '') if isinstance(item, dict) else str(item)
                    for item in text
                )
            if text:
                lines.append('{}: {}'.format(role, text))
        return '\n'.join(lines)

    @api.model
    def _telnyx_ai_summary(self, insights):
        for batch in reversed(insights or []):
            for insight in batch.get('conversation_insights') or []:
                result = insight.get('result')
                if result:
                    return result if isinstance(result, str) else json.dumps(
                        result, ensure_ascii=False)
        return ''

    @api.model
    def _telnyx_find_ai_call(self, conversation):
        metadata = conversation.get('metadata') or {}
        conversation_id = conversation.get('id')
        call = self.sudo().search(
            [('telnyx_ai_conversation_id', '=', conversation_id)], limit=1)
        if call:
            return call
        call_control_id = metadata.get('call_control_id')
        if call_control_id:
            channel = self.env['connect.channel'].sudo().search(
                [('sid', '=', call_control_id)], limit=1)
            if channel.call:
                return channel.call
        agent_target = metadata.get('telnyx_agent_target')
        end_user = metadata.get('telnyx_end_user_target')
        if agent_target and end_user:
            return self.sudo().search([
                '|',
                '&', ('called', '=', agent_target), ('caller', '=', end_user),
                '&', ('caller', '=', agent_target), ('called', '=', end_user),
            ], order='create_date desc', limit=1)
        return self

    @api.model
    def telnyx_sync_ai_conversation(self, conversation, summary=None):
        settings = self.env['connect.settings']
        conversation_id = conversation.get('id')
        if not conversation_id:
            return False
        call = self._telnyx_find_ai_call(conversation)
        if not call:
            return False
        metadata = conversation.get('metadata') or {}
        assistant = self.env['connect.telnyx.ai_assistant'].sudo().search(
            [('sid', '=', metadata.get('assistant_id'))], limit=1)
        messages_response = settings.telnyx_api_request(
            'GET', 'ai/conversations/{}/messages'.format(conversation_id)
        )
        messages = messages_response.get('data', messages_response)
        if not isinstance(messages, list):
            messages = []
        if summary is None:
            insights_response = settings.telnyx_api_request(
                'GET',
                'ai/conversations/{}/conversations-insights'.format(
                    conversation_id),
            )
            insights = insights_response.get('data', insights_response)
            summary = self._telnyx_ai_summary(
                insights if isinstance(insights, list) else []
            )
        transcript = self._telnyx_ai_transcript(messages)
        channel = call.channels.filtered(
            lambda rec: rec.sid == metadata.get('call_control_id'))[:1]
        vals = {
            'sid': conversation_id,
            'call_sid': metadata.get('call_control_id') or '',
            'call': call.id,
            'channel': channel.id,
            'partner': call.partner.id,
            'caller_number': call.caller,
            'called_number': call.called,
            'source': 'telnyx-ai',
            'status': 'completed',
            'transcript': transcript,
            'summary': summary or '',
            'transcription_pending': False,
        }
        recording = self.env['connect.recording'].sudo().search(
            [('sid', '=', conversation_id), ('source', '=', 'telnyx-ai')],
            limit=1,
        )
        if recording:
            recording.with_context(skip_transcription=True).write(vals)
        else:
            recording = self.env['connect.recording'].sudo().with_context(
                skip_transcription=True
            ).create(vals)
        call_control_id = metadata.get('call_control_id') or channel.sid
        try:
            recording.telnyx_attach_ai_audio(call_control_id)
        except Exception:
            logger.exception(
                'Cannot attach Telnyx AI audio for conversation %s',
                conversation_id,
            )
        call.write({
            'telnyx_ai_assistant': assistant.id,
            'telnyx_ai_conversation_id': conversation_id,
            'telnyx_ai_last_sync_at': fields.Datetime.now(),
            'summary': summary or call.summary,
        })
        return recording

    @api.model
    def telnyx_apply_ai_insights(self, payload):
        data = payload.get('data') or payload
        event_payload = data.get('payload') or data
        conversation_id = (
            event_payload.get('conversation_id')
            or data.get('conversation_id')
            or payload.get('conversation_id')
        )
        call_control_id = event_payload.get('call_control_id')
        if not conversation_id and call_control_id:
            channel = self.env['connect.channel'].sudo().search(
                [('sid', '=', call_control_id)], limit=1)
            conversation_id = channel.call.telnyx_ai_conversation_id
        if not conversation_id:
            logger.warning(
                'Cannot match Telnyx AI insight event to a conversation '
                '(call_control_id=%s).', call_control_id or '',
            )
            return False
        insight_items = (
            event_payload.get('results')
            or event_payload.get('insights')
            or data.get('insights')
            or payload.get('insights')
            or []
        )
        summary = ''
        for item in insight_items:
            if item.get('result'):
                result = item['result']
                summary = result if isinstance(result, str) else json.dumps(
                    result, ensure_ascii=False)
                break
        conversation_response = self.env[
            'connect.settings'
        ].telnyx_api_request(
            'GET', 'ai/conversations/{}'.format(conversation_id)
        )
        conversation = conversation_response.get('data', conversation_response)
        return self.telnyx_sync_ai_conversation(
            conversation, summary=summary or None)

    @api.model
    def telnyx_sync_ai_conversations_batch(self, limit=50):
        settings = self.env['connect.settings'].sudo()
        if not settings.get_param('telnyx_api_key'):
            return False
        response = settings.telnyx_api_request(
            'GET', 'ai/conversations', params={
                'metadata->telnyx_conversation_channel': 'eq.phone_call',
                'limit': limit,
                'order': 'last_message_at.desc',
            })
        conversations = response.get('data', response)
        if not isinstance(conversations, list):
            return False
        for conversation in conversations:
            try:
                self.telnyx_sync_ai_conversation(conversation)
            except Exception:
                logger.exception(
                    'Cannot sync Telnyx AI conversation %s',
                    conversation.get('id'),
                )
        return True
