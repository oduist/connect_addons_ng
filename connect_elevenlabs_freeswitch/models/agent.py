# -*- coding: utf-8 -*-
import logging

from odoo import api, models

logger = logging.getLogger(__name__)


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    def generate_dialplan(self, params, exten=None):
        """Render FS dialplan that bridges the inbound call directly to
        the agent's ElevenLabs SIP endpoint over TLS (ADR-021).

        The SIP URI is fully self-contained — no connect.freeswitch.gateway
        record is involved. The user part is `el_virtual_number_uid`
        (EL's phone_number_id, provisioned when an extension is assigned)."""
        self.ensure_one()
        if self.provider_id.code != 'freeswitch':
            return super().generate_dialplan(params, exten=exten)
        if not exten:
            logger.warning(
                "generate_dialplan called for agent %s without exten", self.id)
            return ''
        if not self.agent_uid:
            logger.warning(
                "Agent %s has no agent_uid; cannot bridge", self.id)
            return ''
        if not self.el_virtual_number_uid:
            logger.warning(
                "Agent %s has no el_virtual_number_uid; cannot route to EL. "
                "Has an extension been assigned?", self.id)
            return ''
        Template = self.env['connect.freeswitch.template'].sudo()
        return Template.render('dialplan_elevenlabs_sip', {
            'extension_number': exten.number,
            'agent_uid': self.agent_uid,
            'el_virtual_number_uid': self.el_virtual_number_uid,
        })

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        agent = self._resolve_transfer_agent(channel_sid)
        if not agent or agent.provider_id.code != 'freeswitch':
            return super().transfer(channel_sid=channel_sid, exten=exten)
        logger.info("FS transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return ("Not all parameters passed. You must provide "
                    "channel_sid and exten (only digits)")
        exten_rec, err = agent._resolve_transfer_target(exten)
        if err:
            return err
        channel = self.env['connect.channel'].search(
            [('sid', '=', channel_sid)], limit=1)
        if not channel:
            return "Channel %s not found" % channel_sid
        result = self.env['connect.settings'].freeswitch_api(
            'uuid_transfer',
            '{} {} XML default'.format(channel.sid, exten_rec.number))
        if result is False:
            return "FreeSWITCH transfer failed (XML-RPC unreachable)"
        return "Transfer Successful"
