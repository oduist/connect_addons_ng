# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, api, release

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_call_status(self, params):
        """Twilio webhook adapter: map Twilio params and delegate to core."""
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))
        generic = self._map_twilio_params(params)
        return self.process_channel_event(generic)

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
            'caller': strip_whatsapp(caller_raw),
            'called': strip_whatsapp(called_raw),
            'to': strip_whatsapp(to_raw),
            'technical_direction': params['Direction'],
            'status': params['CallStatus'],
            'duration': int(params.get('CallDuration', 0)),
            'call_type': call_type,
            'parent_sid': params.get('ParentCallSid'),
        }

    def transfer(self, to=None):
        self.ensure_one()
        client = self.env['connect.settings'].sudo().get_client()
        call = client.calls(self.sid).update(
            twiml="<Response><Say>Ahoy there</Say></Response>"
        )

    def connect_notify(
        self, title='Connect', sticky=False, warning=False
    ):
        """Notify user about incoming call."""
        caller = self.caller
        caller_avatar = '/web/static/img/placeholder.png'
        if self.partner:
            caller = """
                <p class="text-center"><strong>Partner:</strong>
                <a href='/web#id={}&model={}&view_type=form'>
                    {}
                </a>
                </p>
            """.format(self.partner.id, 'res.partner', self.partner.name)
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
                        src={}/>
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
