# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.addons.connect.models.call import CALL_END_STATUSES
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# Q.850 hangup causes → core call status vocabulary, for channels that were
# never answered. An answered channel always ends 'completed'.
UNANSWERED_CAUSE_MAP = {
    '16': 'canceled',    # Normal Clearing before answer: caller gave up.
    '17': 'busy',
    '18': 'no-answer',   # No User Responding
    '19': 'no-answer',   # No Answer
    '21': 'busy',        # Call Rejected
    '26': 'canceled',    # Answered elsewhere (call pickup / queue)
}


def _event_time(event):
    """AMI EventTime → naive UTC datetime (Odoo convention).

    EventTime is an ISO-ish local string on Asterisk ≥ 12; the agent
    replaces it with a float epoch timestamp. Asterisk < 16 builds may
    omit it entirely — fall back to now.
    """
    value = event.get('EventTime')
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(
            tzinfo=None)
    return fields.Datetime.now()


class Channel(models.Model):
    _inherit = 'connect.channel'

    asterisk_channel = fields.Char(
        string='Asterisk Channel', readonly=True,
        help='Asterisk channel name, e.g. PJSIP/101-0000af.')
    asterisk_answered = fields.Datetime(
        string='Answered At', readonly=True)
    asterisk_recording_file = fields.Char(
        string='Recording File', readonly=True,
        help='MixMonitor file path reported by the VarSet AMI event.')

    @api.model
    def _asterisk_get(self, sid):
        return self.sudo().search([('sid', '=', sid)], limit=1,
                                  order='id asc')

    def _asterisk_update_params(self, status, duration=None):
        """Build process_channel_event params that update the status of an
        existing channel while preserving every other field (the core
        update path overwrites all keys it knows about)."""
        self.ensure_one()
        return {
            'sid': self.sid,
            'caller': self.caller,
            'called': self.called,
            'to': self.to,
            'technical_direction': self.technical_direction,
            'status': status,
            'duration': self.duration if duration is None else duration,
            'call_type': self.call_type or 'phone',
            'parent_sid': self.parent_sid,
        }

    def _asterisk_relink_orphans(self):
        """Link channels and recordings that arrived before this channel.

        Mirrors the FreeSWITCH provider: a secondary leg or a recording
        upload can reach Odoo before its parent channel exists.
        """
        self.ensure_one()
        orphan_channels = self.sudo().search([
            ('parent_sid', '=', self.sid),
            ('parent_channel', '=', False),
            ('id', '!=', self.id),
        ])
        for orphan in orphan_channels:
            orphan.parent_channel = self
            if orphan.call and self.call and orphan.call != self.call:
                old_call = orphan.call
                orphan.call = self.call
                # Use a fresh DB count instead of `old_call.channels`
                # because the One2many cache is not invalidated by the
                # inverse-side write above and still reports the moved
                # channel as belonging to old_call.
                remaining = self.sudo().search_count(
                    [('call', '=', old_call.id)])
                if not remaining:
                    old_call.unlink()
            debug(self, 'Linked orphan channel %s to parent %s' % (
                orphan.id, self.id))
        orphan_recordings = self.env['connect.recording'].sudo().search([
            ('call_sid', '=', self.sid),
            ('channel', '=', False),
        ])
        if orphan_recordings:
            orphan_recordings.write({
                'channel': self.id,
                'call': self.call.id if self.call else False,
                'partner': self.partner.id if self.partner else False,
                'duration': self.duration,
                'caller_number': self.caller_number,
                'called_number': self.called_number,
            })
            logger.info('Linked %d orphan recording(s) to channel %s',
                        len(orphan_recordings), self.sid)

    @api.model
    def on_ami_new_channel(self, event):
        """AMI Newchannel: create (or refresh) the channel and its call."""
        channel_name = event.get('Channel') or ''
        sid = event.get('Uniqueid')
        if not sid or channel_name.startswith('Local/'):
            return False
        linkedid = event.get('Linkedid')
        existing = self._asterisk_get(sid)
        if existing and existing.technical_direction == 'outbound-api':
            # Click-to-call leg pre-created by originate_call(): keep its
            # direction and numbers, just record progress and the channel.
            params = existing._asterisk_update_params('ringing')
            channel = self.process_channel_event(params)
            channel.sudo().asterisk_channel = channel_name
            self.env['connect.call'].process_call_event(channel)
            return channel.id

        endpoint = self.env['connect.asterisk.endpoint'].get_endpoint_by_channel(
            channel_name)
        connect_user = endpoint.connect_user_id if endpoint else None
        params = {
            'sid': sid,
            'caller': event.get('CallerIDNum') or '',
            'called': event.get('Exten') or '',
            'to': event.get('Exten') or '',
            'status': 'ringing',
            'call_type': 'phone',
        }
        if linkedid and linkedid != sid:
            # Secondary leg: a phone being dialed by the primary leg.
            params['technical_direction'] = 'outbound-dial'
            params['parent_sid'] = linkedid
            if connect_user:
                params['called_pbx_user_id'] = connect_user.id
                params['called'] = (connect_user.asterisk_exten_number
                                    or endpoint.asterisk_sip_user
                                    or params['called'])
        else:
            # Primary leg: an inbound call or an extension dialing out.
            params['technical_direction'] = 'inbound'
            if connect_user:
                params['caller_pbx_user_id'] = connect_user.id
        channel = self.process_channel_event(params)
        channel.sudo().asterisk_channel = channel_name
        self.env['connect.call'].process_call_event(channel)
        channel._asterisk_relink_orphans()
        return channel.id

    @api.model
    def on_ami_new_state(self, event):
        """AMI Newstate: only the 'Up' state is forwarded — answer."""
        if event.get('ChannelStateDesc') != 'Up':
            return False
        channel = self._asterisk_get(event.get('Uniqueid'))
        if not channel:
            debug(self, 'Newstate: channel %s not found, discarding.'
                  % event.get('Uniqueid'), level='warning')
            return False
        params = channel._asterisk_update_params('in-progress')
        channel = self.process_channel_event(params)
        channel.sudo().asterisk_answered = _event_time(event)
        self.env['connect.call'].process_call_event(channel)
        return channel.id

    @api.model
    def on_ami_new_connected_line(self, event):
        """AMI NewConnectedLine: refine missing/placeholder numbers."""
        channel = self._asterisk_get(event.get('Uniqueid'))
        if not channel:
            return False
        connected = event.get('ConnectedLineNum') or ''
        if not connected or connected == '<unknown>':
            return False
        data = {}
        if channel.called in (False, '', 's'):
            data['called'] = connected
        if channel.caller in (False, '', 's'):
            data['caller'] = connected
        if not data:
            return False
        channel.sudo().write(data)
        self.env['connect.call'].process_call_event(channel)
        return channel.id

    @api.model
    def on_ami_hangup(self, event):
        """AMI Hangup: final status, duration, call aggregation."""
        channel = self._asterisk_get(event.get('Uniqueid'))
        if not channel:
            logger.warning('Hangup: channel %s not found.',
                           event.get('Uniqueid'))
            return False
        if channel.status in CALL_END_STATUSES:
            # Replay or reconciler duplicate — already final.
            return channel.id
        answered = bool(channel.asterisk_answered) or \
            event.get('ChannelStateDesc') == 'Up'
        if answered and channel.asterisk_answered:
            duration = int((
                _event_time(event) - channel.asterisk_answered
            ).total_seconds())
            duration = max(duration, 0)
        else:
            duration = 0
        if answered:
            status = 'completed'
        else:
            status = UNANSWERED_CAUSE_MAP.get(
                str(event.get('Cause', '')), 'failed')
        params = channel._asterisk_update_params(status, duration=duration)
        channel = self.process_channel_event(params)
        self.env['connect.call'].process_call_event(channel)
        channel._asterisk_relink_orphans()
        return channel.id

    @api.model
    def on_ami_originate_response_failure(self, event):
        """AMI OriginateResponse with Response=Failure: click-to-call
        could not reach the user's phone."""
        if event.get('Response') != 'Failure':
            return False
        channel = self._asterisk_get(event.get('Uniqueid'))
        if not channel:
            debug(self, 'OriginateResponse: channel %s not found.'
                  % event.get('Uniqueid'))
            return False
        if channel.status in CALL_END_STATUSES:
            # Hangup already processed this leg.
            return channel.id
        reason = str(event.get('Reason', ''))
        if reason == '0':
            reason = 'Calling user SIP phone is not registered ' \
                     'or call declined.'
        params = channel._asterisk_update_params('failed')
        channel = self.process_channel_event(params)
        self.env['connect.call'].process_call_event(channel, error_data={
            'error_code': str(event.get('Reason', '')),
            'error_message': reason,
        })
        if channel.create_uid:
            self.env['connect.settings'].connect_notify(
                'Call to {} failed: {}'.format(channel.called or '', reason),
                notify_uid=channel.create_uid.id, warning=True)
        return channel.id

    @api.model
    def on_ami_var_set(self, event):
        """AMI VarSet for MIXMONITOR_FILENAME: remember the recording path."""
        if event.get('Variable') != 'MIXMONITOR_FILENAME':
            return False
        channel = self._asterisk_get(event.get('Uniqueid'))
        if not channel:
            logger.warning('VarSet: channel %s not found to set recording.',
                           event.get('Uniqueid'))
            return False
        channel.sudo().asterisk_recording_file = event.get('Value')
        return channel.id
