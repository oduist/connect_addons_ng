import logging
import re
import secrets
import uuid

import requests

from odoo import api, fields, models

from odoo.addons.connect.models.settings import PROTECTED_FIELDS
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_dograh')
PROTECTED_FIELDS.append('display_dograh_service_token')

logger = logging.getLogger(__name__)


class Settings(models.Model):
    _inherit = 'connect.settings'

    dograh_api_url = fields.Char(
        string='Dograh API URL',
        help='Base URL of the self-hosted Dograh API, reachable from Odoo '
             '(e.g. https://dograh-api.example.com). FreeSWITCH must also '
             'reach the media WebSocket URL that Dograh advertises via its '
             'BACKEND_ENDPOINT setting.')
    dograh_account_id = fields.Char(
        default='odoo',
        help='Sent as account_id in inbound webhooks; must equal the '
             'Account ID of the FreeSWITCH telephony provider configured '
             'in Dograh.')
    # Shared secret for both control-plane directions: Odoo -> Dograh
    # inbound webhooks and Dograh -> Odoo /dograh/api/* callbacks (ADR-037).
    dograh_service_token = fields.Char(
        string='Dograh Service Token (Stored)',
        groups='connect.group_admin',
        default=lambda self: secrets.token_urlsafe(32))
    display_dograh_service_token = fields.Char(string='Dograh Service Token')
    dograh_status = fields.Char(readonly=True)

    def write(self, vals):
        if 'display_dograh_service_token' in vals and not self.env.context.get(
                'skip_protected_fields'):
            self._validate_firewall_secret(
                vals.get('display_dograh_service_token'),
                label='Dograh Service Token')
        return super().write(vals)

    def get_dograh_api_url(self):
        """Normalized Dograh API base URL (scheme required, no trailing /)."""
        url = (self.sudo().get_param('dograh_api_url') or '').strip()
        if not url:
            return ''
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.rstrip('/')

    @api.model
    def dograh_originate(self, to_number, websocket_url, from_number=None,
                         run_id=None):
        """Originate an outbound leg and fork its audio to Dograh.

        Called by Dograh's freeswitch provider (``initiate_call``) for
        campaign/test calls. Dials ``to_number`` through the matching
        outgoing route and hunts the answered leg into the
        ``dograh_outbound`` dialplan, which attaches mod_audio_fork to
        ``websocket_url`` and parks.

        Returns ``(result_dict, None)`` on success or
        ``(error_dict, http_status)`` on failure.
        """
        to_number = re.sub(r'[\s()\-]', '', to_number or '')
        # Both values are interpolated into the FreeSWITCH originate
        # dialstring, so they must not carry originate metacharacters
        # ({}[]<>,&'|" etc. — ADR-026).
        if not re.fullmatch(r'\+?[0-9*#]{1,20}', to_number):
            return {'error': 'invalid to_number'}, 400
        if not re.fullmatch(r'wss?://[A-Za-z0-9\-._~:/?=&%]+',
                            websocket_url or ''):
            return {'error': 'invalid websocket_url'}, 400
        caller_number = re.sub(r'[\s()\-]', '', from_number or '')
        if caller_number and not re.fullmatch(r'\+?[0-9*#]{1,20}',
                                              caller_number):
            return {'error': 'invalid from_number'}, 400
        if not caller_number:
            default_cid = self.env[
                'connect.freeswitch.outgoing_callerid'].sudo().search(
                    [('is_default', '=', True)], limit=1)
            caller_number = default_cid.number or '' if default_cid else ''

        Route = self.env['connect.freeswitch.outgoing_route'].sudo()
        dial_string = None
        for route in Route.search([('active', '=', True)]):
            if re.match(route.pattern, to_number):
                dial_string = Route._build_bridge_data(
                    route.gateway.name, to_number,
                    strip=route.strip, prefix=route.prefix or '')
                break
        if not dial_string:
            return {'error': 'no outgoing route for {}'.format(
                to_number)}, 404

        call_uuid = str(uuid.uuid4())
        variables = [
            'origination_uuid={}'.format(call_uuid),
            'ignore_early_media=true',
            'originate_timeout=25',
            # Never disclose a name on the PSTN leg (ADR-026).
            "origination_caller_id_name=''",
            'odoo_call_direction=outgoing',
            "absolute_codec_string='PCMU,PCMA'",
            'dograh_ws_url={}'.format(websocket_url),
        ]
        if caller_number:
            variables.append(
                'origination_caller_id_number={}'.format(caller_number))
        if run_id:
            variables.append('odoo_dograh_run_id={}'.format(run_id))
        cmd = '{{{}}}{} dograh_outbound XML default'.format(
            ','.join(variables), dial_string)
        logger.info('Dograh originate: %s', cmd)
        result = self.sudo().freeswitch_api('originate', cmd)
        if result is False:
            return {'error': 'freeswitch unreachable'}, 502
        if result.startswith('-ERR'):
            logger.error('Dograh originate failed: %s', result)
            return {'error': result.strip()}, 502
        return {'call_uuid': call_uuid,
                'status': 'answered',
                'from_number': caller_number}, None

    def check_dograh_status(self):
        self.ensure_one()
        api_url = self.get_dograh_api_url()
        if not api_url:
            self.dograh_status = 'NOT CONFIGURED'
            return
        try:
            response = requests.get(
                '{}/api/v1/health'.format(api_url), timeout=5)
            if response.status_code == 200:
                version = response.json().get('version') or ''
                self.dograh_status = 'UP {}'.format(version).strip()
            else:
                self.dograh_status = 'DOWN (HTTP {})'.format(
                    response.status_code)
        except Exception as e:
            logger.warning('Dograh health check failed: %s', e)
            self.dograh_status = 'DOWN'
