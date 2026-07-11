# -*- coding: utf-8 -*-
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# Bird call statuses → core (Twilio-style) vocabulary. 'accepted' and
# 'starting' precede ringing; 'cancelled' is the UK spelling of the core
# 'canceled' end status.
BIRD_CALL_STATUS_MAP = {
    'accepted': 'initiated',
    'starting': 'initiated',
    'ringing': 'ringing',
    'ongoing': 'in-progress',
    'completed': 'completed',
    'no-answer': 'no-answer',
    'busy': 'busy',
    'failed': 'failed',
    'cancelled': 'canceled',
}


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_bird_call_event(self, payload, event):
        """Normalize a Bird voice webhook payload and upsert the channel."""
        debug(self, 'Bird {} event: {}'.format(event, payload))
        params = self._map_bird_params(payload, event)
        return self.process_channel_event(params)

    @api.model
    def _map_bird_params(self, payload, event):
        """Bird call object → process_channel_event() params.

        All payload-shape assumptions are centralized here so live-traffic
        fixes touch one place.
        """
        caller = payload.get('from')
        called = payload.get('to')
        existing = self.sudo().search(
            [('sid', '=', payload.get('id'))], limit=1)
        if existing and existing.technical_direction:
            # Keep 'outbound-api' on the leg pre-created by originate_call:
            # process_channel_event overwrites technical_direction on update.
            technical_direction = existing.technical_direction
        elif (payload.get('direction') == 'incoming'
                or event == 'voice.inbound'):
            technical_direction = 'inbound'
        else:
            technical_direction = 'outbound-dial'
        params = {
            'sid': payload.get('id'),
            'caller': caller,
            'called': called,
            'to': called,
            'technical_direction': technical_direction,
            'status': BIRD_CALL_STATUS_MAP.get(
                payload.get('status'), payload.get('status')),
            'duration': int(payload.get('duration') or 0),
            'call_type': 'phone',
        }
        parent_sid = (payload.get('parentCallId') or payload.get('parentId')
                      or payload.get('originCallId'))
        if parent_sid:
            params['parent_sid'] = parent_sid
        # Match the agent leg of inbound calls / callback originates by the
        # agent phone number configured on the Connect user.
        agent = self.env['connect.user'].get_user_by_bird_number(called)
        if agent:
            params['called_pbx_user_id'] = agent.id
        caller_agent = self.env['connect.user'].get_user_by_bird_number(caller)
        if caller_agent:
            params['caller_pbx_user_id'] = caller_agent.id
        return params
