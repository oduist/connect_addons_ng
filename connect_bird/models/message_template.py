# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import fields, models, api

logger = logging.getLogger(__name__)


class BirdMessageTemplate(models.Model):
    """Message templates synced read-only from the Bird platform.

    The platform is template-first: WhatsApp accepts ONLY template sends
    and free-form SMS is not generally available yet, so templates are
    the primary way to send. Two products are synced:

    - SMS templates (GET /v1/sms/templates): ``smt_`` ids, named typed
      variables ({{ code }}, {{ date_time }}, ...);
    - WhatsApp templates (GET /v1/whatsapp/templates): identified by
      name + language (no id), positional {{1}} placeholders in the
      body component.
    """
    _name = 'connect.bird.message_template'
    _description = 'Bird Message Template'
    _rec_name = 'name'
    _order = 'product, name, locale'

    sid = fields.Char('Template ID', index=True, readonly=True)
    product = fields.Selection([
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ], required=True, readonly=True, index=True)
    name = fields.Char(required=True, readonly=True)
    locale = fields.Char('Language', readonly=True)
    status = fields.Char(readonly=True)
    category = fields.Char(readonly=True)
    scope = fields.Char(readonly=True)
    variables = fields.Text(
        readonly=True,
        help='JSON list of template variable descriptors: '
             '[{"key", "type", "required", "constraint"}].')
    body_preview = fields.Text(readonly=True)

    def get_variable_keys(self):
        self.ensure_one()
        try:
            keys = []
            for item in json.loads(self.variables or '[]'):
                if isinstance(item, dict) and item.get('key'):
                    keys.append(str(item['key']))
                elif isinstance(item, str):
                    keys.append(item)
            return keys
        except ValueError:
            return []

    @api.model
    def _map_remote_sms_template(self, item):
        """GET /v1/sms/templates item -> field values."""
        languages = item.get('available_languages') or []
        return {
            'sid': item.get('id'),
            'product': 'sms',
            'name': item.get('name') or item.get('id'),
            'locale': languages[0] if languages else '',
            'status': item.get('status'),
            'category': item.get('category'),
            'scope': item.get('scope'),
            'variables': json.dumps(item.get('variables') or []),
            'body_preview': item.get('body') or '',
        }

    @api.model
    def _map_remote_whatsapp_template(self, item):
        """GET /v1/whatsapp/templates item -> field values.

        WhatsApp templates carry no id: name + language identify them.
        The body component uses positional {{1}} placeholders; the
        variable descriptors are derived from them.
        """
        name = item.get('name')
        language = item.get('language') or 'en'
        body_text = ''
        for component in item.get('components') or []:
            if component.get('type') == 'body':
                body_text = component.get('text') or ''
                break
        placeholders = sorted(
            {int(n) for n in re.findall(r'{{\s*(\d+)\s*}}', body_text)})
        variables = [
            {'key': str(n), 'type': 'text', 'required': True}
            for n in placeholders
        ]
        return {
            'sid': 'wa:{}:{}'.format(name, language),
            'product': 'whatsapp',
            'name': name,
            'locale': language,
            'status': item.get('status'),
            'category': item.get('category'),
            'scope': item.get('scope'),
            'variables': json.dumps(variables),
            'body_preview': body_text,
        }

    @api.model
    def sync(self):
        """Upsert templates of both products, drop vanished ones.
        Tolerates missing scopes on the access key (logged, no failure).
        """
        settings = self.env['connect.settings']
        found_any = False
        sources = [
            ('/sms/templates', self._map_remote_sms_template, 'sms'),
            ('/whatsapp/templates', self._map_remote_whatsapp_template,
             'whatsapp'),
        ]
        for path, mapper, product in sources:
            remote_sids = []
            params = {'limit': 100}
            failed = False
            while True:
                data = settings.bird_request(
                    'GET', path, params=params, raise_exc=False)
                if data is False:
                    logger.warning(
                        'Bird %s template sync failed; keeping existing '
                        '%s templates.', product, product)
                    failed = True
                    break
                items = data.get('data') or []
                if items:
                    found_any = True
                for item in items:
                    values = mapper(item)
                    if not values['sid'] or not values['name']:
                        continue
                    remote_sids.append(values['sid'])
                    template = self.search(
                        [('sid', '=', values['sid'])], limit=1)
                    if template:
                        template.write(values)
                    else:
                        self.create(values)
                cursor = data.get('next_cursor')
                if not cursor:
                    break
                params['starting_after'] = cursor
            if failed:
                continue
            if remote_sids:
                stale = self.search([
                    ('product', '=', product),
                    ('sid', 'not in', remote_sids),
                ])
            else:
                stale = self.search([('product', '=', product)])
            if stale:
                stale.unlink()
        if not found_any:
            logger.warning('Bird templates sync returned nothing '
                           '(missing scopes or no templates).')
            return True
        return True
