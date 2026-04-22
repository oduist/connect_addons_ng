import logging
import re
from odoo import fields, models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    destination = fields.Selection(
        selection_add=[('fs_fifo', 'FS Queue')],
        ondelete={'fs_fifo': 'set null'},
    )
    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null')

    def write(self, vals):
        if 'destination' in vals and vals['destination'] != 'fs_fifo':
            vals.setdefault('fs_fifo_id', False)
        return super().write(vals)

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for inbound DID routing."""
        self.ensure_one()

        transfer_target = ''
        if self.destination == 'user' and self.user:
            transfer_target = self.user.exten_number
        elif self.destination == 'callflow' and self.callflow:
            transfer_target = self.callflow.exten_number or str(self.callflow.id)
        elif self.destination == 'fs_fifo' and self.fs_fifo_id:
            transfer_target = self.fs_fifo_id.exten_number or str(self.fs_fifo_id.id)

        return self.env['connect.freeswitch.template'].render('dialplan_inbound_did', {
            'phone_number': re.escape(self.phone_number),
            'number_id': self.id,
            'destination': self.destination,
            'transfer_target': transfer_target,
        })
