from odoo import fields, models


class CallflowChoice(models.Model):
    _name = 'connect.callflow_choice'
    _description = 'Callflow Choice'

    callflow = fields.Many2one('connect.callflow', required=True, ondelete='cascade')
    choice_digits = fields.Char(required=True)
    exten = fields.Many2one('connect.exten', ondelete='restrict', required=True)
    speech = fields.Char()
