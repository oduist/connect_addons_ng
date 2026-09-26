# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin

from odoo import fields, models, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.voiceml.number'
    _description = 'VoiceML Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('application', 'TwiML'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.voiceml.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    application = fields.Many2one('connect.voiceml.application', ondelete='set null')
    is_ignored = fields.Boolean('Ignored')
    sid = fields.Char()
    voice_url = fields.Char(compute='_get_voiceml_urls', compute_sudo=True)
    voice_fallback_url = fields.Char(compute='_get_voiceml_urls', compute_sudo=True)
    voice_status_url = fields.Char(compute='_get_voiceml_urls', compute_sudo=True)

    def _get_voiceml_urls(self):
        api_url = self.env['connect.settings'].get_param('api_url')
        fallback_url = self.env['connect.settings'].get_param('api_fallback_url')
        for rec in self:
            rec.voice_status_url = urljoin(api_url, 'voiceml/webhook/callstatus')
            rec.voice_url = urljoin(api_url, 'voiceml/webhook/number')
            rec.voice_fallback_url = (
                urljoin(fallback_url, 'voiceml/webhook/number') if fallback_url else ''
            )

    def update_number(self, client):
        self.ensure_one()
        if self.is_ignored:
            return
        try:
            client.incoming_phone_numbers.update(
                self.sid,
                friendly_name=self.friendly_name,
                voice_url=self.voice_url,
                voice_fallback_url=self.voice_fallback_url,
            )
        except Exception as e:
            logger.exception('Number Update Exception:')
            raise ValidationError(format_connect_response(str(e)))

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow', 'application']:
                if field != vals['destination']:
                    vals.update({field: None})
        res = super().write(vals)
        if not self.env["connect.settings"].get_param("voiceml_auto_sync"):
            return res
        client = self.env['connect.settings'].get_client()
        for rec in self:
            if not self.env.context.get('skip_voiceml_sync'):
                rec.update_number(client)
        return res

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_client()
        numbers = client.incoming_phone_numbers.list().incoming_phone_numbers
        seen = set()
        for number in numbers:
            seen.add(number.sid)
            rec = self.search([('sid', '=', number.sid)])
            if not rec:
                rec = self.create({
                    'phone_number': number.phone_number,
                    'sid': number.sid,
                    'friendly_name': number.friendly_name,
                })
            rec.update_number(client)
        numbers_to_remove = self.search([
            ('sid', 'not in', list(seen)),
            ('sid', '!=', False),
        ])
        if numbers_to_remove:
            numbers_to_remove.unlink()

    def render(self, request={}, params={}):
        self.ensure_one()
        if self.destination == 'application' and self.application:
            return self.application.render(request)
        elif self.destination == 'user' and self.user:
            return self.user.render(request)
        elif self.destination == 'callflow' and self.callflow:
            return self.callflow.render(request)
        else:
            return '<Response><Say>Number not configured. Goodbye!</Say></Response>'

    @api.model
    def route_call(self, request, params={}):
        debug(self, 'Route number call: %s' % request)
        self.env['connect.call'].on_call_status(request)
        number = self.sudo().search([('phone_number', '=', request.get('Called'))])
        if not number:
            return '<Response><Say>Number not found. Goodbye!</Say></Response>'
        return number.render(request=request, params=params)
