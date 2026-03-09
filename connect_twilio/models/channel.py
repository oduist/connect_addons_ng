# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api, release

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'connect.channel'

    sid = fields.Char('SID', readonly=True)

    @api.model
    def on_call_status(self, params):
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))

        # Pre-process for WhatsApp and E.164 normalization
        def strip_whatsapp(v):
            return (
                v.split(':', 1)[1]
                if isinstance(v, str) and v.startswith('whatsapp:')
                else v
            )

        caller_raw = params.get('Caller')
        called_raw = params.get('Called')
        to_raw = params.get('To')
        caller_clean = strip_whatsapp(caller_raw)
        called_clean = strip_whatsapp(called_raw)
        to_clean = strip_whatsapp(to_raw)
        call_type = (
            'whatsapp'
            if any(
                isinstance(x, str) and x.startswith('whatsapp:')
                for x in [caller_raw, called_raw, to_raw]
            )
            else 'phone'
        )

        channel = self.search(
            [('sid', '=', params['CallSid'])], limit=1, order='id asc'
        )
        if channel:
            # Update channel data.
            data = {
                'called': called_clean,
                'to': to_clean,
                'technical_direction': params['Direction'],
                'status': params['CallStatus'],
                'duration': int(params.get('CallDuration', 0)),
                'caller': caller_clean,
                'call_type': call_type,
            }
            # Find an existing parent channel.
            if not channel.parent_channel:
                if channel.parent_sid:
                    parent_channel = self.search(
                        [('sid', '=', channel.parent_sid)]
                    )
                    data['parent_channel'] = parent_channel.id
                elif params.get('ParentCallSid'):
                    parent_channel = self.search(
                        [('sid', '=', params.get('ParentCallSid'))]
                    )
                    data['parent_channel'] = parent_channel.id
                    data['parent_sid'] = parent_channel.parent_channel.sid
            channel.write(data)
            debug(self, 'Channel %s updated.' % channel.id)
        else:
            # Channel not found by sid, create it.
            data = {
                'sid': params['CallSid'],
                'called': called_clean,
                'to': to_clean,
                'technical_direction': params['Direction'],
                'status': params['CallStatus'],
                'duration': int(params.get('CallDuration', 0)),
                'caller': caller_clean,
                'call_type': call_type,
            }
            if channel.parent_sid:
                parent_channel = self.search(
                    [('sid', '=', channel.parent_sid)]
                )
                data['parent_channel'] = parent_channel.id
            elif params.get('ParentCallSid'):
                parent_channel = self.search(
                    [('sid', '=', params.get('ParentCallSid'))]
                )
                data['parent_channel'] = parent_channel.id
                data['parent_sid'] = parent_channel.parent_channel.sid
            # Find caller user
            caller_pbx_user = None
            called_pbx_user = None
            if params.get('Caller'):
                caller_pbx_user = self.env[
                    'connect.user'
                ].get_user_by_uri(params['Caller'])
                data['caller_pbx_user'] = caller_pbx_user.id
                data['caller_user'] = caller_pbx_user.user.id
            # Find called user
            if params.get('Called'):
                called_pbx_user = self.env[
                    'connect.user'
                ].get_user_by_uri(params['Called'])
                data['called_pbx_user'] = called_pbx_user.id
                data['called_user'] = called_pbx_user.user.id
            # Find the partner
            if caller_pbx_user and called_clean:
                if (called_clean or '').startswith('+'):
                    data['partner'] = self.env[
                        'res.partner'
                    ].get_partner_by_number(called_clean).id
                    debug(self, 'Setting partner caller user by called.')
            elif called_pbx_user and caller_clean:
                if (caller_clean or '').startswith('+'):
                    data['partner'] = self.env[
                        'res.partner'
                    ].get_partner_by_number(caller_clean).id
                    debug(self, 'Setting partner called user by caller.')
            elif (
                params.get('Direction') == 'outbound-dial' and called_clean
            ):
                data['partner'] = self.env[
                    'res.partner'
                ].get_partner_by_number(called_clean).id
                debug(self, 'Setting partner for outbound dial by called.')
            elif (
                params.get('Direction') == 'inbound'
                and (called_clean or '').startswith('+')
                and (caller_clean or '').startswith('+')
            ):
                debug(
                    self,
                    'Incoming DID/WhatsApp call. Get the partner from caller number.',
                )
                data['partner'] = self.env[
                    'res.partner'
                ].get_partner_by_number(caller_clean).id
            else:
                debug(
                    self,
                    'Not setting channel partner without channel users.',
                )
            channel = self.with_context(tracking_disable=True).create(data)
            debug(self, 'Channel %s created.' % channel.id)
        return channel

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
