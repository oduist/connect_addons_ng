# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

logger = logging.getLogger(__name__)


class BirdWebhook(models.Model):
    """Registry of Bird webhook subscriptions provisioned by
    connect.settings.setup_bird_webhooks(). Kept for diagnostics and to
    make re-runs of the setup idempotent.
    """
    _name = 'connect.bird.webhook'
    _description = 'Bird Webhook Subscription'
    _rec_name = 'event'
    _order = 'event'

    sid = fields.Char('Subscription ID', readonly=True)
    service = fields.Char(default='channels', readonly=True)
    event = fields.Char(required=True, readonly=True)
    url = fields.Char(readonly=True)
    status = fields.Char(readonly=True)

    @api.model
    def setup_subscriptions(self, url, signing_key, events):
        """Create missing workspace-wide subscriptions; returns how many
        were created. Existing local rows are trusted (Bird has no public
        idempotency key for subscriptions, so re-creating blindly would
        duplicate deliveries).
        """
        settings = self.env['connect.settings']
        created = 0
        for event in events:
            existing = self.search([('event', '=', event)], limit=1)
            if existing and existing.url == url:
                continue
            res = settings.bird_request('POST', '/webhook-subscriptions', {
                'service': 'channels',
                'event': event,
                'url': url,
                'signingKey': signing_key,
            })
            values = {
                'sid': res.get('id'),
                'service': res.get('service', 'channels'),
                'event': event,
                'url': url,
                'status': res.get('status'),
            }
            if existing:
                # The endpoint URL changed: register anew and keep the
                # fresh subscription id locally. The stale remote
                # subscription (pointing to the old URL) must be removed
                # in the Bird dashboard; surface that to the admin.
                existing.write(values)
                settings.connect_notify(
                    'Bird subscription for {} re-created with a new URL. '
                    'Delete the old subscription in the Bird dashboard '
                    'if it still exists.'.format(event),
                    title='Webhooks Setup', sticky=True, warning=True)
            else:
                self.create(values)
            created += 1
        return created
