# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from odoo.addons.connect.models.call import CALL_END_STATUSES
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# Room-name prefixes tracked in the ledger (ADR-037). Other rooms on the
# same LiveKit server are ignored.
LIVEKIT_ROOM_PREFIXES = ('meet-', 'did-', 'out-', 'ai-out-')


class Call(models.Model):
    _inherit = 'connect.call'

    livekit_room_name = fields.Char(readonly=True, index=True)

    @api.model
    def _livekit_is_tracked_room(self, room_name):
        return bool(room_name) and room_name.startswith(LIVEKIT_ROOM_PREFIXES)

    @api.model
    def on_livekit_webhook(self, event):
        """Dispatch one LiveKit webhook event (parsed JSON body).

        Handlers are idempotent upserts: LiveKit retries failed deliveries
        and events can arrive out of order (participant_joined before
        room_started, upload before egress_ended).
        """
        etype = event.get('event')
        room_name = (
            (event.get('room') or {}).get('name')
            or (event.get('egressInfo') or {}).get('roomName') or '')
        if not self._livekit_is_tracked_room(room_name):
            debug(self, 'LiveKit {} for foreign room "{}" ignored.'.format(
                etype, room_name))
            return False
        if etype in ('participant_joined', 'participant_left',
                     'participant_connection_aborted'):
            channel = self.env['connect.channel'].livekit_process_event(event)
            if channel:
                self._livekit_after_channel_event(room_name, channel)
            return True
        if etype == 'room_started':
            self._livekit_on_room_started(event)
            return True
        if etype == 'room_finished':
            self._livekit_on_room_finished(event)
            return True
        if etype in ('egress_started', 'egress_updated', 'egress_ended'):
            self.env['connect.recording'].on_livekit_egress(event)
            return True
        debug(self, 'Unhandled LiveKit event: {}'.format(etype))
        return False

    def _livekit_after_channel_event(self, room_name, channel):
        call_id = self.process_call_event(channel)
        if not call_id:
            return
        call = self.sudo().browse(call_id)
        if not call.livekit_room_name:
            call.livekit_room_name = room_name
        if room_name.startswith('meet-'):
            room = self.env['connect.livekit.room'].sudo().search(
                [('room_name', '=', room_name)], limit=1)
            if room:
                if not room.call:
                    room.call = call.id
                if room.partner and not call.partner:
                    call.partner = room.partner

    def _livekit_on_room_started(self, event):
        room_data = event.get('room') or {}
        room_name = room_data.get('name')
        if not room_name or not room_name.startswith('meet-'):
            return
        room = self.env['connect.livekit.room'].sudo().search(
            [('room_name', '=', room_name)], limit=1)
        if room:
            vals = {'state': 'active'}
            if room_data.get('sid'):
                vals['sid'] = room_data['sid']
            room.write(vals)

    def _livekit_on_room_finished(self, event):
        room_name = (event.get('room') or {}).get('name')
        if not room_name:
            return
        if room_name.startswith('meet-'):
            room = self.env['connect.livekit.room'].sudo().search(
                [('room_name', '=', room_name)], limit=1)
            if room:
                room.write({'state': 'finished', 'egress_sid': False})
        call = self.sudo().search(
            [('livekit_room_name', '=', room_name)], limit=1)
        if not call:
            return
        # Force-close any channel the participant events missed, then run
        # the finalization once so the call registers in the chatter.
        open_channels = call.channels.filtered(
            lambda ch: ch.status not in CALL_END_STATUSES)
        if open_channels:
            open_channels.write({'status': 'completed'})
            self.process_call_event(open_channels[0])
