import logging
import re
from odoo import models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for inbound DID routing."""
        self.ensure_one()

        transfer_target = ''
        if self.destination == 'user' and self.user:
            transfer_target = self.user.exten_number or self.user.username
        elif self.destination == 'callflow' and self.callflow:
            transfer_target = self.callflow.exten_number or str(self.callflow.id)

        return self.env['connect.freeswitch.template'].render('dialplan_inbound_did', {
            'phone_number': re.escape(self.phone_number),
            'number_id': self.id,
            'destination': self.destination,
            'transfer_target': transfer_target,
        })
