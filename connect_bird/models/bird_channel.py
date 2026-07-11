# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BirdChannel(models.Model):
    """Registry of Bird channels (the config anchor of the Channels API):
    every message send and call originate targets a channelId.
    Synced read-only from GET /workspaces/{ws}/channels.
    """
    _name = 'connect.bird.channel'
    _description = 'Bird Channel'
    _order = 'platform_id, name'

    sid = fields.Char('Channel ID', required=True, index=True, readonly=True)
    name = fields.Char(required=True, readonly=True)
    platform_id = fields.Char('Platform', index=True, readonly=True)
    identifier = fields.Char('Number / Identifier', readonly=True)
    status = fields.Char(readonly=True)
    is_default = fields.Boolean(
        'Default',
        help='Default channel of its platform for outgoing messages/calls.')

    @api.depends('name', 'identifier')
    def _compute_display_name(self):
        for rec in self:
            if rec.identifier and rec.identifier != rec.name:
                rec.display_name = '{} ({})'.format(rec.name, rec.identifier)
            else:
                rec.display_name = rec.name

    @api.constrains('is_default', 'platform_id')
    def _check_single_default(self):
        for rec in self:
            if not rec.is_default:
                continue
            other = self.search([
                ('is_default', '=', True),
                ('platform_id', '=', rec.platform_id),
                ('id', '!=', rec.id),
            ], limit=1)
            if other:
                raise ValidationError(
                    'Only one default {} channel is allowed!'.format(
                        rec.platform_id))

    @api.model
    def get_default_channel(self, platform):
        """Default channel of the platform, else the first active one."""
        platforms = [platform] if isinstance(platform, str) else list(platform)
        channel = self.search([
            ('is_default', '=', True),
            ('platform_id', 'in', platforms),
        ], limit=1)
        if not channel:
            channel = self.search([
                ('status', '=', 'active'),
                ('platform_id', 'in', platforms),
            ], limit=1)
        if not channel:
            raise ValidationError(
                'No active Bird {} channel. Run Sync in Bird Settings '
                'first!'.format('/'.join(platforms)))
        return channel

    @api.model
    def sync(self):
        """Upsert channels from the Bird API, drop vanished ones."""
        settings = self.env['connect.settings']
        remote_sids = []
        page_token = None
        while True:
            params = {'limit': 100}
            if page_token:
                params['pageToken'] = page_token
            data = settings.bird_request('GET', '/channels', params=params)
            for item in data.get('results', data.get('channels', [])) or []:
                values = {
                    'sid': item.get('id'),
                    'name': item.get('name') or item.get('id'),
                    'platform_id': item.get('platformId'),
                    'identifier': item.get('identifier'),
                    'status': item.get('status'),
                }
                if not values['sid']:
                    continue
                remote_sids.append(values['sid'])
                channel = self.search([('sid', '=', values['sid'])], limit=1)
                if channel:
                    channel.write(values)
                else:
                    self.create(values)
            page_token = data.get('nextPageToken')
            if not page_token:
                break
        stale = self.search([('sid', 'not in', remote_sids)])
        if stale:
            names = ', '.join(stale.mapped('name'))
            stale.unlink()
            settings.connect_notify(
                'Bird channels removed (gone remotely): {}'.format(names),
                title='Bird Sync', sticky=True, warning=True)
        return True
