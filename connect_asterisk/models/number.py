# -*- coding: utf-8 -*-
from odoo import fields, models, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint


class Number(models.Model):
    """Minimal DID -> user map used by the dialplan-assist API.

    Inbound DIDs stay in the customer's Asterisk dialplan; this model only
    lets the dialplan resolve a DID to a Connect user via
    /asterisk/api/get_user_data_by_did.
    """
    _name = 'connect.asterisk.number'
    _description = 'Asterisk Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    user = fields.Many2one('connect.user', ondelete='set null')
    active = fields.Boolean(default=True)

    if release.version_info[0] >= 19:
        _phone_number_uniq = Constraint('UNIQUE(phone_number)', 'This number is already defined!')
    else:
        _sql_constraints = [
            ('phone_number_uniq', 'UNIQUE(phone_number)', 'This number is already defined!')
        ]
