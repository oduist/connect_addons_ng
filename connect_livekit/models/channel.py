# -*- coding: utf-8 -*-
import logging

from odoo import api, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# LiveKit participant state → connect.channel status.
LIVEKIT_STATUS_BY_EVENT = {
    'participant_joined': 'in-progress',
    'participant_left': 'completed',
    'participant_connection_aborted': 'failed',
}


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def livekit_process_event(self, event):
        """Map a LiveKit participant event to process_channel_event().

        One LiveKit participant is one channel. SIP participants join on
        their ``sip.callID`` attribute so the click-to-call channel created
        by originate_call() is updated instead of duplicated; browser
        participants join on the participant SID.
        """
        etype = event.get('event')
        room = event.get('room') or {}
        participant = event.get('participant') or {}
        room_name = room.get('name') or ''
        attrs = participant.get('attributes') or {}
        identity = participant.get('identity') or ''
        sid = attrs.get('sip.callID') or participant.get('sid')
        if not sid:
            debug(self, 'LiveKit participant event without sid, skipped.')
            return False
        is_sip = bool(attrs.get('sip.callID')) or (
            participant.get('kind') == 'SIP')
        inbound = room_name.startswith('did-')

        params = {
            'sid': sid,
            'status': LIVEKIT_STATUS_BY_EVENT.get(etype, 'in-progress'),
            'call_type': 'phone',
        }
        if is_sip:
            # sip.phoneNumber is the remote party, sip.trunkPhoneNumber is
            # the DID/caller ID on our side of the trunk.
            phone = attrs.get('sip.phoneNumber') or ''
            trunk_phone = attrs.get('sip.trunkPhoneNumber') or ''
            if inbound:
                params.update({
                    'technical_direction': 'inbound',
                    'caller': phone,
                    'called': trunk_phone,
                    'to': trunk_phone,
                })
            else:
                # Outbound legs (out-/ai-out- rooms): keep the same values
                # originate_call() wrote so the upsert does not blank them.
                params.update({
                    'technical_direction': 'outbound-api',
                    'caller': trunk_phone,
                    'called': phone,
                    'to': phone,
                })
        else:
            # Browser/web participant: identity is user-<connect_user_id>
            # or guest-<random> (meet page).
            params.update({
                'technical_direction': 'inbound',
                'caller': identity,
                'called': '',
                'to': room_name,
            })
            if identity.startswith('user-'):
                try:
                    pbx_user_id = int(identity[5:])
                except ValueError:
                    pbx_user_id = False
                if pbx_user_id and self.env['connect.user'].sudo().browse(
                        pbx_user_id).exists():
                    params['caller_pbx_user_id'] = pbx_user_id

        # Parent linking: the first channel of the room is the parent of
        # every later participant so all legs roll up into one call.
        call = self.env['connect.call'].sudo().search(
            [('livekit_room_name', '=', room_name)], limit=1)
        if call and call.channels:
            first_sid = call.channels.sorted(key='id')[0].sid
            if first_sid and first_sid != sid:
                params['parent_sid'] = first_sid

        if etype == 'participant_left':
            duration = self._livekit_participant_duration(event, participant)
            if duration is not None:
                params['duration'] = duration

        return self.process_channel_event(params)

    @api.model
    def _livekit_participant_duration(self, event, participant):
        try:
            joined_at = int(participant.get('joinedAt') or 0)
            left_at = int(event.get('createdAt') or 0)
        except (TypeError, ValueError):
            return None
        if joined_at and left_at and left_at >= joined_at:
            return left_at - joined_at
        return None
