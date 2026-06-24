from odoo import fields, models
from odoo.models import Constraint


class CallSource(models.Model):
    _inherit = 'utm.source'

    phone = fields.Char()

    _phone_uniq = Constraint('UNIQUE(phone)', 'This phone number is already used!')
