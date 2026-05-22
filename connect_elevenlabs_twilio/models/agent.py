# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.addons.connect.models.settings import debug
from odoo.addons.connect_twilio.models.twiml import pretty_xml
from twilio.twiml.voice_response import Dial, VoiceResponse

logger = logging.getLogger(__name__)


# Twilio SIP signaling IP ranges (per Twilio Programmable Voice docs).
# Used as the default `el_inbound_allowed_ips` on agents when the
# Twilio bridge is installed (ADR-021).
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


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    twilio_sip_host = fields.Char(
        string='ElevenLabs SIP Host',
        default='sip.elevenlabs.io',
        help="SIP host of the ElevenLabs inbound trunk.",
    )
    el_inbound_allowed_ips = fields.Text(
        default="\n".join(TWILIO_SIP_SIGNALING_IPS),
    )

    def render(self, request, params=None):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_elevenlabs'):
            return (
                "<Response><Pause length='1'/>"
                "<Say>This is Oduist Connect. Your trial period is over. "
                "Please buy a license to continue.</Say>"
                "<Pause length='1'/></Response>"
            )
        channel_sid = request.get('CallSid')
        host = self.twilio_sip_host or 'sip.elevenlabs.io'
        response = VoiceResponse()
        dial = Dial()
        dial.sip(f"sip:{self.agent_uid}@{host}?X-Call-Sid={channel_sid}")
        response.append(dial)
        debug(self, pretty_xml(response))
        return response

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        logger.info("Transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return "Not all parameters passed. You must provide channel_sid and exten (only digits)"
        exten_rec, err = self._resolve_transfer_target(exten)
        if err:
            return err
        self = self.sudo()
        client = self.env['connect.settings'].get_client()
        channel = self.env['connect.channel'].search([('sid', '=', channel_sid)])
        twiml = exten_rec.render(
            {"Caller": channel.caller, "Called": channel.called, "CallSid": channel.sid}
        )
        debug(self, "Transfer to: {}".format(pretty_xml(twiml)))
        client.calls(channel_sid).update(twiml=twiml)
        return "Transfer Successful"
