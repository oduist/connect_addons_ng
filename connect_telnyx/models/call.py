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
