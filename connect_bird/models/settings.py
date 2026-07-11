# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import urljoin

import httpx

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

ODUIST_MODULES.append('connect_bird')


logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

# Bird developer platform (platform.bird.com). Regional hosts; the region
# is encoded in the access key prefix (bk_{region}_...).
BIRD_HOST_TEMPLATE = 'https://{region}.platform.bird.com'
BIRD_DEFAULT_REGION = 'eu1'

BIRD_PROTECTED_FIELDS = [
    'display_bird_access_key',
    'display_bird_webhook_signing_key',
]

# Events requested when registering the webhook endpoint. The SMS event
# names are published (SDK/webhooks guide); the inbound/voice/whatsapp
# names are asserted from the platform's naming convention and verified
# against the live API — _register_webhook_endpoint() falls back to the
# known-safe subset when the full list is rejected.
BIRD_WEBHOOK_EVENTS_SAFE = [
    'sms.accepted',
    'sms.sent',
    'sms.delivered',
    'sms.undelivered',
    'sms.failed',
    'sms.rejected',
    'sms.expired',
]
BIRD_WEBHOOK_EVENTS = BIRD_WEBHOOK_EVENTS_SAFE + [
    'sms.received',
    'whatsapp.received',
    'whatsapp.sent',
    'whatsapp.delivered',
    'whatsapp.failed',
    'voice.call.created',
    'voice.call.updated',
    'voice.call.completed',
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
    # the controller reads the signing secret via sudo() and is not affected.
    bird_access_key = fields.Char(groups="base.group_erp_manager")
    display_bird_access_key = fields.Char()
    # Signing secret (whsec_...) issued by Bird when the webhook endpoint
    # is registered. Returned by the API exactly once.
    bird_webhook_signing_key = fields.Char(groups="base.group_erp_manager")
    display_bird_webhook_signing_key = fields.Char()
    bird_verify_requests = fields.Boolean(
        default=True, string='Verify Bird Requests')
    bird_signature_tolerance = fields.Integer(
        default=300, string='Signature Timestamp Tolerance (seconds)')
    bird_sms_category = fields.Char(
        default='transactional', string='SMS Category',
        help='Content classification sent with outgoing SMS '
             '(e.g. transactional, marketing, authentication). Controls '
             'opt-out policy and compliance on the Bird side.')
    bird_ring_timeout = fields.Integer(
        default=30, string='Agent Ring Timeout (seconds)',
        help='How long Bird rings the agent phone on click-to-call.')

    @api.model
    def _get_bird_base_url(self):
        """Regional API base. The region is taken from the access key
        prefix (bk_{region}_...); ir.config_parameter connect.bird_api_url
        overrides the whole base for debugging.
        """
        override = self.env['ir.config_parameter'].sudo().get_param(
            'connect.bird_api_url')
        if override:
            return override.rstrip('/')
        access_key = self.sudo().get_param('bird_access_key') or ''
        match = re.match(r'^bk_([a-z0-9]+)_', access_key)
        region = match.group(1) if match else BIRD_DEFAULT_REGION
        return BIRD_HOST_TEMPLATE.format(region=region)

    @api.model
    def bird_request(self, method, path, payload=None, params=None,
                     timeout=15, raise_exc=True):
        """Single entry point for Bird platform API calls.

        ``path`` is relative to /v1, e.g. '/sms/messages'. Returns the
        decoded JSON body ({} for empty responses) or False when the
        request failed and ``raise_exc`` is not set.
        """
        access_key = self.sudo().get_param('bird_access_key')
        if not access_key:
            raise ValidationError('Set Bird access key first!')
        url = '{}/v1{}'.format(self._get_bird_base_url(), path)
        headers = {
            'Authorization': 'Bearer {}'.format(access_key),
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
            # Platform errors: {"code": "...", "message": "..."}; some
            # endpoints return {"errors": [{...}]} lists.
            if isinstance(data, dict):
                if data.get('message'):
                    return '{} ({})'.format(data['message'], res.status_code)
                errors = data.get('errors') or []
                details = '; '.join(
                    filter(None, [e.get('message') or e.get('code')
                                  for e in errors if isinstance(e, dict)]))
                if details:
                    return '{} ({})'.format(details, res.status_code)
        except ValueError:
            pass
        return '{} {}'.format(res.status_code, (res.text or '')[:200])

    @api.model
    def bird_paginate(self, path, params=None):
        """Iterate a cursor-paginated collection (data / next_cursor)."""
        params = dict(params or {})
        params.setdefault('limit', 100)
        while True:
            data = self.bird_request('GET', path, params=params,
                                     raise_exc=False)
            if data is False:
                return
            for item in data.get('data') or []:
                yield item
            cursor = data.get('next_cursor')
            if not cursor:
                return
            params['starting_after'] = cursor

    def sync(self):
        if not self.sudo().get_param('bird_access_key'):
            raise ValidationError('You must set the Bird access key!')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        self.env['connect.bird.number'].sync()
        self.env['connect.bird.message_template'].sync()
        self.connect_notify(
            'Bird account synced successfully', title='Sync Complete')

    def _register_webhook_endpoint(self, url, events):
        """POST /v1/webhooks with a fallback to the known-safe event
        subset when the platform rejects event names it does not know.
        Returns the created endpoint object (with the one-time secret).
        """
        res = self.bird_request('POST', '/webhooks', {
            'url': url,
            'events': events,
        }, raise_exc=False)
        if res is False and events != BIRD_WEBHOOK_EVENTS_SAFE:
            logger.warning(
                'Bird webhook registration with the full event list '
                'failed; retrying with the known-safe SMS subset.')
            res = self.bird_request('POST', '/webhooks', {
                'url': url,
                'events': BIRD_WEBHOOK_EVENTS_SAFE,
            })
        elif res is False:
            raise ValidationError(
                'Bird webhook registration failed, check the Odoo log.')
        return res

    def setup_bird_webhooks(self):
        """Register the single webhook endpoint (idempotent).

        Bird returns the signing secret (whsec_...) exactly once, in the
        creation response — it is stored on connect.settings immediately.
        """
        self.ensure_one()
        api_url = self.sudo().get_param('api_url')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        url = urljoin(api_url, 'bird/webhook')
        existing = self.env['connect.bird.webhook'].search(
            [('url', '=', url)], limit=1)
        if existing and self.sudo().get_param('bird_webhook_signing_key'):
            self.connect_notify(
                'Bird webhook endpoint already registered for this URL.',
                title='Webhooks Setup')
            return
        res = self._register_webhook_endpoint(url, BIRD_WEBHOOK_EVENTS)
        secret = res.get('secret')
        if secret:
            self.sudo().with_context(skip_protected_fields=True).set_param(
                'bird_webhook_signing_key', secret)
            self.sudo().with_context(skip_protected_fields=True).set_param(
                'display_bird_webhook_signing_key', '*' * len(secret))
        values = {
            'sid': res.get('id'),
            'url': url,
            'status': res.get('status'),
            'events': ', '.join(res.get('events') or []),
        }
        if existing:
            existing.write(values)
        else:
            self.env['connect.bird.webhook'].create(values)
        self.connect_notify(
            'Bird webhook endpoint registered ({} events).'.format(
                len(res.get('events') or [])),
            title='Webhooks Setup')

    @api.model
    def _build_bird_originate_payload(self, agent_number, from_number,
                                      destination, record, notification_url):
        """Two-leg callback originate: dial the agent first, then connect
        to the destination. Isolated in one builder because the voice API
        request shape is confirmed against the live platform
        (POST /v1/voice/calls is present but not yet publicly documented).
        """
        payload = {
            'to': agent_number,
            'from': from_number,
            'connect_to': destination,
            'ring_timeout': int(self.sudo().get_param('bird_ring_timeout') or 30),
            'max_duration': int(self.sudo().get_param('call_duration_limit')),
            'record': bool(record),
        }
        if notification_url:
            payload['notification_url'] = notification_url
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
        from_number = (connect_user.bird_voice_number
                       or self.env['connect.bird.number'].get_default_number('voice'))
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
            connect_user.bird_phone_number, from_number.number, number,
            connect_user.record_calls, notification_url)
        debug(self, 'Bird originate payload: {}'.format(payload))
        res = self.bird_request('POST', '/voice/calls', payload)
        # Pre-create the agent leg so the voice webhooks update it instead
        # of creating a technical_direction-less duplicate. The destination
        # is stored at once: the bridged leg may arrive as a separate call
        # object without a guaranteed parent linkage.
        ch = self.env['connect.channel'].sudo().process_channel_event({
            'sid': res.get('id'),
            'caller': from_number.number,
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
