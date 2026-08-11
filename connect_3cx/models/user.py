# -*- coding: utf-8 -*-
from odoo import api, fields, models


class User(models.Model):
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('3cx', '3CX')],
        ondelete={'3cx': 'set null'},
    )
    # 3CX numbering is owned by the PBX; Odoo mirrors the user's extension
    # as a plain string so journal webhooks can resolve the agent.
    threecx_exten = fields.Char(string='3CX Extension')

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['threecx_exten']
