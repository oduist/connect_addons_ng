import logging
import re
from xml.etree import ElementTree as ET
from odoo import models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    def generate_dialplan(self, context_el, params):
        """Generate FreeSWITCH dialplan for inbound DID routing."""
        self.ensure_one()

        ext = ET.SubElement(context_el, 'extension',
            name='did_{}'.format(self.phone_number))
        condition = ET.SubElement(ext, 'condition',
            field='destination_number',
            expression='^{}$'.format(re.escape(self.phone_number)))

        ET.SubElement(condition, 'action', application='set',
            data='odoo_call_direction=inbound')
        ET.SubElement(condition, 'action', application='set',
            data='odoo_number_id={}'.format(self.id))

        # Route to destination
        if self.destination == 'user' and self.user:
            # Transfer to user's extension in default context
            user_number = self.user.exten_number or self.user.username
            ET.SubElement(condition, 'action', application='transfer',
                data='{} XML default'.format(user_number))
        elif self.destination == 'callflow' and self.callflow:
            # Transfer to callflow's extension in default context
            cf_number = self.callflow.exten_number or str(self.callflow.id)
            ET.SubElement(condition, 'action', application='transfer',
                data='{} XML default'.format(cf_number))
        else:
            ET.SubElement(condition, 'action', application='respond', data='404')
