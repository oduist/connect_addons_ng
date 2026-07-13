# -*- coding: utf-8 -*-
import json
import uuid

from odoo import fields, models
from odoo.exceptions import ValidationError

from livekit import api as lk_api

from ..models.number import LIVEKIT_AGENT_NAME


class LivekitAICallWizard(models.TransientModel):
    _name = 'connect.livekit.ai_call_wizard'
    _description = 'Call with LiveKit AI Agent'

    agent = fields.Many2one(
        'connect.livekit.agent', required=True, ondelete='cascade')
    caller_id = fields.Many2one(
        'connect.livekit.outgoing_callerid', required=True)
    to_number = fields.Char(required=True)
    partner = fields.Many2one('res.partner', ondelete='set null')

    def action_call(self):
        self.ensure_one()
        settings = self.env['connect.settings']
        trunk = self.caller_id.trunk
        if not trunk.outbound_trunk_sid:
            trunk._push_outbound()
        if not trunk.outbound_trunk_sid:
            raise ValidationError(
                'The LiveKit outbound trunk is not configured!')
        number = self.to_number.strip()
        if not number.startswith('+'):
            number = '+{}'.format(number)
        room_name = 'ai-out-{}'.format(uuid.uuid4().hex[:8])
        dynamic_variables = {}
        if self.partner:
            dynamic_variables = {
                'customer_name': self.partner.display_name,
                'odoo_partner_id': str(self.partner.id),
                'customer_email': self.partner.email or '',
                'customer_language': self.partner.lang or '',
            }
        settings.livekit_api_call('room.create_room', lk_api.CreateRoomRequest(
            name=room_name, empty_timeout=300))
        # Put the agent into the room before the callee answers.
        settings.livekit_api_call(
            'agent_dispatch.create_dispatch',
            lk_api.CreateAgentDispatchRequest(
                agent_name=LIVEKIT_AGENT_NAME,
                room=room_name,
                metadata=json.dumps({
                    'agent_id': self.agent.id,
                    'dynamic_variables': dynamic_variables,
                }),
            ))
        info = settings.livekit_api_call(
            'sip.create_sip_participant',
            lk_api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk.outbound_trunk_sid,
                sip_call_to=number,
                sip_number=self.caller_id.number,
                room_name=room_name,
                participant_identity='sip-callee',
                participant_name=number,
                krisp_enabled=trunk.krisp_enabled,
            ))
        sid = getattr(info, 'sip_call_id', None) or getattr(
            info, 'participant_id', None)
        if sid:
            self.env['connect.channel'].sudo().create({
                'sid': sid,
                'technical_direction': 'outbound-api',
                'status': 'initiated',
                'caller': self.caller_id.number,
                'called': number,
                'partner': self.partner.id,
            })
        settings.connect_notify(
            'LiveKit AI call started.', title='AI Agent')
        return {'type': 'ir.actions.act_window_close'}
