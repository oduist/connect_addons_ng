# -*- coding: utf-8 -*-
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# Bird call statuses -> core (Twilio-style) vocabulary. Statuses are
# normalized (underscores to dashes) before lookup; unknown values pass
# through unchanged. Verified against live voice events.
BIRD_CALL_STATUS_MAP = {
    'accepted': 'initiated',
    'created': 'initiated',
    'starting': 'initiated',
    'ringing': 'ringing',
    'ongoing': 'in-progress',
    'in-progress': 'in-progress',
    'answered': 'in-progress',
    'completed': 'completed',
    'no-answer': 'no-answer',
    'busy': 'busy',
    'failed': 'failed',
    'cancelled': 'canceled',
    'canceled': 'canceled',
}


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_bird_call_event(self, data, event_type):
        """Normalize a Bird voice event and upsert the channel."""
        debug(self, 'Bird {} event: {}'.format(event_type, data))
        params = self._map_bird_params(data, event_type)
        return self.process_channel_event(params)

    @api.model
    def _map_bird_params(self, data, event_type):
        """Bird voice event ``data`` -> process_channel_event() params.

        All payload-shape assumptions are centralized here so live-traffic
        fixes touch one place (the voice API is present on the platform
        but not yet publicly documented).
        """
        call_id = data.get('call_id') or data.get('id')
        caller = data.get('from')
        called = data.get('to')
        raw_status = str(data.get('status')
                         or event_type.split('.')[-1]).replace('_', '-')
        existing = self.sudo().search([('sid', '=', call_id)], limit=1)
        if existing and existing.technical_direction:
            # Keep 'outbound-api' on the leg pre-created by originate_call:
            # process_channel_event overwrites technical_direction on update.
            technical_direction = existing.technical_direction
        elif data.get('direction') in ('inbound', 'incoming'):
            technical_direction = 'inbound'
        else:
            technical_direction = 'outbound-dial'
        params = {
            'sid': call_id,
            'caller': caller,
            'called': called,
            'to': called,
            'technical_direction': technical_direction,
            'status': BIRD_CALL_STATUS_MAP.get(raw_status, raw_status),
            'duration': int(data.get('duration') or 0),
            'call_type': 'phone',
        }
        parent_sid = (data.get('parent_call_id') or data.get('parent_id')
                      or data.get('origin_call_id'))
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
