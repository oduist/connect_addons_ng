"""FreeSWITCH bridge provider hooks (ADR-026)."""
from odoo import models


class ConnectProvider(models.Model):
    _inherit = 'connect.provider'

    def _elevenlabs_has_bridge(self):
        if self.code != 'freeswitch':
            return super()._elevenlabs_has_bridge()
        return True

    def _elevenlabs_default_inbound_ips(self):
        if self.code != 'freeswitch':
            return super()._elevenlabs_default_inbound_ips()
        return ''
