# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from odoo.addons.connect.models.call import CALL_END_STATUSES

from .texml_response import VoiceResponse

logger = logging.getLogger(__name__)


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
        debug(self, 'On call action: %s' % params)
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

        # Core call processing
        call_id = self.process_call_event(channel, error_data)

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
                    message=params.get('ErrorMessage', ''),
                    warning=True,
                )

        return call_id

    @api.model
    def on_telnyx_vm_recording_status(self, params):
        debug(
            self.sudo(),
            'On recording status: %s' % json.dumps(params, indent=2),
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
        call.write({
            'telnyx_ai_assistant': assistant.id,
            'telnyx_ai_conversation_id': conversation_id,
            'telnyx_ai_last_sync_at': fields.Datetime.now(),
            'summary': summary or call.summary,
        })
        return recording

    @api.model
    def telnyx_apply_ai_insights(self, payload):
        conversation_id = (
            payload.get('conversation_id')
            or (payload.get('data') or {}).get('conversation_id')
        )
        if not conversation_id:
            return False
        insight_items = payload.get('insights') or (
            payload.get('data') or {}).get('insights') or []
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
