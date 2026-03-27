import logging
import re
from odoo import models

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _inherit = 'connect.exten'

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for this extension."""
        self.ensure_one()
        if not self.dst:
            return ('<extension name="ext_{number}">'
                    '<condition field="destination_number" expression="^{number}$">'
                    '<action application="respond" data="404"/>'
                    '</condition></extension>').format(number=re.escape(self.number))

        return self.dst.generate_dialplan(params, exten=self)
