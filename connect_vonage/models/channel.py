# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from .settings import to_e164

logger = logging.getLogger(__name__)

# Vonage per-leg statuses mapped to the core (Twilio-vocabulary) statuses
# expected by connect.call.process_call_event / CALL_END_STATUSES.
VONAGE_STATUS_MAP = {
    'started': 'initiated',
    'ringing': 'ringing',
    'answered': 'in-progress',
    'human': 'in-progress',
    'machine': 'in-progress',
    'completed': 'completed',
    'busy': 'busy',
    'cancelled': 'canceled',
    'timeout': 'no-answer',
    'unanswered': 'no-answer',
    'rejected': 'failed',
    'failed': 'failed',
}

# Statuses of a synchronous connect event that mean the leg did not end in
# a normal conversation — the user callflow must advance (e.g. voicemail).
VONAGE_FAIL_STATUSES = [
    'busy', 'cancelled', 'timeout', 'unanswered', 'rejected', 'failed',
]


class Channel(models.Model):
    _inherit = 'connect.channel'

    # Vonage sends no parent leg reference; legs of one call share a
    # conversation_uuid, which is the only correlation key available.
    conversation_uuid = fields.Char(index=True, readonly=True)

    @api.model
    def on_voice_event(self, params):
        """Vonage webhook adapter: map event params and delegate to core."""
        debug(self, 'On voice event: %s' % json.dumps(params, indent=2))
        generic = self._map_vonage_params(params)
        if not generic:
            return self.env['connect.channel']
        channel = self.process_channel_event(generic)
        if (channel and params.get('conversation_uuid')
                and not channel.conversation_uuid):
            channel.sudo().conversation_uuid = params['conversation_uuid']
        return channel

    @api.model
    def _vonage_endpoint_to_uri(self, value):
        """Normalize a Vonage from/to value to a core-parsable URI/number.

        App (Client SDK) legs are reported as bare user names; core
        expects client:<user>@<domain> URIs (see connect.channel
        _get_channel_numbers and connect.user.get_user_by_uri).
        """
        if isinstance(value, dict):
            endpoint_type = value.get('type')
            if endpoint_type == 'app':
                return 'client:{}@vonage'.format(value.get('user') or '')
            if endpoint_type == 'phone':
                return to_e164(value.get('number') or '')
            if endpoint_type == 'sip':
                return value.get('uri') or ''
            return value.get('number') or value.get('user') or ''
        if not isinstance(value, str) or not value:
            return ''
        if re.match(r'^\d+$', value):
            return to_e164(value)
        if value.startswith('sip:') or value.startswith('client:'):
            return value
        # A bare non-numeric value is a Client SDK user name.
        return 'client:{}@vonage'.format(value)

    @api.model
    def _map_vonage_params(self, params):
        """Map a Vonage voice event to the generic channel event dict.

        Returns None for payloads that are not per-leg status events.
        """
        uuid = params.get('uuid')
        raw_status = params.get('status')
        if not uuid or not raw_status:
            return None
        status = VONAGE_STATUS_MAP.get(raw_status, raw_status)
        caller = self._vonage_endpoint_to_uri(params.get('from'))
        called = self._vonage_endpoint_to_uri(params.get('to'))
        generic = {
            'sid': uuid,
            'status': status,
            'duration': int(params.get('duration') or 0),
        }
        existing = self.sudo().search([('sid', '=', uuid)], limit=1)
        if existing:
            # Do not let sparse event payloads wipe values set at
            # pre-create time (originate_call / client-originated legs).
            generic['caller'] = caller or existing.caller
            generic['called'] = called or existing.called
            generic['to'] = called or existing.to
            generic['technical_direction'] = existing.technical_direction
        else:
            generic['caller'] = caller
            generic['called'] = called
            generic['to'] = called
            if params.get('direction') == 'outbound':
                generic['technical_direction'] = 'outbound-dial'
            else:
                generic['technical_direction'] = 'inbound'
            # Resolve the parent leg by conversation_uuid: the earliest
            # known leg of the conversation is the originating one.
            conversation_uuid = params.get('conversation_uuid')
            if conversation_uuid:
                parent = self.sudo().search(
                    [('conversation_uuid', '=', conversation_uuid),
                     ('sid', '!=', uuid)],
                    limit=1, order='id asc')
                if parent:
                    generic['parent_sid'] = parent.sid
        return generic

    def transfer(self, to=None):
        self.ensure_one()
        logger.warning(
            'Call transfer is not implemented in the Vonage module yet.')
