# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

RE_SIP_URI = re.compile(r'^(?:sips?|client):([^@]+)(?:@(.+))?$')


class User(models.Model):
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('asterisk', 'Asterisk')],
        ondelete={'asterisk': 'set null'},
    )
    # Asterisk numbering is owned by the customer's dialplan; Odoo mirrors
    # the user's extension as a plain string (no extension model).
    asterisk_exten_number = fields.Char(string='Asterisk Extension')
    asterisk_endpoint_ids = fields.One2many(
        'connect.asterisk.endpoint', 'connect_user_id', string='Asterisk Endpoints')
    asterisk_endpoint_count = fields.Integer(compute='_compute_asterisk_endpoint_count')
    asterisk_originate_vars = fields.Text(
        string='Originate Variables',
        help='Extra channel variables for click-to-call originate, '
             'one VAR=value per line.')
    phone_ring_volume = fields.Integer(default=100)
    mask_call_number = fields.Boolean(
        help='Mask the middle digits of phone numbers in the web phone.')
    call_popup_is_enabled = fields.Boolean(
        string='Call Popup', default=True)
    call_popup_is_sticky = fields.Boolean(string='Sticky Popup')

    def _compute_asterisk_endpoint_count(self):
        for rec in self:
            rec.asterisk_endpoint_count = len(rec.asterisk_endpoint_ids)

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['asterisk_exten_number']

    @api.model
    def get_user_by_uri(self, userinfo):
        """Match a SIP URI or a bare number to a connect.user.

        Accepts 'sip:101@pbx.example.com', 'client:101' or a bare '101':
        matches the SIP user of an Asterisk endpoint first, then the
        user extension number.
        """
        if not isinstance(userinfo, str) or not userinfo:
            return super().get_user_by_uri(userinfo)
        match = RE_SIP_URI.search(userinfo)
        name = match.group(1) if match else userinfo
        endpoint = self.env['connect.asterisk.endpoint'].sudo().search(
            [('asterisk_sip_user', '=', name)], limit=1)
        if endpoint and endpoint.connect_user_id:
            return endpoint.connect_user_id
        user = self.sudo().search([('asterisk_exten_number', '=', name)], limit=1)
        if user:
            return user
        return super().get_user_by_uri(userinfo)

    @api.model
    def search_pbx_users(self, search_query):
        """Search PBX users by name or extension for the web phone contacts."""
        has_group = self.env.user.has_group
        if not any([has_group('connect.group_user'),
                    has_group('connect.group_admin')]):
            raise ValidationError(
                'Only Connect users can search other Connect users!')
        domain = ['|', ('name', 'ilike', search_query),
                  ('asterisk_exten_number', 'ilike', search_query)]
        results = self.sudo().search_read(
            domain, ['id', 'name', 'asterisk_exten_number'],
            limit=10, order='asterisk_exten_number asc')
        # Keep the historical key used by the web phone contacts widget.
        for rec in results:
            rec['exten_number'] = rec.get('asterisk_exten_number') or ''
        return results

    def _get_asterisk_originate_vars(self):
        """Per-user extra channel variables for AMI Originate."""
        self.ensure_one()
        if not self.asterisk_originate_vars:
            return []
        return [line.strip() for line in
                self.asterisk_originate_vars.split('\n') if line.strip()]
