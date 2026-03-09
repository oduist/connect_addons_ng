from odoo import models, fields


class PhoneWizard(models.TransientModel):
    _name = 'connect.transfer_wizard'
    _description = 'Transfer Wizard'

    phone_number = fields.Char(string='Phone Number', required=True)

    def action_confirm(self):
        return {'type': 'ir.actions.act_window_close'}
