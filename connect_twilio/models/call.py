# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

CALL_END_STATUSES = ['completed', 'busy', 'failed', 'no-answer', 'canceled']
IGNORE_ERROR_CODES = ['32009']


class Call(models.Model):
    _inherit = 'connect.call'

    call_sid = fields.Char(
        string='Twilio Call SID', readonly=True,
        help='Twilio CallSid for fetching price information'
    )
    price = fields.Float(
        string='Call Price', readonly=True, digits=(10, 3)
    )
    price_unit = fields.Char(
        string='Price Unit', readonly=True,
        help='The currency unit for call price (e.g., USD)'
    )
    price_currency = fields.Char(
        string='Price Currency', readonly=True, default='USD'
    )
    is_price_fetched = fields.Boolean(
        string='Price Fetched', default=False, readonly=True,
        help='Indicates if call price has been fetched from Twilio API'
    )

    @api.model
    def on_call_status(self, params):
        self = self.sudo()
        # Create channel
        channel = self.env['connect.channel'].on_call_status(params)
        if not channel:
            logger.error('No channel returned from on_call_status!')
            return False
        if not channel.parent_channel and not channel.call:
            # Create a new call.
            if channel.technical_direction == 'outbound-api':
                debug(self, 'outbound-api channel direction.')
                direction = 'outgoing'
            elif (
                channel.technical_direction == 'inbound'
                and channel.caller_pbx_user
            ):
                debug(self, 'inbound channel direction with caller_pbx_user.')
                direction = 'outgoing'
            elif (
                channel.technical_direction == 'inbound'
                and not channel.caller_pbx_user
            ):
                debug(
                    self,
                    'inbound channel direction without caller_pbx_user. '
                    'Assuming DID call.',
                )
                direction = 'incoming'
            else:
                debug(self, 'Setting default call direction to outgoing.')
                direction = 'outgoing'
            call = self.with_context(tracking_disable=True).create(
                {
                    'partner': channel.partner.id,
                    'called': channel.called_number,
                    'caller': channel.caller_number,
                    'status': channel.status,
                    'caller_pbx_user': channel.caller_pbx_user.id,
                    'caller_user': channel.caller_user.id,
                    'direction': direction,
                    'call_type': channel.call_type or 'phone',
                }
            )
            channel.call = call
        elif channel.parent_channel and channel.parent_channel.call:
            # Secondary channel, assign the call from the parent.
            channel.call = channel.parent_channel.call
            if (
                channel.caller_pbx_user
                and channel.parent_channel.called_pbx_user
            ):
                channel.call.direction = 'internal'
            elif (
                channel.called_pbx_user
                and channel.parent_channel.caller_pbx_user
            ):
                channel.call.direction = 'internal'
        # Set call status from the last channel
        channel.call.status = channel.call.channels.sorted(
            key='id', reverse=True
        )[0].status
        # Set call duration from the first channel
        channel.call.duration = channel.call.channels.sorted(
            key='id', reverse=False
        )[0].duration
        # Set called from 2nd call leg for click2call external calls.
        if channel.parent_channel.technical_direction == 'outbound-api':
            channel.call.called = channel.called_number
        # Set called users (avoid duplicates)
        if (
            channel.called_user
            and channel.called_user not in channel.call.called_users
        ):
            channel.call.called_users = [(4, channel.called_user.id)]
        if (
            channel.called_pbx_user
            and channel.called_pbx_user not in channel.call.called_pbx_users
        ):
            channel.call.called_pbx_users = [(4, channel.called_pbx_user.id)]
        # Set the answered user
        if channel.call.status == 'completed':
            answered_user = channel.call.channels[0].called_pbx_user
            channel.call.answered_pbx_user = answered_user
            channel.call.answered_user = answered_user.user
        # Check if we need to set a partner from child channel
        if not channel.call.partner and channel.partner:
            channel.call.partner = channel.partner
        if (
            channel.call.direction == 'incoming'
            and params.get('CallStatus') == 'initiated'
            and params.get('To', '').startswith('sip:')
        ):
            # Desktop notification only for SIP calls.
            channel.connect_notify()
        # Register call when ALL channels have ended.
        if params.get('CallStatus') in CALL_END_STATUSES:
            all_channels_ended = all(
                ch.status in CALL_END_STATUSES
                for ch in channel.call.channels
            )
            if all_channels_ended:
                self.register_call(channel, params)
            # Fetch call price if enabled in settings
            if self.env['connect.settings'].sudo().get_param(
                'fetch_call_prices'
            ):
                self.save_call_price(channel.call, params)
        # Reload call view
        self.env['connect.settings'].connect_reload_view('connect.call')
        if params.get('ErrorCode') and params.get(
            'ErrorCode'
        ) not in IGNORE_ERROR_CODES:
            channel.call.update(
                {
                    'has_error': True,
                    'error_code': params.get('ErrorCode'),
                    'error_message': params.get('ErrorMessage'),
                }
            )
            # Notify caller user on errors on outgoing calls.
            user = channel.caller_user or channel.call.caller_user
            if channel.call.direction == 'outgoing' and user:
                if 'No International Permission' in params.get(
                    'ErrorMessage', ''
                ):
                    message_text = re.sub(
                        r'(https?://\S+)',
                        r'<strong><a target="_blank" href="\1">'
                        r'your Twilio Console</a></strong>',
                        params.get('ErrorMessage', ''),
                    )
                else:
                    message_text = params.get('ErrorMessage', '')
                self.env['connect.settings'].connect_notify(
                    notify_uid=user.id,
                    title="Call Error",
                    message=message_text,
                    warning=True,
                )
        return channel.call.id

    @api.model
    def on_vm_recording_status(self, params):
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

    def save_call_price(self, call, params):
        """Mark call as needing price fetch (will be processed by cron job)"""
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
                    'call_sid': call_sid,
                    'is_price_fetched': False,
                }
            )
            debug(
                self,
                'Marked call {} (CallSid: {}) for price fetching by cron job'.format(
                    call.id, call_sid
                ),
            )
        except Exception as e:
            logger.error('Error in save_call_price: %s', e)

    def _fetch_call_price_from_api(self, call, call_sid):
        """Fetch call price from Twilio REST API"""
        try:
            client = self.env['connect.settings'].get_client()
            twilio_call = client.calls(call_sid).fetch()
            debug(
                self,
                'Fetched call data: price={}, price_unit={}'.format(
                    twilio_call.price, twilio_call.price_unit
                ),
            )
            if twilio_call.price is not None and twilio_call.price != '':
                try:
                    price_value = round(abs(float(twilio_call.price)), 3)
                    price_unit = twilio_call.price_unit or 'USD'
                    call.write(
                        {
                            'price': price_value,
                            'price_unit': price_unit,
                            'price_currency': price_unit,
                        }
                    )
                    debug(
                        self,
                        'Saved call price: ${:.3f} {} for call {}'.format(
                            price_value, price_unit, call.id
                        ),
                    )
                    return True
                except ValueError as e:
                    logger.error(
                        'Error converting call price %s to float: %s',
                        twilio_call.price,
                        e,
                    )
            else:
                debug(
                    self,
                    'Call price not yet available for {}, will be available later'.format(
                        call_sid
                    ),
                )
        except Exception as e:
            logger.error(
                'Error fetching call price from API for %s: %s', call_sid, e
            )
        return False

    @api.model
    def fetch_call_prices_batch(self):
        """Cron job method to fetch prices for calls that don't have them yet"""
        if not self.env['connect.settings'].sudo().get_param(
            'fetch_call_prices'
        ):
            debug(self, 'Call price fetching is disabled in settings')
            return
        # Find calls that need price fetching
        calls_to_fetch = self.search(
            [
                ('is_price_fetched', '=', False),
                ('call_sid', '!=', False),
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
            'Found {} calls needing price fetch'.format(len(calls_to_fetch)),
        )
        for call in calls_to_fetch:
            try:
                success = self._fetch_call_price_from_api(call, call.call_sid)
                if success:
                    call.write({'is_price_fetched': True})
                    debug(
                        self,
                        'Successfully fetched price for call {}'.format(
                            call.id
                        ),
                    )
                else:
                    debug(
                        self,
                        'Price not yet available for call {}, will retry next time'.format(
                            call.id
                        ),
                    )
            except Exception as e:
                logger.error(
                    'Error fetching price for call %s: %s', call.id, e
                )
        debug(self, 'Batch price fetch completed')

    def transfer(self, user=None):
        from twilio.twiml.voice_response import VoiceResponse, Dial, Sip, Conference
        import uuid

        self.ensure_one()
        # Get the PBX user doing transfer
        if not user:
            user = self.env.user.connect_user
            user = (
                self.channels[0].caller_pbx_user
                or self.channels[0].called_pbx_user
            )
        user_channel = self.channels.filtered(
            lambda x: (
                x.caller_pbx_user == user or x.called_pbx_user == user
            )
        )
        if not user_channel:
            logger.warning(
                'Cannot get user channel for call %s for user %s',
                self.id,
                user.name,
            )
            return
        other_channel = self.channels - user_channel
        if len(other_channel) != 1:
            logger.warning(
                'Cannot transfer call, number of other channels: %s',
                len(other_channel),
            )
            return
        client = self.env['connect.settings'].get_client()
        conf_id = uuid.uuid4().hex

        def transfer_other():
            response = VoiceResponse()
            response.say('Transfer')
            dial = Dial()
            dial.conference('user-{}-{}'.format(user.id, conf_id))
            response.append(dial)
            client.calls(other_channel.sid).update(twiml=response)

        def transfer_user():
            response = VoiceResponse()
            response.say('Transfer')
            dial = Dial()
            sip = Sip('sip:user@devmax17.sip.twilio.com')
            dial.append(sip)
            response.append(dial)
            client.calls(user_channel.sid).update(twiml=response)

        transfer_user()
        transfer_other()
