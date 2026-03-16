import logging
import re
from xml.etree import ElementTree as ET
from odoo import models

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _inherit = 'connect.exten'

    def generate_dialplan(self, context_el, params):
        """Generate FreeSWITCH dialplan XML for this extension."""
        self.ensure_one()
        if not self.dst:
            ext = ET.SubElement(context_el, 'extension', name='ext_{}'.format(self.number))
            condition = ET.SubElement(ext, 'condition',
                field='destination_number', expression='^{}$'.format(re.escape(self.number)))
            ET.SubElement(condition, 'action', application='respond', data='404')
            return

        self.dst.generate_dialplan(context_el, params, exten=self)
