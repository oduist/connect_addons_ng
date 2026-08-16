# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response
from .texml_response import Connect, VoiceResponse
from .utils import format_telnyx_debug_payload

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.telnyx.number'
    _description = 'Telnyx Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('texml', 'TeXML'),
        ('ai_assistant', 'AI Assistant'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.telnyx.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    is_ignored = fields.Boolean('Ignored')
    sid = fields.Char()
    texml = fields.Many2one(
        'connect.telnyx.texml', string='TeXML', ondelete='set null'
    )
    ai_assistant = fields.Many2one(
        'connect.telnyx.ai_assistant', string='AI Assistant',
        ondelete='set null',
    )

    @api.model
    def get_number_app(self):
        """The TeXML application inbound calls to numbers are routed to.

        Telnyx numbers carry no per-number webhook URL, so every number
        points at one application whose voice_url renders
        `connect.telnyx.number.route_call` and dispatches by the dialled
        number (ADR-032).
        """
        app = self.env['connect.telnyx.texml'].search(
            [
                ('code_type', '=', 'model_method'),
                ('model', '=', 'connect.telnyx.number'),
                ('method', '=', 'route_call'),
            ],
            limit=1,
        )
        if not app:
            app = self.env['connect.telnyx.texml'].create(
                {
                    'model': 'connect.telnyx.number',
                    'method': 'route_call',
                    'code_type': 'model_method',
                    'name': 'Number Calls',
                    'description': 'Required application!',
                }
            )
        return app

    def update_telnyx_number(self, client):
        """Attach the number to the number-routing TeXML app (voice) and
        to the Odoo messaging profile (SMS). Telnyx numbers carry no
        per-number webhook URLs — routing happens in Odoo by the To
        number (ADR-032).
        """
        self.ensure_one()
        if self.is_ignored:
            debug(
                self,
                'Ignoring number {} update.'.format(self.phone_number),
            )
            return
        app = self.get_number_app()
        if not app.sid:
            app.update_telnyx_app(client)
        try:
            client.phone_numbers.update(
                self.sid,
                connection_id=app.sid,
                customer_reference=self.friendly_name or '',
            )
            debug(
                self,
                'Number {} updated.'.format(self.phone_number),
            )
        except Exception as e:
            logger.exception('Number Update Exception:')
            raise ValidationError(format_connect_response(str(e)))
        # Messaging is optional: numbers without SMS capability reject the
        # profile attach, and that must not abort the account sync.
        profile_id = self.env['connect.settings'].sudo().get_param(
            'telnyx_messaging_profile_id')
        if not profile_id:
            return
        try:
            client.phone_numbers.messaging.update(
                self.sid, messaging_profile_id=profile_id)
        except Exception as e:
            debug(
                self,
                'Number {} was not attached to the messaging profile: {}'.format(
                    self.phone_number, format_connect_response(str(e))),
                level='warning',
            )

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow', 'texml', 'ai_assistant']:
                if field != vals['destination']:
                    vals.update({field: None})
        res = super().write(vals)
        if not self.env["connect.settings"].get_param("telnyx_auto_sync"):
            return res
        client = self.env['connect.settings'].get_telnyx_client()
        for rec in self:
            if not self.env.context.get('skip_telnyx_sync'):
                rec.update_telnyx_number(client)
        return res

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_telnyx_client()
        numbers = list(client.phone_numbers.list())
        for number in numbers:
            rec = self.search([('sid', '=', number.id)])
            if not rec:
                rec = self.with_context(skip_telnyx_sync=True).create(
                    {
                        'phone_number': number.phone_number,
                        'sid': number.id,
                        'friendly_name': number.customer_reference or '',
                    }
                )
                rec.update_telnyx_number(client)
                self.env['connect.settings'].connect_notify(
                    title="Telnyx Sync",
                    message='Number {} added'.format(
                        number.phone_number
                    ),
                )
            else:
                rec.update_telnyx_number(client)
        # Remove numbers that exist only in Odoo
        numbers_to_remove = self.search(
            [
                ('sid', 'not in', [k.id for k in numbers]),
                ('sid', '!=', False),
            ]
        )
        if numbers_to_remove:
            user_message = 'Number(s) {} removed in Telnyx!'.format(
                ','.join(
                    [k.phone_number for k in numbers_to_remove]
                )
            )
            numbers_to_remove.unlink()
            self.env['connect.settings'].connect_notify(
                title="Telnyx Sync",
                warning=True,
                sticky=True,
                message=user_message,
            )

    def render(self, request={}, params={}):
        self.ensure_one()
        if not self.env["oduist.license"].check_license('connect'):
            return '<Response><Say>Service unavailable.</Say></Response>'
        if self.destination == 'texml' and self.texml:
            return self.texml.render(request)
        elif self.destination == 'user' and self.user:
            return self.user.telnyx_render(request)
        elif self.destination == 'callflow' and self.callflow:
            return self.callflow.render(request)
        elif self.destination == 'ai_assistant' and self.ai_assistant:
            if not self.ai_assistant.sid:
                return '<Response><Say>AI assistant is not synchronized.</Say></Response>'
            response = VoiceResponse()
            connect = Connect()
            connect.ai_assistant(self.ai_assistant.sid)
            response.append(connect)
            return response.to_xml()
        else:
            return '<Response><Say>Number not configured. Goodbye!</Say></Response>'

    @api.model
    def route_call(self, request, params={}):
        debug(
            self,
            'Route number call: %s'
            % format_telnyx_debug_payload(request),
        )
        self.env['connect.call'].on_telnyx_call_status(request)
        return self.sudo().render_inbound(request, params=params)

    @api.model
    def render_inbound(self, request, params={}):
        """Render the dialplan for a call arriving on one of our numbers.

        Called both from the number application webhook and from
        `connect.telnyx.domain.route_call()`, which still receives the
        inbound leg on installations whose numbers are attached to the
        domain application. The call ledger is updated by the caller.
        """
        dialed = request.get('Called') or request.get('To') or ''
        number = self.sudo().search([('phone_number', '=', dialed)], limit=1)
        if number and number.destination:
            return number.render(request=request, params=params)
        # Numbers may also be routed through an extension carrying the
        # number itself, the way SIP subdomain calls are.
        exten = self.env['connect.telnyx.exten'].sudo().search(
            [('number', '=', dialed)], limit=1)
        if exten:
            return exten.render(request=request, params=params)
        if not number:
            return '<Response><Say>Number not found. Goodbye!</Say></Response>'
        return number.render(request=request, params=params)
