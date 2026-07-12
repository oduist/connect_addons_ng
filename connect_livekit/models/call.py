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
    livekit_agent = fields.Many2one(
        'connect.livekit.agent', readonly=True, ondelete='set null')

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
                self._livekit_after_channel_event(room_name, channel, event)
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

    def _livekit_after_channel_event(self, room_name, channel, event):
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
        elif room_name.startswith('did-'):
            self._livekit_notify_did_user(room_name, channel, event)

    def _livekit_notify_did_user(self, room_name, channel, event):
        """Ring (or stop ringing) the destination user's web phone for an
        inbound DID call."""
        number = self.env['connect.livekit.number'].get_number_for_room(
            room_name)
        if not number or number.destination != 'user' or not number.user:
            return
        pbx_user = number.user
        # Enrich the ledger: the trunk DID does not resolve to the user
        # by URI lookup.
        if not channel.called_pbx_user:
            channel.sudo().write({
                'called_pbx_user': pbx_user.id,
                'called_user': pbx_user.user.id if pbx_user.user else False,
            })
        if not pbx_user.user:
            return
        participant = (event.get('participant') or {})
        attrs = participant.get('attributes') or {}
        is_sip = bool(attrs.get('sip.callID')) or (
            participant.get('kind') == 'SIP')
        if not is_sip:
            return
        action = 'ring' if event.get('event') == 'participant_joined' \
            else 'hangup'
        self.env['bus.bus']._sendone(
            pbx_user.user.partner_id, 'connect_livekit.call', {
                'action': action,
                'room_name': room_name,
                'number': channel.caller,
                'partner_id': channel.partner.id or False,
                'partner_name': channel.partner.name or '',
            })

    @api.model
    def livekit_apply_agent_transcript(self, agent, payload):
        """Store an AI-agent conversation transcript delivered by the
        worker as a connect.recording (source='livekit-ai').

        The worker supplies the transcript and summary itself, so the
        recording bypasses the core OpenAI pipeline
        (skip_transcription, the Telnyx AI pattern)."""
        room_name = payload.get('room_name') or ''
        channel_sid = payload.get('channel_sid')
        call = self.sudo().search(
            [('livekit_room_name', '=', room_name)], limit=1) \
            if room_name else self.sudo().browse()
        if not call and channel_sid:
            channel = self.env['connect.channel'].sudo().search(
                [('sid', '=', channel_sid)], limit=1)
            call = channel.call
        lines = []
        for message in (payload.get('messages') or []):
            text = (message.get('text') or '').strip()
            if text:
                lines.append('{}: {}'.format(
                    message.get('role') or 'user', text))
        transcript = '\n'.join(lines)
        summary = (payload.get('summary') or '').strip()
        vals = {
            'sid': room_name,
            'source': 'livekit-ai',
            'status': 'completed',
            'transcript': transcript,
            'duration': int(payload.get('duration_secs') or 0),
        }
        if summary:
            vals['summary'] = summary
        if call:
            vals.update({
                'call': call.id,
                'channel': call.channels[:1].id,
                'partner': call.partner.id,
                'caller_number': call.caller,
                'called_number': call.called,
            })
        Recording = self.env['connect.recording'].sudo()
        rec = Recording.search(
            [('sid', '=', room_name), ('source', '=', 'livekit-ai')],
            limit=1)
        if rec:
            rec.with_context(tracking_disable=True).write(vals)
        else:
            rec = Recording.with_context(skip_transcription=True).create(
                vals)
        if call:
            call_vals = {'livekit_agent': agent.id}
            call.write(call_vals)
            if summary:
                call.summary = summary
        return rec.id

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
        # Stop a still-ringing web phone when the caller gave up.
        if room_name.startswith('did-'):
            number = self.env['connect.livekit.number'].get_number_for_room(
                room_name)
            if number and number.destination == 'user' and number.user.user:
                self.env['bus.bus']._sendone(
                    number.user.user.partner_id, 'connect_livekit.call',
                    {'action': 'hangup', 'room_name': room_name})
        # Force-close any channel the participant events missed, then run
        # the finalization once so the call registers in the chatter.
        open_channels = call.channels.filtered(
            lambda ch: ch.status not in CALL_END_STATUSES)
        if open_channels:
            open_channels.write({'status': 'completed'})
            self.process_call_event(open_channels[0])
