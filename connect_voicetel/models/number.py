# -*- coding: utf-8 -*-
import json
import logging
from odoo import fields, models, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.voicetel.number'
    _description = 'VoiceTel Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('voiceml', 'VoiceML'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.voicetel.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    is_ignored = fields.Boolean('Ignored')
    sid = fields.Char()
    voice_url = fields.Char(
        compute='_get_voicetel_urls', compute_sudo=True
    )
    voice_fallback_url = fields.Char(
        compute='_get_voicetel_urls', compute_sudo=True
    )
    voice_status_url = fields.Char(
        compute='_get_voicetel_urls', compute_sudo=True
    )
    message_url = fields.Char(
        compute='_get_voicetel_urls', compute_sudo=True
    )
    message_fallback_url = fields.Char(
        compute='_get_voicetel_urls', compute_sudo=True
    )
    voiceml = fields.Many2one(
        'connect.voicetel.voiceml', string='VoiceML', ondelete='set null'
    )

    def _get_voicetel_urls(self):
        settings = self.env['connect.settings'].sudo()
        fallback_url = settings.get_param('api_fallback_url')
        for rec in self:
            rec.voice_status_url = settings.voicetel_webhook_url(
                'voicetel/webhook/callstatus')
            rec.voice_url = settings.voicetel_webhook_url('voicetel/webhook/number')
            rec.message_url = settings.voicetel_webhook_url('voicetel/webhook/message')
            rec.message_fallback_url = rec.message_url
            if fallback_url:
                rec.voice_fallback_url = '{}/voicetel/webhook/number'.format(
                    fallback_url.rstrip('/'))
            else:
                rec.voice_fallback_url = ''

    def update_voicetel_number(self, client):
        self.ensure_one()
        if self.is_ignored:
            debug(
                self,
                'Ignoring number {} update.'.format(self.phone_number),
            )
            return
        try:
            client.incoming_phone_numbers.update(
                self.sid,
                voice_url=self.voice_url,
                voice_fallback_url=self.voice_fallback_url,
                sms_url=self.message_url,
                sms_fallback_url=self.message_fallback_url,
                status_callback=self.voice_status_url,
            )
            debug(
                self,
                'Number {} updated.'.format(self.phone_number),
            )
        except Exception as e:
            logger.exception('Number Update Exception:')
            raise ValidationError(format_connect_response(str(e)))

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow', 'voiceml']:
                if field != vals['destination']:
                    vals.update({field: None})
        res = super().write(vals)
        if not self.env["connect.settings"].get_param(
            "voicetel_auto_sync"
        ):
            return res
        client = self.env['connect.settings'].get_voicetel_client()
        for rec in self:
            if not self.env.context.get('skip_voicetel_sync'):
                rec.update_voicetel_number(client)
        return res

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_voicetel_client()
        numbers = client.incoming_phone_numbers.iter()
        for number in numbers:
            rec = self.search([('sid', '=', number.sid)])
            if not rec:
                rec = self.create(
                    {
                        'phone_number': number.phone_number,
                        'sid': number.sid,
                        'friendly_name': number.friendly_name,
                    }
                )
                rec.update_voicetel_number(client)
                self.env['connect.settings'].connect_notify(
                    title="VoiceTel Sync",
                    message='Number {} added'.format(
                        number.phone_number
                    ),
                )
            else:
                rec.update_voicetel_number(client)
        # Remove numbers that exist only in Odoo
        numbers_to_remove = self.search(
            [
                ('sid', 'not in', [k.sid for k in numbers]),
                ('sid', '!=', False),
            ]
        )
        if numbers_to_remove:
            user_message = 'Number(s) {} removed in VoiceTel!'.format(
                ','.join(
                    [k.phone_number for k in numbers_to_remove]
                )
            )
            numbers_to_remove.unlink()
            self.env['connect.settings'].connect_notify(
                title="VoiceTel Sync",
                warning=True,
                sticky=True,
                message=user_message,
            )

    def render(self, request=None, params=None):
        request = dict(request or {})
        params = dict(params or {})
        self.ensure_one()
        if not self.env["oduist.license"].check_license('connect'):
            return '<Response><Say>Service unavailable.</Say></Response>'
        if self.destination == 'voiceml' and self.voiceml:
            return self.voiceml.render(request)
        elif self.destination == 'user' and self.user:
            return self.user.voicetel_render(request)
        elif self.destination == 'callflow' and self.callflow:
            return self.callflow.render(request)
        else:
            return '<Response><Say>Number not configured. Goodbye!</Say></Response>'

    @api.model
    def route_call(self, request, params=None):
        params = dict(params or {})
        debug(
            self,
            'Route number call: %s'
            % json.dumps(request, indent=2),
        )
        self.env['connect.call'].on_voicetel_call_status(request)
        number = self.sudo().search(
            [('phone_number', '=', request.get('Called') or request.get('To'))], limit=1
        )
        if not number:
            return '<Response><Say>Number not found. Goodbye!</Say></Response>'
        return number.render(request=request, params=params)
