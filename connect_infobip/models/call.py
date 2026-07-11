# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from .settings import MAX_EXTEN_LEN, strip_number

logger = logging.getLogger(__name__)

# Failure codes that are normal ring outcomes, not call errors.
BENIGN_FAILURES = [
    'NO_ANSWER', 'BUSY', 'REJECTED', 'DECLINED', 'CANCELED', 'CANCELLED',
]

STATUS_EVENTS = [
    'CALL_RINGING', 'CALL_PRE_ESTABLISHED', 'CALL_ANSWERED',
    'CALL_ESTABLISHED', 'CALL_FINISHED', 'CALL_FAILED',
]

IGNORED_EVENTS = [
    'CALL_RECORDING_STARTED', 'CALL_RECORDING_FAILED',
    'DIALOG_RECORDING_STARTED', 'DIALOG_RECORDING_FAILED',
    'PLAY_FINISHED', 'DTMF_COLLECTED', 'MACHINE_DETECTION_FINISHED',
    'DIALOG_FINISHED', 'DIALOG_HANGUP',
]


class Call(models.Model):
    _inherit = 'connect.call'

    infobip_dialog_id = fields.Char(readonly=True)

    @api.model
    def on_infobip_voice_event(self, event, kind='event'):
        """Voice webhook dispatcher (ADR-035).

        Always returns True: errors are logged, never raised, so Infobip
        gets a 200 and does not retry-storm a failing handler.
        """
        try:
            self._dispatch_infobip_voice_event(event, kind)
        except Exception:
            logger.exception('Infobip voice event error:')
        return True

    @api.model
    def _dispatch_infobip_voice_event(self, event, kind):
        Channel = self.env['connect.channel']
        etype = (event.get('type') or event.get('event') or '').upper()
        call = Channel._infobip_event_call(event)
        call_id = event.get('callId') or call.get('id')
        debug(self, 'Infobip voice event {} for {}'.format(etype, call_id))
        if call_id:
            # Serialize all handlers of one leg: concurrent webhook workers
            # and our REST-create transactions take the same lock, so
            # upserts by sid cannot race into duplicates (ADR-035).
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s))', [call_id])

        if etype == 'CALL_RECEIVED':
            endpoint = call.get('endpoint') or {}
            if (endpoint.get('type') or '').upper() == 'WEBRTC':
                self._infobip_route_internal(event)
            else:
                self.env['connect.infobip.number'].route_call(event)
            return

        if etype in STATUS_EVENTS:
            channel = Channel.on_infobip_event(event)
            if not channel:
                return
            error_data = None
            if etype == 'CALL_FAILED':
                code = self._infobip_error_code(event)
                if (code.get('name')
                        and code['name'].upper() not in BENIGN_FAILURES):
                    error_data = {
                        'error_code': code.get('name') or code.get('id'),
                        'error_message': code.get('description'),
                    }
            self.process_call_event(channel, error_data)
            if etype == 'CALL_ESTABLISHED':
                channel._infobip_on_established()
            elif etype == 'CALL_FAILED':
                self._infobip_maybe_advance_parent(event, channel)
            return

        if etype in ('DIALOG_CREATED', 'DIALOG_ESTABLISHED'):
            self._infobip_record_dialog(event)
            return

        if etype == 'DIALOG_FAILED':
            dialog_id = (event.get('dialogId')
                         or (event.get('properties') or {}).get('dialogId'))
            if dialog_id:
                parent = Channel.sudo().search([
                    ('infobip_dialog_id', '=', dialog_id),
                    ('infobip_route_user', '!=', False),
                ], limit=1)
                if parent:
                    parent._infobip_advance_ring(dialog_id=dialog_id)
            return

        if etype == 'SAY_FINISHED':
            channel = Channel.sudo().search(
                [('sid', '=', call_id)], limit=1) if call_id else Channel
            if channel and channel.infobip_hangup_after_say:
                channel._infobip_hangup()
            return

        if etype in ('CALL_RECORDING_FINISHED', 'DIALOG_RECORDING_FINISHED',
                     'RECORDING_FINISHED'):
            self.env['connect.recording'].on_infobip_recording(event)
            return

        if etype in IGNORED_EVENTS:
            debug(self, 'Infobip event {} ignored (v1).'.format(etype))
            return

        debug(self, 'Unknown Infobip event type {}.'.format(etype),
              level='warning')

    @api.model
    def _infobip_error_code(self, event):
        properties = event.get('properties') or {}
        call = self.env['connect.channel']._infobip_event_call(event)
        for source in (properties, call):
            code = source.get('errorCode')
            if isinstance(code, dict):
                return code
            if isinstance(code, str):
                return {'name': code}
        return {}

    @api.model
    def _infobip_maybe_advance_parent(self, event, channel):
        """Advance the parent's ring machine when a routing child leg
        failed (no answer / busy / declined)."""
        parent = channel.parent_channel
        if not parent or not parent.infobip_route_user:
            return
        custom = (self.env['connect.channel']._infobip_event_call(event)
                  .get('customData') or {})
        step_index = None
        if custom.get('route_step') not in (None, ''):
            try:
                step_index = int(custom['route_step'])
            except (TypeError, ValueError):
                step_index = None
        parent._infobip_advance_ring(
            step_index=step_index,
            dialog_id=channel.infobip_dialog_id or None,
        )

    @api.model
    def _infobip_record_dialog(self, event):
        """Bookkeeping: stamp the dialog id on both legs and the call."""
        properties = event.get('properties') or {}
        dialog = properties.get('dialog') or {}
        dialog_id = (event.get('dialogId') or properties.get('dialogId')
                     or dialog.get('id'))
        if not dialog_id:
            return
        sids = [sid for sid in (
            dialog.get('parentCallId'), dialog.get('childCallId'),
            event.get('callId')) if sid]
        channels = self.env['connect.channel'].sudo().search(
            [('sid', 'in', sids)])
        if channels:
            channels.write({'infobip_dialog_id': dialog_id})
            calls = channels.mapped('call')
            if calls:
                calls.write({'infobip_dialog_id': dialog_id})

    @api.model
    def _infobip_route_internal(self, event):
        """CALL_RECEIVED from a WEBRTC endpoint: the web phone dialed the
        application (callApplication). Route by the number carried in
        customData.dialed_number."""
        Channel = self.env['connect.channel']
        call = Channel._infobip_event_call(event)
        endpoint = call.get('endpoint') or {}
        custom = call.get('customData') or {}
        identity = endpoint.get('identity') or call.get('from')
        caller_user = self.env['connect.user'].get_user_by_infobip_identity(
            identity)
        dialed = custom.get('dialed_number') or call.get('to') or ''
        channel = Channel.on_infobip_event(event)
        if not channel:
            return
        if caller_user and not channel.caller_pbx_user:
            channel.write({
                'caller_pbx_user': caller_user.id,
                'caller_user': (caller_user.user.id
                                if caller_user.user else False),
            })
        if dialed and not channel.called:
            channel.called = dialed
        self.process_call_event(channel)
        if not self.env['oduist.license'].check_license('connect', silent=True):
            channel.infobip_answer_say_hangup('Service unavailable.')
            return
        if not dialed:
            channel.infobip_answer_say_hangup('Unknown destination. Goodbye!')
            return
        exten = self.env['connect.infobip.exten'].sudo().search(
            [('number', '=', dialed)], limit=1)
        if exten and exten.dst and exten.dst._name == 'connect.user':
            channel._infobip_start_user_ring(exten.dst)
            return
        # External number: dial out with the agent's caller ID.
        dest = strip_number(dialed)
        if len(dest) > MAX_EXTEN_LEN:
            dest = '+{}'.format(dest)
        if caller_user and caller_user.infobip_outgoing_callerid:
            callerId = caller_user.infobip_outgoing_callerid.number
        else:
            callerId = channel._infobip_default_callerid()
        if not callerId:
            channel.infobip_answer_say_hangup(
                'No outgoing caller ID is configured. Goodbye!')
            return
        try:
            channel._infobip_create_dialog(
                endpoint={'type': 'PHONE', 'phoneNumber': dest},
                from_=callerId,
                custom_data={},
                connect_timeout=45,
                record=caller_user.record_calls if caller_user else False,
                called=dest,
            )
        except Exception as e:
            logger.warning(
                'Web phone external dial failed for %s: %s', channel.sid, e)
            channel.infobip_answer_say_hangup(
                'The call cannot be completed. Goodbye!')
