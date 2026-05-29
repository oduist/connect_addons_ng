# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.addons.connect.models.settings import debug
from odoo.addons.connect_twilio.models.twiml import pretty_xml
from twilio.twiml.voice_response import Dial, VoiceResponse

logger = logging.getLogger(__name__)


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    twilio_sip_host = fields.Char(
        string='ElevenLabs SIP Host',
        default='sip.rtc.elevenlabs.io',
        help="SIP host of the ElevenLabs inbound trunk. EL terminates "
             "inbound SIP on sip.rtc.elevenlabs.io (TLS:5061); the legacy "
             "sip.elevenlabs.io does not resolve.",
    )

    def render(self, request, params=None):
        self.ensure_one()
        if self.provider_id.code != 'twilio':
            return super().render(request, params=params)
        if not self.env['oduist.license'].check_license('connect_elevenlabs'):
            return (
                "<Response><Pause length='1'/>"
                "<Say>This is Oduist Connect. Your trial period is over. "
                "Please buy a license to continue.</Say>"
                "<Pause length='1'/></Response>"
            )
        channel_sid = request.get('CallSid')
        host = self.twilio_sip_host or 'sip.rtc.elevenlabs.io'
        response = VoiceResponse()
        dial = Dial()
        # EL accepts inbound SIP over TLS:5061 / TCP:5060 only — never UDP,
        # which is Twilio's <Sip> default. Force TLS transport explicitly
        # (Twilio routes `;transport=tls`; it ignores the `sips:` scheme).
        dial.sip(
            f"sip:{self.agent_uid}@{host}:5061;transport=tls"
            f"?X-Call-Sid={channel_sid}"
        )
        response.append(dial)
        debug(self, pretty_xml(response))
        return response

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        agent = self._resolve_transfer_agent(channel_sid)
        if not agent or agent.provider_id.code != 'twilio':
            return super().transfer(channel_sid=channel_sid, exten=exten)
        logger.info("Transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return "Not all parameters passed. You must provide channel_sid and exten (only digits)"
        exten_rec, err = agent._resolve_transfer_target(exten)
        if err:
            return err
        client = self.env['connect.provider.twilio.config'].sudo().get_client()
        channel = self.env['connect.channel'].search(
            [('sid', '=', channel_sid)], limit=1)
        twiml = exten_rec.render(
            {"Caller": channel.caller, "Called": channel.called, "CallSid": channel.sid}
        )
        debug(agent, "Transfer to: {}".format(pretty_xml(twiml)))
        client.calls(channel_sid).update(twiml=twiml)
        return "Transfer Successful"
