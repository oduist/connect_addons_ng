from odoo import fields, models


class Exten(models.Model):
    _inherit = 'connect.freeswitch.exten'

    dst = fields.Reference(
        selection_add=[('connect.pipecat.agent', 'AI Agent')],
    )
