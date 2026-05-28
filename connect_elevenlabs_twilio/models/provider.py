"""Twilio bridge provider hooks (ADR-026)."""
from odoo import models


TWILIO_SIP_SIGNALING_IPS = (
    "54.172.60.0/23",
    "54.244.51.0/24",
    "54.171.127.192/30",
    "35.156.191.128/25",
    "35.162.40.0/23",
    "54.65.63.192/26",
    "54.169.127.128/26",
    "54.252.254.64/26",
    "177.71.206.192/26",
)


class ConnectProvider(models.Model):
    _inherit = 'connect.provider'

    def _elevenlabs_has_bridge(self):
        if self.code != 'twilio':
            return super()._elevenlabs_has_bridge()
        return True

    def _elevenlabs_default_inbound_ips(self):
        if self.code != 'twilio':
            return super()._elevenlabs_default_inbound_ips()
        return "\n".join(TWILIO_SIP_SIGNALING_IPS)
