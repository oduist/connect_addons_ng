# -*- coding: utf-8 -*-
import json
import logging
import uuid
from datetime import timedelta

from odoo import fields, models, api

from .voiceml_response import VoiceResponse, Dial

from odoo.addons.connect.models.settings import debug
from odoo.addons.connect.models.call import CALL_END_STATUSES

logger = logging.getLogger(__name__)

IGNORE_ERROR_CODES = ['32009']


class Call(models.Model):
    _inherit = 'connect.call'

    @api.model
    def on_voicetel_call_action(self, params):
        debug(self, 'On call action: %s' % params)
        response = VoiceResponse()
        response.hangup()
        return response.to_xml()

    voicetel_call_sid = fields.Char(
        string='VoiceML Call SID', readonly=True,
        help='VoiceML CallSid for fetching price information'
    )
    voicetel_price = fields.Float(
        string='Call Price', readonly=True, digits=(10, 3)
    )
    voicetel_price_unit = fields.Char(
        string='Price Unit', readonly=True,
        help='The currency unit for call price (e.g., USD)'
    )
    voicetel_is_price_fetched = fields.Boolean(
        string='Price Fetched', default=False, readonly=True,
        help='Indicates if the call price has been fetched from the VoiceML API'
    )

    @api.model
    def on_voicetel_call_status(self, params):
        """VoiceML webhook adapter: map params, delegate to core."""
        self = self.sudo()
        channel = self.env['connect.channel'].on_voicetel_call_status(params)
        if not channel:
            logger.error('No channel returned from on_voicetel_call_status!')
            return False

        error_data = None
        # The fallback voice URL fetch carries ErrorCode 11200/12100 with
        # ErrorUrl naming the failed primary fetch: a routing detail, not a
        # call failure.
        if params.get('ErrorUrl'):
            pass
        elif (params.get('ErrorCode')
                and params.get('ErrorCode') not in IGNORE_ERROR_CODES):
            error_data = {
                'error_code': params.get('ErrorCode'),
                'error_message': params.get('ErrorMessage'),
            }

        call_id = self.process_call_event(channel, error_data)

        # Desktop notification for incoming calls to a SIP device.
        if (channel.call
                and channel.call.direction == 'incoming'
                and params.get('CallStatus') == 'initiated'
                and str(params.get('To') or '').startswith('sip:')):
            channel.voicetel_notify()

        if params.get('CallStatus') in CALL_END_STATUSES:
            if self.env['connect.settings'].sudo().get_param(
                'voicetel_fetch_call_prices'
            ):
                self.voicetel_save_call_price(channel.call, params)

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
    def on_voicetel_vm_recording_status(self, params):
        debug(
            self.sudo(),
            'On voicemail recording status: %s' % json.dumps(params, indent=2),
        )
        channel = self.sudo().env['connect.channel'].search(
            [('sid', '=', params['CallSid'])]
        )
        if channel and channel.call:
            channel.call.write(
                {
                    'voicemail_url': self.env['connect.recording']._voicetel_media_url(
                        params.get('RecordingUrl')),
                    'voicemail_duration': int(
                        params.get('RecordingDuration') or 0
                    ),
                }
            )
        return True

    def voicetel_save_call_price(self, call, params):
        """Mark the call for price fetching (processed by the cron job)."""
        try:
            call_sid = params.get('CallSid')
            if not call_sid:
                return
            call.write(
                {
                    'voicetel_call_sid': call_sid,
                    'voicetel_is_price_fetched': False,
                }
            )
        except Exception as e:
            logger.error('Error in voicetel_save_call_price: %s', e)

    def _voicetel_fetch_call_price(self, call, call_sid):
        """Fetch the call price from the VoiceML REST API."""
        try:
            client = self.env['connect.settings'].get_voicetel_client()
            remote_call = client.calls.get(call_sid)
            if remote_call.price is not None and remote_call.price != '':
                try:
                    price_value = round(abs(float(remote_call.price)), 3)
                    price_unit = remote_call.price_unit or 'USD'
                    call.write(
                        {
                            'voicetel_price': price_value,
                            'voicetel_price_unit': price_unit,
                        }
                    )
                    return True
                except ValueError as e:
                    logger.error(
                        'Error converting call price %s to float: %s',
                        remote_call.price, e,
                    )
            else:
                debug(
                    self,
                    'Call price not yet available for {}'.format(call_sid),
                )
        except Exception as e:
            logger.error(
                'Error fetching call price from API for %s: %s', call_sid, e
            )
        return False

    @api.model
    def voicetel_fetch_call_prices_batch(self):
        """Cron job: fetch prices for finished calls that have none yet."""
        if not self.env['connect.settings'].sudo().get_param(
            'voicetel_fetch_call_prices'
        ):
            return
        calls_to_fetch = self.search(
            [
                ('voicetel_is_price_fetched', '=', False),
                ('voicetel_call_sid', '!=', False),
                ('status', 'in', CALL_END_STATUSES),
                (
                    'create_date',
                    '>=',
                    fields.Datetime.now() - timedelta(days=30),
                ),
            ]
        )
        for call in calls_to_fetch:
            try:
                if self._voicetel_fetch_call_price(call, call.voicetel_call_sid):
                    call.write({'voicetel_is_price_fetched': True})
            except Exception as e:
                logger.error(
                    'Error fetching price for call %s: %s', call.id, e
                )

    def voicetel_transfer(self, user=None):
        """Attended transfer through a conference room on VoiceML."""
        self.ensure_one()
        if not user:
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
                self.id, user.name,
            )
            return
        other_channel = self.channels - user_channel
        if len(other_channel) != 1:
            logger.warning(
                'Cannot transfer call, number of other channels: %s',
                len(other_channel),
            )
            return
        client = self.env['connect.settings'].get_voicetel_client()
        room = 'user-{}-{}'.format(user.id, uuid.uuid4().hex)

        response = VoiceResponse()
        response.say('Transfer')
        dial = Dial()
        dial.sip('sip:{}'.format(user.voicetel_uri))
        response.append(dial)
        client.calls.update(user_channel.sid, UpdateCallRequest(Twiml=str(response)))

        response = VoiceResponse()
        response.say('Transfer')
        dial = Dial()
        dial.conference(room)
        response.append(dial)
        client.calls.update(other_channel.sid, UpdateCallRequest(Twiml=str(response)))
