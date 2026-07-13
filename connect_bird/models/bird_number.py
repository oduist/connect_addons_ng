# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BirdNumber(models.Model):
    """Registry of Bird numbers / sender identities: every message send
    and call originate carries a ``from`` out of this registry. Synced
    read-only from GET /v1/numbers.
    """
    _name = 'connect.bird.number'
    _description = 'Bird Number'
    _order = 'number'

    sid = fields.Char('Number ID', index=True, readonly=True)
    number = fields.Char(
        'Number', required=True, index=True, readonly=True,
        help='E.164 number, alphanumeric sender ID or short code.')
    name = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    capabilities = fields.Char(
        readonly=True, help='Comma-separated: sms, whatsapp, voice, mms.')
    is_default = fields.Boolean(
        'Default',
        help='Default sender for outgoing messages and calls.')

    @api.depends('name', 'number')
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.name != rec.number:
                rec.display_name = '{} ({})'.format(rec.name, rec.number)
            else:
                rec.display_name = rec.number

    def has_capability(self, capability):
        self.ensure_one()
        if not self.capabilities:
            # Capabilities unknown (e.g. sparse API payload): do not block.
            return True
        return capability in [
            c.strip() for c in self.capabilities.split(',')]

    @api.model
    def get_default_number(self, capability=None):
        """Default number with the capability, else the first active one."""
        candidates = self.search([], order='is_default desc, id')
        for number in candidates:
            if number.status and number.status not in ('active', 'enabled'):
                continue
            if capability and not number.has_capability(capability):
                continue
            return number
        raise ValidationError(
            'No active Bird number{}. Run Sync in Bird Settings first!'.format(
                ' with {} capability'.format(capability) if capability else ''))

    @api.model
    def _map_remote_number(self, item):
        """GET /v1/numbers item -> field values. The exact payload shape
        is confirmed against the live platform; all assumptions live here.
        """
        capabilities = item.get('capabilities') or item.get('features') or []
        if isinstance(capabilities, str):
            capabilities = [capabilities]
        return {
            'sid': item.get('id'),
            'number': (item.get('number') or item.get('phone_number')
                       or item.get('identifier')),
            'name': item.get('name') or item.get('label'),
            'status': item.get('status'),
            'capabilities': ', '.join(
                str(c).lower() for c in capabilities),
        }

    @api.model
    def sync(self):
        """Upsert numbers from the Bird API, drop vanished ones."""
        settings = self.env['connect.settings']
        seen_numbers = []
        found_any = False
        for item in settings.bird_paginate('/numbers'):
            found_any = True
            values = self._map_remote_number(item)
            if not values['number']:
                continue
            seen_numbers.append(values['number'])
            record = self.search([('number', '=', values['number'])], limit=1)
            if record:
                record.write(values)
            else:
                self.create(values)
        if not found_any:
            logger.warning('Bird numbers sync returned nothing '
                           '(missing scope or no numbers).')
            return True
        stale = self.search([('number', 'not in', seen_numbers)])
        if stale:
            names = ', '.join(stale.mapped('number'))
            stale.unlink()
            settings.connect_notify(
                'Bird numbers removed (gone remotely): {}'.format(names),
                title='Bird Sync', sticky=True, warning=True)
        return True
