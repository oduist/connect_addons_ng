# -*- coding: utf-8 -*-
import logging
import re
import secrets
from urllib.parse import urljoin

import httpx

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

ODUIST_MODULES.append('connect_bird')


logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

BIRD_API_BASE = 'https://api.bird.com'

BIRD_PROTECTED_FIELDS = [
    'display_bird_access_key',
    'display_bird_webhook_signing_key',
]

# Events provisioned by setup_bird_webhooks(). All share the same endpoint;
# the controller dispatches on the envelope "event" key.
BIRD_WEBHOOK_EVENTS = [
    'sms.inbound',
    'sms.outbound',
    'whatsapp.inbound',
    'whatsapp.outbound',
    'voice.inbound',
    'voice.outbound',
]


def strip_number(number):
    """Strip number formatting"""
    if not isinstance(number, str):
        return number
    pattern = r"[\s\(\)\-\+]"
    return re.sub(pattern, "", number).lstrip("0")


class Settings(models.Model):
    _inherit = 'connect.settings'

    # Never grant this to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members. Signature validation in
    # the controller reads the signing key via sudo() and is not affected.
    bird_access_key = fields.Char(groups="base.group_erp_manager")
    display_bird_access_key = fields.Char()
    bird_workspace_id = fields.Char(string='Bird Workspace ID')
    bird_webhook_signing_key = fields.Char(groups="base.group_erp_manager")
    display_bird_webhook_signing_key = fields.Char()
    bird_verify_requests = fields.Boolean(
        default=True, string='Verify Bird Requests')
    bird_signature_tolerance = fields.Integer(
        default=300, string='Signature Timestamp Tolerance (seconds)')
    bird_ring_timeout = fields.Integer(
        default=30, string='Agent Ring Timeout (seconds)',
        help='How long Bird rings the agent phone on click-to-call (3-120).')

    @api.model
    def bird_request(self, method, path, payload=None, params=None,
                     timeout=15, raise_exc=True):
        """Single entry point for Bird API calls.

        ``path`` is relative to the workspace, e.g. '/channels/{id}/messages'.
        Returns the decoded JSON body ({} for empty responses) or False when
        the request failed and ``raise_exc`` is not set.
        """
        access_key = self.sudo().get_param('bird_access_key')
        workspace_id = self.sudo().get_param('bird_workspace_id')
        if not (access_key and workspace_id):
            raise ValidationError('Set Bird access key and workspace ID first!')
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'connect.bird_api_url', BIRD_API_BASE)
        url = '{}/workspaces/{}{}'.format(base_url, workspace_id, path)
        headers = {
            'Authorization': 'AccessKey {}'.format(access_key),
            'Content-Type': 'application/json',
        }
        try:
            res = httpx.request(
                method, url, json=payload, params=params,
                headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            message = 'Bird API connection error: {}'.format(e)
            logger.error(message)
            if raise_exc:
                raise ValidationError(message)
            return False
        debug(self, 'Bird {} {} -> {}'.format(method, path, res.status_code))
        if res.status_code in (200, 201, 202, 204):
            if not res.content:
                return {}
            try:
                return res.json()
            except ValueError:
                return {}
        message = self._format_bird_error(res)
        logger.error('Bird API error: %s %s -> %s', method, path, message)
        if raise_exc:
            raise ValidationError('Bird API error: {}'.format(message))
        return False

    @staticmethod
    def _format_bird_error(res):
        """Compact human message from a Bird error response."""
        try:
            data = res.json()
            errors = data.get('errors') or []
            details = '; '.join(
                filter(None, [e.get('message') or e.get('code')
                              for e in errors if isinstance(e, dict)]))
            if details:
                return '{} ({})'.format(details, res.status_code)
        except ValueError:
            pass
        return '{} {}'.format(res.status_code, (res.text or '')[:200])

    def sync(self):
        if not (self.sudo().get_param('bird_access_key')
                and self.sudo().get_param('bird_workspace_id')):
            raise ValidationError('You must set Bird access key and workspace ID!')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        self.env['connect.bird.channel'].sync()
        self.env['connect.bird.message_template'].sync()
        self.connect_notify(
            'Bird account synced successfully', title='Sync Complete')

    def setup_bird_webhooks(self):
        """Provision workspace-wide webhook subscriptions (idempotent).

        Subscriptions carry no channelId filters so newly synced channels
        do not require re-subscription.
        """
        self.ensure_one()
        api_url = self.sudo().get_param('api_url')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        signing_key = self.sudo().get_param('bird_webhook_signing_key')
        if not signing_key:
            signing_key = secrets.token_urlsafe(32)
            self.sudo().with_context(skip_protected_fields=True).set_param(
                'bird_webhook_signing_key', signing_key)
            self.sudo().with_context(skip_protected_fields=True).set_param(
                'display_bird_webhook_signing_key', '*' * len(signing_key))
        url = urljoin(api_url, 'bird/webhook')
        created = self.env['connect.bird.webhook'].setup_subscriptions(
            url, signing_key, BIRD_WEBHOOK_EVENTS)
        self.connect_notify(
            'Bird webhooks configured: {} created, {} already in place.'.format(
                created, len(BIRD_WEBHOOK_EVENTS) - created),
            title='Webhooks Setup')

    @api.model
    def _build_bird_originate_payload(self, agent_number, destination,
                                      record, notification_url):
        """Two-leg callback originate: dial the agent first, then bridge
        to the destination. Isolated in one builder because the exact
        bridge options shape is confirmed against the live API.
        """
        payload = {
            'to': agent_number,
            'ringTimeout': int(self.sudo().get_param('bird_ring_timeout') or 30),
            'maxDuration': int(self.sudo().get_param('call_duration_limit')),
            'record': bool(record),
            'callFlow': [{
                'command': 'bridge',
                'options': {
                    'to': destination,
                },
            }],
        }
        if notification_url:
            payload['notification'] = {'url': notification_url}
        return payload

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None,
                       **kwargs):
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Bird.
        if self._get_originate_provider(user) != 'bird':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user,
                **kwargs)
        self.env['oduist.license'].check_license('connect', silent=False)
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = '+{}'.format(number)
        if not user:
            user = self.env.user
        connect_user = user.connect_user
        if not connect_user:
            raise ValidationError('User is not a Connect user!')
        if not connect_user.bird_phone_number:
            raise ValidationError(
                'Set the agent phone number (Bird) on the Connect user!')
        channel = (connect_user.bird_voice_channel
                   or self.env['connect.bird.channel'].get_default_channel('voice'))
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        if res_model == 'res.partner' and obj:
            partner_id = res_id
        elif obj and hasattr(obj, 'partner_id') and obj.partner_id:
            partner_id = obj.partner_id.id
        elif obj and hasattr(obj, 'partner') and obj.partner:
            partner_id = obj.partner.id
        api_url = self.sudo().get_param('api_url')
        notification_url = urljoin(api_url, 'bird/webhook')
        payload = self._build_bird_originate_payload(
            connect_user.bird_phone_number, number,
            connect_user.record_calls, notification_url)
        debug(self, 'Bird originate payload: {}'.format(payload))
        res = self.bird_request(
            'POST', '/channels/{}/calls'.format(channel.sid), payload)
        # Pre-create the agent leg so the voice webhooks update it instead
        # of creating a technical_direction-less duplicate. The destination
        # is stored at once: the bridged leg may arrive as a separate call
        # object without a guaranteed parent linkage.
        ch = self.env['connect.channel'].sudo().process_channel_event({
            'sid': res['id'],
            'caller': channel.identifier,
            'called': number,
            'to': connect_user.bird_phone_number,
            'technical_direction': 'outbound-api',
            'status': 'initiated',
            'caller_pbx_user_id': connect_user.id,
        })
        if partner_id and not ch.partner:
            ch.partner = partner_id
        self.env['connect.call'].sudo().process_call_event(ch)

    def write(self, vals):
        if self.env.context.get('skip_protected_fields'):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in BIRD_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace('display_', ''): vals.get(field_name),
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
