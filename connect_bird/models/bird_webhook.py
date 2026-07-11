# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

logger = logging.getLogger(__name__)


class BirdWebhook(models.Model):
    """Registry of the Bird webhook endpoint registered by
    connect.settings.setup_bird_webhooks(). Kept for diagnostics and to
    make re-runs of the setup idempotent (the signing secret is returned
    by Bird exactly once, so blind re-registration must be avoided).
    """
    _name = 'connect.bird.webhook'
    _description = 'Bird Webhook Endpoint'
    _rec_name = 'url'
    _order = 'id'

    sid = fields.Char('Endpoint ID', readonly=True)
    url = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    events = fields.Text('Subscribed Events', readonly=True)
