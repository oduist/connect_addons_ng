# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api

logger = logging.getLogger(__name__)


class BirdMessageTemplate(models.Model):
    """Approved WhatsApp message templates synced read-only from
    GET /v1/whatsapp/templates. Required to start a WhatsApp conversation
    outside the 24-hour customer-service window; templates are authored
    and approved in the Bird dashboard.
    """
    _name = 'connect.bird.message_template'
    _description = 'Bird Message Template'
    _rec_name = 'name'
    _order = 'name, locale'

    sid = fields.Char('Template ID', index=True, readonly=True)
    name = fields.Char(required=True, readonly=True)
    locale = fields.Char('Locale', readonly=True)
    status = fields.Char(readonly=True)
    category = fields.Char(readonly=True)
    variables = fields.Text(
        readonly=True,
        help='JSON list of template variable keys/descriptors.')
    body_preview = fields.Text(readonly=True)

    def get_variable_keys(self):
        self.ensure_one()
        try:
            keys = []
            for item in json.loads(self.variables or '[]'):
                if isinstance(item, dict) and item.get('key'):
                    keys.append(item['key'])
                elif isinstance(item, str):
                    keys.append(item)
            return keys
        except ValueError:
            return []

    @api.model
    def _map_remote_template(self, item):
        """GET /v1/whatsapp/templates item -> field values. The exact
        payload shape is confirmed against the live platform; all
        assumptions live here.
        """
        return {
            'sid': item.get('id'),
            'name': item.get('name') or item.get('id'),
            'locale': item.get('locale') or item.get('language'),
            'status': item.get('status'),
            'category': item.get('category'),
            'variables': json.dumps(item.get('variables') or []),
            'body_preview': (item.get('body') or item.get('text')
                             or item.get('preview') or ''),
        }

    @api.model
    def sync(self):
        """Upsert templates, drop vanished ones. Tolerates a missing
        whatsapp scope on the access key (logged, no failure).
        """
        settings = self.env['connect.settings']
        remote_sids = []
        found_any = False
        for item in settings.bird_paginate('/whatsapp/templates'):
            found_any = True
            values = self._map_remote_template(item)
            if not values['sid']:
                continue
            remote_sids.append(values['sid'])
            template = self.search([('sid', '=', values['sid'])], limit=1)
            if template:
                template.write(values)
            else:
                self.create(values)
        if not found_any:
            logger.warning('Bird WhatsApp templates sync returned nothing '
                           '(missing scope or no templates).')
            return True
        stale = self.search([('sid', 'not in', remote_sids)])
        if stale:
            stale.unlink()
        return True
