# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

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
    ], ondelete='set null')
    callflow = fields.Many2one('connect.telnyx.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    is_ignored = fields.Boolean('Ignored')
    sid = fields.Char()
    texml = fields.Many2one(
        'connect.telnyx.texml', string='TeXML', ondelete='set null'
    )

    def update_telnyx_number(self, client):
        """Attach the number to the routing TeXML app (voice) and to the
        Odoo messaging profile (SMS). Telnyx numbers carry no per-number
        webhook URLs — routing happens in Odoo by the To number (ADR-032).
        """
        self.ensure_one()
        if self.is_ignored:
            debug(
                self,
                'Ignoring number {} update.'.format(self.phone_number),
            )
            return
        domain = self.env['connect.telnyx.domain'].search([], limit=1)
        if not domain or not domain.application.sid:
            debug(
                self,
                'No Telnyx domain/routing app yet, number {} left unrouted.'.format(
                    self.phone_number),
                level='warning',
            )
            return
        try:
            client.phone_numbers.update(
                self.sid,
                connection_id=domain.application.sid,
                customer_reference=self.friendly_name or '',
            )
            profile_id = self.env['connect.settings'].sudo().get_param(
                'telnyx_messaging_profile_id')
            if profile_id:
                client.phone_numbers.messaging.update(
                    self.sid, messaging_profile_id=profile_id)
            debug(
                self,
                'Number {} updated.'.format(self.phone_number),
            )
        except Exception as e:
            logger.exception('Number Update Exception:')
            raise ValidationError(format_connect_response(str(e)))

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow', 'texml']:
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
        else:
            return '<Response><Say>Number not configured. Goodbye!</Say></Response>'

    @api.model
    def route_call(self, request, params={}):
        debug(
            self,
            'Route number call: %s'
            % json.dumps(request, indent=2),
        )
        self.env['connect.call'].on_telnyx_call_status(request)
        number = self.sudo().search(
            [('phone_number', '=', request.get('Called') or request.get('To'))]
        )
        if not number:
            return '<Response><Say>Number not found. Goodbye!</Say></Response>'
        return number.render(request=request, params=params)
