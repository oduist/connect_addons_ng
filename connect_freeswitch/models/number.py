import logging
import re
from odoo import fields, models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null')

    def write(self, vals):
        # ODU-12: when destination switches away from the FS provider, clear
        # the FS-specific destination pointer. The selection_add of
        # 'fs_fifo' on `destination` is gone — FS routes now via
        # destination='provider' + destination_provider_id == freeswitch.
        if 'destination_provider_id' in vals or 'destination' in vals:
            current_provider = vals.get('destination_provider_id', None)
            if vals.get('destination') and vals['destination'] != 'provider':
                vals.setdefault('fs_fifo_id', False)
            elif current_provider is False:
                vals.setdefault('fs_fifo_id', False)
        return super().write(vals)

    def _is_freeswitch_destination(self):
        return (self.destination == 'provider'
                and self.destination_provider_id
                and self.destination_provider_id.code == 'freeswitch')

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for inbound DID routing."""
        self.ensure_one()

        transfer_target = ''
        # `destination` reported to FS template kept as a friendly tag —
        # 'fs_fifo' is the legacy tag the dialplan branches on.
        dest_tag = self.destination
        if self.destination == 'user' and self.user:
            transfer_target = self.user.exten_number
        elif self.destination == 'callflow' and self.callflow:
            transfer_target = self.callflow.exten_number or str(self.callflow.id)
        elif self._is_freeswitch_destination() and self.fs_fifo_id:
            transfer_target = self.fs_fifo_id.exten_number or str(self.fs_fifo_id.id)
            dest_tag = 'fs_fifo'

        return self.env['connect.freeswitch.template'].render('dialplan_inbound_did', {
            'phone_number': re.escape(self.phone_number),
            'number_id': self.id,
            'destination': dest_tag,
            'transfer_target': transfer_target,
        })
