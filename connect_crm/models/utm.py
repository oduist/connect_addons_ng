from odoo import fields, models, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint


class CallSource(models.Model):
    _inherit = 'utm.source'

    phone = fields.Char()

    if release.version_info[0] >= 19:
        _phone_uniq = Constraint(
            'UNIQUE(phone)', 'This phone number is already used!')
    else:
        _sql_constraints = [
            ('phone_uniq', 'UNIQUE(phone)', 'This phone number is already used!')
        ]
