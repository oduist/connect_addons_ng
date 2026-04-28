# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.addons.connect.models.settings import debug
from odoo.addons.connect_twilio.models.twiml import pretty_xml
from twilio.twiml.voice_response import Connect, Dial, VoiceResponse

logger = logging.getLogger(__name__)


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    twilio_transport = fields.Selection(
        [
            ('media_stream', 'Twilio Media Streams (WSS to relay)'),
            ('sip_trunk', 'Twilio SIP-bridge to ElevenLabs trunk'),
        ],
        string='Twilio Transport',
        default='media_stream',
        required=True,
        help="How Twilio bridges the call to ElevenLabs. Media Streams forks "
             "audio to our relay (full audio control). SIP Trunk hands the "
             "call directly to an ElevenLabs SIP trunk (no relay). See ADR-017.",
    )
    twilio_sip_host = fields.Char(
        string='ElevenLabs SIP Host',
        default='sip.elevenlabs.io',
        help="SIP host of the ElevenLabs inbound trunk. Used only when "
             "Twilio Transport is 'SIP Trunk'.",
    )

    def render(self, request, params={}):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_elevenlabs'):
            return (
                "<Response><Pause length='1'/>"
                "<Say>This is Oduist Connect. Your trial period is over. "
                "Please buy a license to continue.</Say>"
                "<Pause length='1'/></Response>"
            )
        channel_sid = request.get('CallSid')
        agent_uid = self.agent_uid

        if self.twilio_transport == 'sip_trunk':
            host = self.twilio_sip_host or 'sip.elevenlabs.io'
            response = VoiceResponse()
            dial = Dial()
            dial.sip(f"sip:{agent_uid}@{host}?X-Call-Sid={channel_sid}")
            response.append(dial)
            debug(self, pretty_xml(response))
            return response

        call_id = (
            self.env['connect.channel']
            .search([('sid', '=', channel_sid)], limit=1)
            .call.id
        )
        elevenlabs_agent_url = (
            self.env['connect.settings']
            .sudo()
            .get_param('elevenlabs_agent_url')
            .replace('https://', 'wss://')
        )
        connect = Connect()
        connect.stream(
            url=f"{elevenlabs_agent_url}/twilio/stream/{agent_uid}/{call_id}/{channel_sid}",
        )
        response = VoiceResponse()
        response.append(connect)
        debug(self, pretty_xml(response))
        return response

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        logger.info("Transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return "Not all parameters passed. You must provide channel_sid and exten (only digits)"
        if isinstance(exten, str) and not exten.isalnum():
            return "Wrong extension format. Only digits, e.g. 101"
        self = self.sudo()
        client = self.env['connect.settings'].get_client()
        channel = self.env['connect.channel'].search([('sid', '=', channel_sid)])
        exten_rec = self.env['connect.exten'].search(
            [('number', '=', str(exten).strip())]
        )
        if not exten_rec:
            published_extens = self.env['connect.exten'].search([('is_published', '=', True)])
            if published_extens:
                available = ", ".join(
                    ['<{}> "{}"'.format(k.number, k.dst.name if k.dst else '') for k in published_extens]
                )
                if len(published_extens) == 1:
                    exten_rec = published_extens[0]
                    logger.info(
                        "Extension %s not found, falling back to single published extension %s",
                        exten,
                        exten_rec.number,
                    )
                else:
                    return (
                        f"Extension {exten} not found. Available extensions: {available}. "
                        "Please try again with a correct number."
                    )
            else:
                return "There is no public extension to connect the call. Cannot transfer"
        exten = exten_rec
        twiml = exten.render(
            {
                "Caller": channel.caller,
                "Called": channel.called,
                "CallSid": channel.sid,
            }
        )
        debug(self, "Transfer to: {}".format(pretty_xml(twiml)))
        client.calls(channel_sid).update(twiml=twiml)
        return "Transfer Successful"
