# -*- coding: utf-8 -*-
import logging
import re
import secrets
from urllib.parse import urljoin

import requests

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

ODUIST_MODULES.append('connect_infobip')

logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

INFOBIP_PROTECTED_FIELDS = [
    "display_infobip_api_key",
]


def strip_number(number):
    """Strip number formatting"""
    if not isinstance(number, str):
        return number
    pattern = r"[\s\(\)\-\+]"
    return re.sub(pattern, "", number).lstrip("0")


class Settings(models.Model):
    _inherit = "connect.settings"

    # Personalized per-account API host, e.g. https://xxxxx.api.infobip.com.
    # Infobip publishes no fixed global endpoint for production accounts,
    # so the base URL is configuration, not a constant (ADR-036).
    infobip_base_url = fields.Char(string="Infobip Base URL")
    # Never grant this to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members (ADR-025).
    infobip_api_key = fields.Char(groups="base.group_erp_manager")
    display_infobip_api_key = fields.Char(string="Infobip API Key")
    # Shared secret embedded as ?token= into every webhook URL configured
    # on the Infobip side. Infobip does not sign webhooks, so this token
    # plus HTTPS is the trust boundary (ADR-036).
    infobip_webhook_token = fields.Char(
        groups="connect.group_admin",
        default=lambda self: secrets.token_urlsafe(32))
    infobip_verify_requests = fields.Boolean(
        default=True, string="Verify Infobip Requests")
    infobip_auto_sync = fields.Boolean(default=True)
    infobip_calls_configuration_id = fields.Char(
        string="Calls Configuration ID",
        help="Infobip Calls configuration (application) ID used for voice "
             "call control. Auto-created as 'Odoo Connect' on sync when "
             "empty; a manually entered value is never overwritten.")
    infobip_webrtc_application_id = fields.Char(
        string="WebRTC Application ID",
        help="Optional WebRTC application ID included in web phone token "
             "requests when the account requires one.")
    infobip_webphone_via_rest = fields.Boolean(
        string="Web Phone Dials via REST",
        help="Fallback mode: the web phone originates calls through the "
             "REST API (agent leg rings first) instead of calling the "
             "Infobip application directly from the browser.")
    infobip_webhook_urls = fields.Text(
        compute='_get_infobip_webhook_urls', string='Infobip Webhook URLs')

    def _get_infobip_webhook_urls(self):
        for rec in self:
            try:
                rec.infobip_webhook_urls = '\n'.join([
                    'Voice receive URL: {}'.format(
                        self.get_infobip_webhook_url('voice/received')),
                    'Voice event URL: {}'.format(
                        self.get_infobip_webhook_url('voice/event')),
                    'Inbound SMS URL: {}'.format(
                        self.get_infobip_webhook_url('message')),
                    'Inbound WhatsApp URL: {}'.format(
                        self.get_infobip_webhook_url('whatsapp')),
                    'Delivery report URL: {}'.format(
                        self.get_infobip_webhook_url('message_status')),
                ])
            except Exception:
                logger.exception('Webhook URLs compute error:')
                rec.infobip_webhook_urls = ''

    @api.model
    def get_infobip_webhook_url(self, endpoint):
        """Absolute webhook URL with the shared token, for the Infobip side."""
        api_url = self.sudo().get_param('api_url')
        url = urljoin(api_url, 'infobip/webhook/{}'.format(endpoint))
        token = self.sudo().get_param('infobip_webhook_token') or ''
        if token:
            url = '{}?token={}'.format(url, token)
        return url

    @api.model
    def _infobip_http(self, method, path, payload=None, params=None,
                      timeout=20):
        """Perform an authenticated Infobip API request, return the response.

        The account key never appears in error messages or debug output.
        """
        # connect.settings is admin-only; credentials are read with sudo()
        # here, so no caller-level model access check is needed.
        api_key = self.sudo().get_param('infobip_api_key')
        if not api_key:
            raise ValidationError('Set the Infobip API key first!')
        base_url = (self.sudo().get_param('infobip_base_url') or '').strip()
        if not base_url:
            raise ValidationError('Set the Infobip base URL first!')
        if not base_url.endswith('/'):
            base_url += '/'
        url = urljoin(base_url, path.lstrip('/'))
        try:
            response = requests.request(
                method.upper(), url,
                headers={
                    'Authorization': 'App {}'.format(api_key),
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                json=payload,
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            # RequestException reprs carry only the URL and transport error,
            # never the Authorization header.
            raise ValidationError(
                'Infobip API request failed: {}'.format(exc)) from exc
        if response.status_code >= 400:
            detail = None
            try:
                body = response.json()
                detail = (
                    body.get('requestError', {})
                        .get('serviceException', {}).get('text')
                    or body.get('errorMessage') or body.get('message')
                )
            except ValueError:
                pass
            raise ValidationError(
                'Infobip API returned HTTP {}{}'.format(
                    response.status_code,
                    ': {}'.format(detail) if detail else '',
                )
            )
        return response

    @api.model
    def infobip_api_request(self, method, path, payload=None, params=None,
                            timeout=20):
        """Call an Infobip endpoint and return the decoded JSON body."""
        response = self._infobip_http(
            method, path, payload=payload, params=params, timeout=timeout)
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ValidationError(
                'Infobip API returned an invalid JSON response.') from exc

    @api.model
    def infobip_api_request_raw(self, method, path, params=None, timeout=60):
        """Call an Infobip endpoint and return raw bytes (file downloads)."""
        response = self._infobip_http(
            method, path, params=params, timeout=timeout)
        return response.content

    @api.model
    def infobip_list_numbers(self):
        """List all numbers owned in the account (Numbers API, paginated)."""
        results, page = [], 0
        while True:
            data = self.infobip_api_request(
                'GET', '/numbers/1/numbers',
                params={'page': page, 'size': 100})
            batch = data.get('numbers') or data.get('results') or []
            results.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return results

    def infobip_sync(self):
        if not self.sudo().get_param('infobip_api_key'):
            raise ValidationError('You must set the Infobip API key!')
        if not self.sudo().get_param('infobip_base_url'):
            raise ValidationError('You must set the Infobip base URL!')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self.infobip_setup_webhooks()
            self.env['connect.infobip.number'].sync()
            self.env['connect.infobip.outgoing_callerid'].sync()
            # WhatsApp onboarding is optional on the Infobip account —
            # keep its sync failures non-fatal (ADR-033 pattern).
            for model, title in [
                ('connect.infobip.whatsapp_sender', 'WhatsApp Senders'),
                ('connect.infobip.whatsapp_template', 'WhatsApp Templates'),
            ]:
                try:
                    self.env[model].sync()
                except Exception as e:
                    logger.warning('%s sync failed: %s', title, e)
                    self.connect_notify(
                        '{} sync failed: {}'.format(title, e),
                        title='Sync Warning', warning=True)
            self.connect_notify(
                'Infobip account synced successfully', title='Sync Complete')
        except Exception as e:
            if '401' in str(e) or 'UNAUTHORIZED' in str(e).upper():
                raise ValidationError(
                    'Error authenticating requests to the Infobip API! '
                    'Check your API key and base URL!'
                )
            else:
                raise

    def infobip_setup_webhooks(self):
        """Best-effort provisioning of the Infobip-side voice plumbing.

        Auto-creates the 'Odoo Connect' Calls configuration when the ID is
        empty. Event subscriptions (receive/event URLs) are NOT
        auto-provisioned: the Subscriptions API shape varies between
        classic and CPaaS-X accounts, so the admin wires the URLs shown in
        the settings form in the Infobip portal instead (ADR-036). An
        admin-entered configuration ID is authoritative and never
        overwritten.
        """
        cfg = self.sudo().get_param('infobip_calls_configuration_id')
        if not cfg:
            try:
                existing = self.infobip_api_request(
                    'GET', '/calls/1/configurations',
                    params={'page': 0, 'size': 100})
                for item in existing.get('results', []):
                    if item.get('name') == 'Odoo Connect':
                        cfg = item.get('id')
                        break
                if not cfg:
                    created = self.infobip_api_request(
                        'POST', '/calls/1/configurations',
                        {'name': 'Odoo Connect'})
                    cfg = created.get('id')
                if cfg:
                    self.sudo().set_param(
                        'infobip_calls_configuration_id', cfg)
                    debug(self, 'Infobip calls configuration: {}'.format(cfg))
            except Exception as e:
                logger.warning(
                    'Infobip calls configuration setup failed: %s', e)
                self.connect_notify(
                    'Could not create the Infobip Calls configuration '
                    'automatically ({}). Create one in the Infobip portal '
                    '(Voice & Video) and paste its ID into Infobip '
                    'Settings.'.format(e),
                    title='Infobip Setup', warning=True, sticky=True)
        self.connect_notify(
            'Configure these URLs on the Infobip side (Calls configuration '
            'webhooks / number forwarding):\n{}'.format(
                self.infobip_webhook_urls or ''),
            title='Infobip Webhooks')

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None,
                       **kwargs):
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Infobip.
        if self._get_originate_provider(user) != 'infobip':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user,
                **kwargs)
        self.env['oduist.license'].check_license('connect', silent=False)
        cfg = self.sudo().get_param('infobip_calls_configuration_id')
        if not cfg:
            raise ValidationError(
                'Set the Infobip Calls Configuration ID in Infobip settings '
                'first (run Sync)!')
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = '+{}'.format(number)
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        caller_name = ''
        if res_model == 'res.partner' and obj:
            partner_id = res_id
            caller_name = obj.display_name
        elif obj and hasattr(obj, 'partner_id') and obj.partner_id:
            partner_id = obj.partner_id.id
            caller_name = obj.partner_id.display_name
        elif obj and hasattr(obj, 'partner') and obj.partner:
            partner_id = obj.partner.id
            caller_name = obj.partner.display_name
        if not user:
            user = self.env.user
        connect_user = user.connect_user
        if not connect_user:
            raise ValidationError('User does not have a PBX user defined!')
        first_flow = self.env['connect.infobip.user_callflow'].search([
            ('user', '=', connect_user.id),
        ], order='prio', limit=1)
        if not first_flow:
            raise ValidationError(
                'Enable the web phone or an external phone on the Connect '
                'user first!')
        if first_flow.callflow_type == 'phone':
            endpoint = {
                'type': 'PHONE',
                'phoneNumber': connect_user.infobip_phone_number,
            }
        else:
            endpoint = {
                'type': 'WEBRTC',
                'identity': connect_user.infobip_identity,
            }
        exten = self.env['connect.infobip.exten'].search(
            [('number', '=', number)], limit=1)
        if exten and connect_user.infobip_exten:
            callerId = connect_user.infobip_exten.number
        else:
            if connect_user.infobip_outgoing_callerid:
                callerId = connect_user.infobip_outgoing_callerid.number
            else:
                callerId = self.env[
                    'connect.infobip.outgoing_callerid'
                ].search([('is_default', '=', True)], limit=1).number
            if not callerId:
                raise ValidationError(
                    'No outgoing caller ID: set one on the Connect user or '
                    'mark a default Infobip caller ID!')
        # customData values must be strings; they are echoed back in every
        # event for this leg and in the WebRTC SDK, carrying the ledger
        # correlation through webhook races (ADR-036).
        custom_data = {
            'technical_direction': 'outbound-api',
            'caller_pbx_user_id': str(connect_user.id),
            'originate_dest': number,
            'autoAnswer': 'yes' if kwargs.get('auto_answer') else '',
            # Shown by the web phone as the dialed party (the agent leg
            # rings first, then the destination is bridged).
            'From': number.replace('+', ''),
        }
        if partner_id:
            custom_data['Partner'] = str(partner_id)
        if caller_name:
            custom_data['CallerName'] = caller_name
        payload = {
            'endpoint': endpoint,
            'from': callerId,
            'callsConfigurationId': cfg,
            'connectTimeout': int(first_flow.ring_timeout or 30),
            'customData': custom_data,
        }
        call_duration_limit = int(
            self.sudo().get_param('call_duration_limit') or 0)
        if call_duration_limit:
            payload['maxDuration'] = call_duration_limit
        debug(self, 'Infobip originate to {}: agent endpoint {}'.format(
            number, endpoint.get('identity') or endpoint.get('phoneNumber')))
        resp = self.infobip_api_request('POST', '/calls/1/calls', payload)
        sid = resp.get('id')
        if not sid:
            debug(
                self,
                'Infobip originate response has no call id; webhook events '
                'will create the channel record.',
                level='warning',
            )
            return
        # Upsert under the same per-callId advisory lock the webhook
        # handlers take, so an event racing this transaction cannot create
        # a duplicate channel.
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))', [sid])
        channel = self.env['connect.channel'].sudo().process_channel_event({
            'sid': sid,
            'technical_direction': 'outbound-api',
            'caller': callerId,
            'called': number,
            'status': 'initiated',
            'caller_pbx_user_id': connect_user.id,
        })
        channel.write({
            'infobip_originate_dest': number,
            'caller_user': user.id,
            'partner': partner_id,
        })

    def write(self, vals):
        if self.env.context.get('skip_protected_fields'):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in INFOBIP_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace('display_', ''): vals.get(
                            field_name
                        ),
                        field_name: '*' * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(
                skip_protected_fields=True
            ).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return res
