import secrets

import httpx

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import PROTECTED_FIELDS

ODUIST_MODULES.append('connect_pipecat')

for _field in (
    'display_pipecat_service_token',
    'display_deepgram_api_key',
    'display_elevenlabs_api_key',
    'display_anthropic_api_key',
):
    if _field not in PROTECTED_FIELDS:
        PROTECTED_FIELDS.append(_field)


class Settings(models.Model):
    _inherit = 'connect.settings'

    pipecat_sidecar_url = fields.Char(
        string='Pipecat Sidecar URL',
        default='ws://pipecat-agent:7860',
        help='Base WebSocket or HTTP URL of the Pipecat sidecar.',
    )
    pipecat_service_token = fields.Char(
        groups='connect.group_admin',
        default=lambda self: secrets.token_urlsafe(32),
    )
    display_pipecat_service_token = fields.Char(groups='connect.group_admin')
    deepgram_api_key = fields.Char(groups='connect.group_admin')
    display_deepgram_api_key = fields.Char(groups='connect.group_admin')
    elevenlabs_api_key = fields.Char(groups='connect.group_admin')
    display_elevenlabs_api_key = fields.Char(groups='connect.group_admin')
    anthropic_api_key = fields.Char(groups='connect.group_admin')
    display_anthropic_api_key = fields.Char(groups='connect.group_admin')
    pipecat_status = fields.Char(readonly=True)

    def write(self, vals):
        if (not self.env.context.get('skip_protected_fields')
                and vals.get('display_pipecat_service_token')):
            self._validate_firewall_secret(
                vals['display_pipecat_service_token'],
                label='Pipecat Service Token',
            )
        return super().write(vals)

    def get_pipecat_ws_url(self):
        base = (self.sudo().get_param('pipecat_sidecar_url') or '').strip()
        if base.startswith('https://'):
            return 'wss://' + base[8:]
        if base.startswith('http://'):
            return 'ws://' + base[7:]
        return base

    def get_pipecat_http_url(self):
        base = (self.sudo().get_param('pipecat_sidecar_url') or '').strip()
        if base.startswith('wss://'):
            return 'https://' + base[6:]
        if base.startswith('ws://'):
            return 'http://' + base[5:]
        return base

    def check_pipecat_status(self):
        self.ensure_one()
        url = self.get_pipecat_http_url().rstrip('/')
        token = self.sudo().get_param('pipecat_service_token') or ''
        if not url or not token:
            self.pipecat_status = 'NOT CONFIGURED'
            raise UserError('Configure the sidecar URL and service token first.')
        try:
            response = httpx.get(
                url + '/health',
                headers={'Authorization': 'Bearer {}'.format(token)},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            self.pipecat_status = 'UP ({})'.format(data.get('version', 'unknown'))
        except Exception as exc:
            self.pipecat_status = 'DOWN'
            raise UserError('Pipecat sidecar is unavailable: {}'.format(exc)) from exc
        return True
