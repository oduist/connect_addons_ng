# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


FS_GATEWAY_NAME = 'elevenlabs'
AUDIO_FORK_FORMAT = 'pcm_16000'  # ADR-016: pcm_16000 end-to-end for audio_stream


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    fs_transport = fields.Selection(
        [
            ('sip_trunk', 'SIP Trunk to ElevenLabs'),
            ('audio_fork', 'WebSocket via mod_audio_fork'),
        ],
        string='FreeSWITCH Transport',
        default='sip_trunk',
        required=True,
        help="How FreeSWITCH bridges the call to ElevenLabs. SIP Trunk uses a "
             "sofia gateway named '%s' provisioned with credentials from the "
             "ElevenLabs dashboard. Audio Fork (mod_audio_fork) is not yet "
             "implemented." % FS_GATEWAY_NAME,
    )

    @api.constrains('fs_transport', 'output_audio_format', 'user_input_audio_format')
    def _check_fs_transport_audio_format(self):
        """audio_fork requires pcm_16000 in both directions (ADR-016)."""
        for rec in self:
            if rec.fs_transport != 'audio_fork':
                continue
            if (rec.output_audio_format != AUDIO_FORK_FORMAT
                    or rec.user_input_audio_format != AUDIO_FORK_FORMAT):
                raise ValidationError(
                    "FreeSWITCH Audio Fork transport requires both "
                    "Output Audio Format and User Input Audio Format to be "
                    "'%s'. See ADR-016." % AUDIO_FORK_FORMAT
                )

    def generate_dialplan(self, params, exten=None):
        """Render FS dialplan that bridges the inbound call to ElevenLabs.

        Called from connect.exten.generate_dialplan when the extension's
        destination Reference points at this agent record.
        """
        self.ensure_one()
        if not exten:
            logger.warning(
                "generate_dialplan called for agent %s without exten", self.id)
            return ''
        if not self.agent_uid:
            logger.warning(
                "Agent %s has no agent_uid; cannot bridge", self.id)
            return ''

        Template = self.env['connect.freeswitch.template'].sudo()

        if self.fs_transport == 'sip_trunk':
            return Template.render('dialplan_elevenlabs_sip', {
                'extension_number': exten.number,
                'agent_uid': self.agent_uid,
                'gateway_name': FS_GATEWAY_NAME,
            })

        if self.fs_transport == 'audio_fork':
            relay_url = self.env['connect.settings'].sudo().get_param(
                'elevenlabs_agent_url') or ''
            wss_url = relay_url.replace('https://', 'wss://').replace(
                'http://', 'ws://').rstrip('/')
            if not wss_url:
                logger.warning(
                    "Agent %s uses audio_fork but elevenlabs_agent_url "
                    "is not configured", self.id)
                return ''
            return Template.render('dialplan_elevenlabs_audio_stream', {
                'extension_number': exten.number,
                'agent_uid': self.agent_uid,
                'wss_base_url': wss_url,
            })

        logger.warning(
            "Agent %s has unknown fs_transport=%s", self.id, self.fs_transport)
        return ''

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        """Transfer an active leg to a published Odoo extension via ESL.

        Called by the ElevenLabs `transfer_to_agent` tool webhook. For FS the
        channel_sid IS the FS channel UUID (see connect.channel.sid usage in
        connect_freeswitch).
        """
        logger.info(
            "FS transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return ("Not all parameters passed. You must provide "
                    "channel_sid and exten (only digits)")
        if isinstance(exten, str) and not exten.isalnum():
            return "Wrong extension format. Only digits, e.g. 101"

        self = self.sudo()
        channel = self.env['connect.channel'].search(
            [('sid', '=', channel_sid)], limit=1)
        if not channel:
            return "Channel %s not found" % channel_sid

        exten_rec = self.env['connect.exten'].search(
            [('number', '=', str(exten).strip())], limit=1)
        if not exten_rec:
            published = self.env['connect.exten'].search(
                [('is_published', '=', True)])
            if len(published) == 1:
                exten_rec = published
                logger.info(
                    "Extension %s not found; falling back to single published %s",
                    exten, exten_rec.number)
            elif published:
                available = ", ".join(
                    '<{}> "{}"'.format(p.number, p.dst.name if p.dst else '')
                    for p in published)
                return ("Extension {} not found. Available extensions: {}. "
                        "Please try again with a correct number.".format(
                            exten, available))
            else:
                return ("There is no public extension to connect the call. "
                        "Cannot transfer")

        result = self.env['connect.settings'].freeswitch_api(
            'uuid_transfer',
            '{} {} XML default'.format(channel.sid, exten_rec.number))
        if result is False:
            return "FreeSWITCH transfer failed (XML-RPC unreachable)"
        return "Transfer Successful"
