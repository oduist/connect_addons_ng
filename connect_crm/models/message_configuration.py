from odoo import fields, models


class ConnectMessageConfiguration(models.Model):
    _inherit = 'connect.message_configuration'

    destination = fields.Selection(
        selection_add=[('crm.lead', 'CRM Lead')],
        ondelete={'crm.lead': 'set default'},
    )
