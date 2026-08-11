# -*- coding: utf-8 -*-
import hashlib
import logging
from datetime import datetime, timezone

from odoo import api, fields, models

logger = logging.getLogger(__name__)

# Channel statuses that end a leg — replayed/out-of-order upserts must
# not resurrect a finished channel.
FINAL_STATUSES = ('completed', 'no-answer', 'busy', 'canceled', 'failed')


def _dt_from_epoch(value):
    """Naive-UTC datetime from an epoch float, or False."""
    try:
        return datetime.fromtimestamp(
            float(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return False


class Channel(models.Model):
    _inherit = 'connect.channel'

    threecx_callid = fields.Char(
        string='3CX Call ID', readonly=True, index=True)
    threecx_legid = fields.Char(string='3CX Leg ID', readonly=True)
    threecx_answered = fields.Datetime(readonly=True)

    # ------------------------------------------------------------------
    # Normalized participant events from the sidecar agent (ADR-035)
    # ------------------------------------------------------------------

    @api.model
    def _threecx_leg_kind(self, state, dn):
        """'outbound' or 'inbound' for a participant of a monitored DN.

        The Call Control participant fields are under-documented; the
        whole heuristic deliberately lives here, pinned by tests:
        a leg the DN originated (or that is Dialing out) is outbound,
        everything else is treated as inbound ringing/answered.
        """
        originated_by = str((state or {}).get('originated_by_dn') or '')
        if originated_by and originated_by == str(dn):
            return 'outbound'
        if (state or {}).get('status') == 'Dialing':
            return 'outbound'
        return 'inbound'

    @api.model
    def _threecx_sid(self, event):
        """Stable SID for a participant event: call+leg ids when the
        PBX provides them, else a hash of the entity path."""
        state = event.get('state') or {}
        callid = state.get('callid')
        legid = state.get('legid')
        if callid not in (None, '') and legid not in (None, ''):
            return '3cxcc-{}-{}'.format(callid, legid)
        entity = str(event.get('entity') or '')
        return '3cxcc-' + hashlib.sha1(entity.encode()).hexdigest()[:16]

    @api.model
    def on_threecx_participant_event(self, event):
        """Map one normalized agent event into the core pipeline."""
        if not isinstance(event, dict):
            return False
        kind = event.get('event')
        if kind not in ('upsert', 'remove'):
            return False
        state = event.get('state') or {}
        dn = str(event.get('dn') or '')
        sid = self._threecx_sid(event)
        existing = self.sudo().search([('sid', '=', sid)], limit=1)

        connect_user = self.env['connect.user'].sudo()
        if dn:
            connect_user = connect_user.search(
                [('threecx_exten', '=', dn)], limit=1)
        party = str(state.get('party_caller_id') or '')
        params = {'sid': sid}
        if self._threecx_leg_kind(state, dn) == 'outbound':
            params.update({
                'caller': dn,
                'called': party,
                'technical_direction': 'outbound-api',
            })
            if connect_user:
                params['caller_pbx_user_id'] = connect_user.id
        else:
            params.update({
                'caller': party,
                'called': dn,
                'technical_direction': 'inbound',
            })
            if connect_user:
                params['called_pbx_user_id'] = connect_user.id
        if existing:
            # Never flip the direction of a known leg (e.g. an
            # originate-pre-created outbound-api leg whose first upsert
            # arrives as Ringing).
            params['technical_direction'] = existing.technical_direction

        if kind == 'upsert':
            return self._threecx_apply_upsert(event, state, params,
                                              existing)
        return self._threecx_apply_remove(event, params, existing)

    @api.model
    def _threecx_apply_upsert(self, event, state, params, existing):
        if existing and existing.status in FINAL_STATUSES:
            # Replay / out-of-order after the leg already ended.
            return existing
        answered = state.get('status') == 'Connected'
        params['status'] = 'in-progress' if answered else 'ringing'
        if existing:
            params['duration'] = existing.duration
        channel = self.process_channel_event(params)
        updates = self._threecx_id_updates(channel, state)
        if answered and not channel.threecx_answered:
            updates['threecx_answered'] = _dt_from_epoch(
                event.get('answered_at')) or fields.Datetime.now()
        if updates:
            channel.write(updates)
        self.env['connect.call'].process_call_event(channel)
        return channel

    @api.model
    def _threecx_apply_remove(self, event, params, existing):
        answered_dt = existing.threecx_answered if existing else False
        if not answered_dt:
            answered_dt = _dt_from_epoch(event.get('answered_at'))
        end_dt = _dt_from_epoch(event.get('ts')) or datetime.now(
            timezone.utc).replace(tzinfo=None)
        if answered_dt:
            duration = max(int((end_dt - answered_dt).total_seconds()), 0)
            params.update({'status': 'completed', 'duration': duration})
        else:
            params.update({'status': 'no-answer', 'duration': 0})
        channel = self.process_channel_event(params)
        updates = self._threecx_id_updates(
            channel, event.get('state') or {})
        if answered_dt and not channel.threecx_answered:
            updates['threecx_answered'] = answered_dt
        if updates:
            channel.write(updates)
        self.env['connect.call'].process_call_event(channel)
        return channel

    @api.model
    def _threecx_id_updates(self, channel, state):
        updates = {}
        if state.get('callid') and not channel.threecx_callid:
            updates['threecx_callid'] = str(state['callid'])
        if state.get('legid') and not channel.threecx_legid:
            updates['threecx_legid'] = str(state['legid'])
        return updates
