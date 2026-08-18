# -*- coding: utf-8 -*-
import json
import logging
from urllib.parse import urljoin

from markupsafe import escape

from odoo import models, api, release
from odoo.exceptions import UserError

from odoo.addons.connect.models.settings import debug
from .settings import MAX_EXTEN_LEN

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_call_status(self, params):
        """Twilio webhook adapter: map Twilio params and delegate to core."""
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))
        generic = self._map_twilio_params(params)
        return self.process_channel_event(generic)

    def _strip_exten_plus(self, number):
        """Undo the E.164 prefix Twilio puts on an extension used as caller ID.

        Internal calls hand Twilio a bare extension (``100``) as the caller
        ID, and Twilio echoes it back in its webhooks as ``+100``. Map it back
        to the extension so the ledger shows ``100`` instead of a bogus
        phone number.
        """
        if not isinstance(number, str) or not number.startswith('+'):
            return number
        candidate = number[1:]
        if not candidate.isdigit() or len(candidate) > MAX_EXTEN_LEN:
            return number
        exten = self.env['connect.twilio.exten'].sudo().search(
            [('number', '=', candidate)], limit=1
        )
        return candidate if exten else number

    def _map_twilio_params(self, params):
        """Map Twilio webhook params to generic channel event dict."""
        def strip_whatsapp(v):
            return (
                v.split(':', 1)[1]
                if isinstance(v, str) and v.startswith('whatsapp:')
                else v
            )

        caller_raw = params.get('Caller')
        called_raw = params.get('Called')
        to_raw = params.get('To')
        call_type = (
            'whatsapp'
            if any(
                isinstance(x, str) and x.startswith('whatsapp:')
                for x in [caller_raw, called_raw, to_raw]
            )
            else 'phone'
        )

        return {
            'sid': params['CallSid'],
            'caller': self._strip_exten_plus(strip_whatsapp(caller_raw)),
            'called': self._strip_exten_plus(strip_whatsapp(called_raw)),
            'to': strip_whatsapp(to_raw),
            'technical_direction': params['Direction'],
            'status': params['CallStatus'],
            'duration': int(params.get('CallDuration', 0)),
            'call_type': call_type,
            'parent_sid': params.get('ParentCallSid'),
        }

    @api.model
    def _softphone_recording_state_twilio(self, payload):
        channel = self._softphone_recording_channel(payload)
        result = channel._softphone_recording_payload()
        if result['state'] == 'off' and not result['recording_ref']:
            pbx_user = channel.caller_pbx_user or channel.called_pbx_user
            if pbx_user and pbx_user.record_calls:
                result['state'] = 'on'
        return result

    @api.model
    def _softphone_recording_start_twilio(self, payload):
        channel = self._softphone_recording_channel(payload)
        channel._check_softphone_recording_active()
        channel.sudo().write({
            'recording_state': 'starting',
            'recording_control_error': False,
        })
        try:
            settings = self.env['connect.settings'].sudo()
            api_url = settings.get_param('api_url')
            edge = settings.get_param('twilio_edge')
            callback_url = urljoin(
                api_url or '',
                'twilio/webhook/recordingstatus#e={}'.format(edge or ''),
            )
            kwargs = {
                'recording_channels': 'dual',
            }
            if api_url:
                kwargs.update({
                    'recording_status_callback': callback_url,
                    'recording_status_callback_event': ['completed'],
                })
            recording = settings.get_client().calls(
                channel.sid).recordings.create(**kwargs)
            channel.sudo().write({
                'recording_state': 'on',
                'recording_control_ref': getattr(recording, 'sid', '') or '',
                'recording_control_error': False,
            })
        except Exception as e:
            logger.exception('Twilio recording start failed for %s', channel.sid)
            channel.sudo().write({
                'recording_state': 'error',
                'recording_control_error': str(e),
            })
            raise UserError('Could not start recording: {}'.format(e))
        return channel._softphone_recording_payload()

    @api.model
    def _softphone_recording_stop_twilio(self, payload):
        channel = self._softphone_recording_channel(payload)
        channel._check_softphone_recording_active()
        channel.sudo().write({
            'recording_state': 'stopping',
            'recording_control_error': False,
        })
        recording_ref = channel.recording_control_ref or 'Twilio.CURRENT'
        try:
            self.env['connect.settings'].sudo().get_client().calls(
                channel.sid).recordings(recording_ref).update(
                    status='stopped')
            channel.sudo().write({
                'recording_state': 'off',
                'recording_control_ref': 'manual-off',
                'recording_control_error': False,
            })
        except Exception as e:
            logger.exception('Twilio recording stop failed for %s', channel.sid)
            channel.sudo().write({
                'recording_state': 'error',
                'recording_control_error': str(e),
            })
            raise UserError('Could not stop recording: {}'.format(e))
        return channel._softphone_recording_payload()

    def transfer(self, to=None):
        self.ensure_one()
        client = self.env['connect.settings'].get_client()
        call = client.calls(self.sid).update(
            twiml="<Response><Say>Ahoy there</Say></Response>"
        )

    def connect_notify(
        self, title='Connect', sticky=False, warning=False
    ):
        """Notify user about incoming call."""
        # The message is rendered as trusted HTML (markup()) on the
        # client, and self.caller / self.partner.name are attacker-
        # controlled (inbound caller-id, partner name), so every dynamic
        # value is HTML-escaped before interpolation to prevent XSS.
        caller = escape(self.caller or '')
        caller_avatar = '/web/static/img/placeholder.png'
        if self.partner:
            caller = """
                <p class="text-center"><strong>Partner:</strong>
                <a href='/web#id={}&model={}&view_type=form'>
                    {}
                </a>
                </p>
            """.format(self.partner.id, 'res.partner', escape(self.partner.name or ''))
            caller_avatar = '/web/image/res.partner/{}/image_1024'.format(
                self.partner.id
            )
        elif self.caller_user:
            caller_avatar = '/web/image/res.users/{}/image_1024'.format(
                self.caller_user.id
            )

        message = """
        <div class="d-flex align-items-center justify-content-center">
            <div>
                <img style="max-height: 100px; max-width: 100px;"
                        class="rounded-circle"
                        src="{}"/>
            </div>
            <div>
                <p class="text-center">Incoming call</p>
                {}
            </div>
        </div>
        """.format(caller_avatar, caller)

        if release.version_info[0] < 15:
            self.env['bus.bus'].sendone(
                'connect_actions_{}'.format(self.called_user.id),
                {
                    'action': 'notify',
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning,
                },
            )
        else:
            self.env['bus.bus']._sendone(
                'connect_actions_{}'.format(self.called_user.id),
                'connect_notify',
                {
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning,
                },
            )
        return True
