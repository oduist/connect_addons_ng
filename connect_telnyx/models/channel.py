# -*- coding: utf-8 -*-
import json
import logging

from markupsafe import escape

from odoo import models, api, release

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_telnyx_call_status(self, params):
        """Telnyx TeXML webhook adapter: map params and delegate to core."""
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))
        generic = self._map_telnyx_params(params)
        return self.process_channel_event(generic)

    def _map_telnyx_params(self, params):
        """Map Telnyx TeXML webhook params (Twilio-compatible) to the
        generic channel event dict."""
        return {
            'sid': params['CallSid'],
            'caller': params.get('Caller'),
            'called': params.get('Called'),
            'to': params.get('To'),
            'technical_direction': params.get('Direction'),
            'status': params.get('CallStatus'),
            'duration': int(params.get('CallDuration', 0)),
            'call_type': 'phone',
            'parent_sid': params.get('ParentCallSid'),
        }

    def telnyx_connect_notify(
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
