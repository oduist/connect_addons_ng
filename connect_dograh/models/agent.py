import json
import logging
import re

import requests

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class DograhAgent(models.Model):
    _name = 'connect.dograh.agent'
    _description = 'Dograh AI Agent'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    # Informational only: the called number -> workflow mapping lives in
    # Dograh (Phone Numbers page), exactly like its Asterisk ARI provider.
    workflow_id = fields.Char(
        string='Dograh Workflow',
        help='Dograh workflow this extension routes to. Informational: the '
             'actual mapping is configured in Dograh under Phone Numbers by '
             'assigning an inbound workflow to this extension number.')
    exten = fields.Many2one('connect.freeswitch.exten', readonly=True,
                            ondelete='set null')
    exten_number = fields.Char(related='exten.number', store=True)
    record_calls = fields.Boolean(
        default=True,
        help='Record the call with the standard FreeSWITCH recording '
             'webhook. Dograh keeps its own run recording independently.')
    notes = fields.Text()

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.freeswitch.exten'].create_extension(
            self, 'connect.dograh.agent')

    def _dograh_start_inbound_run(self, params, number):
        """POST the inbound webhook to Dograh and return its JSON reply.

        Returns a dict with ``websocket_url`` (and ``workflow_run_id``) on
        success, or ``None`` when Dograh is unreachable, rejects the call
        (no phone number / workflow / quota) or replies with an
        unexpected body.
        """
        settings = self.env['connect.settings'].sudo()
        api_url = settings.get_dograh_api_url()
        token = settings.get_param('dograh_service_token')
        account_id = settings.get_param('dograh_account_id')
        if not api_url or not token or not account_id:
            logger.error(
                'Dograh settings incomplete (URL, service token or account '
                'ID missing), cannot route call to agent %s.', self.name)
            return None
        payload = {
            'provider': 'freeswitch',
            'account_id': account_id,
            'call_id': params.get('Caller-Unique-ID') or '',
            'from_number': params.get('Caller-Caller-ID-Number') or '',
            'to_number': number,
            'direction': 'inbound',
            'call_status': 'ringing',
        }
        url = '{}/api/v1/telephony/inbound/run'.format(api_url)
        try:
            response = requests.post(
                url, json=payload,
                headers={'Authorization': 'Bearer {}'.format(token)},
                timeout=5)
        except requests.RequestException as e:
            logger.error('Dograh inbound run request failed: %s', e)
            return None
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            logger.error(
                'Dograh inbound run: non-JSON reply (HTTP %s): %s',
                response.status_code, response.text[:200])
            return None
        if response.status_code != 200 or not data.get('websocket_url'):
            # Validation errors come back as {"error": ..., "message": ...}.
            logger.error(
                'Dograh inbound run rejected (HTTP %s): %s',
                response.status_code, data)
            return None
        return data

    def generate_dialplan(self, params, exten=None):
        """Render the FreeSWITCH dialplan routing this call into Dograh."""
        self.ensure_one()
        exten = exten or self.exten
        number = exten.number if exten else ''
        settings = self.env['connect.settings'].sudo()
        run = self._dograh_start_inbound_run(params, number)
        if not run:
            # Fail with a busy signal so the caller is not left hanging.
            return (
                '<extension name="dograh_agent_{agent_id}_error">'
                '<condition field="destination_number" '
                'expression="^{number}$">'
                '<action application="respond" data="486"/>'
                '</condition></extension>').format(
                    agent_id=self.id, number=re.escape(number))
        recording_url = settings.get_recording_webhook_url()
        return self.env['connect.freeswitch.template'].sudo().render(
            'dialplan_dograh_agent', {
                'agent_id': self.id,
                'number': re.escape(number),
                'ws_url': run['websocket_url'],
                'run_id': run.get('workflow_run_id') or '',
                'record_calls': self.record_calls,
                'recording_url': recording_url,
            })
