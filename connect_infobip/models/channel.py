# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.call import CALL_END_STATUSES
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

INFOBIP_STATUS_MAP = {
    'CALL_RECEIVED': 'ringing',
    'CALL_RINGING': 'ringing',
    'CALL_PRE_ESTABLISHED': 'ringing',
    'CALL_ANSWERED': 'in-progress',
    'CALL_ESTABLISHED': 'in-progress',
    'CALL_FINISHED': 'completed',
}

INFOBIP_FAIL_MAP = {
    'NO_ANSWER': 'no-answer',
    'BUSY': 'busy',
    'REJECTED': 'busy',
    'DECLINED': 'busy',
    'CANCELED': 'canceled',
    'CANCELLED': 'canceled',
}


class Channel(models.Model):
    """Infobip adapter of the shared channel ledger.

    One Infobip call leg = one channel, keyed by sid = callId. Infobip has
    no parent-call concept, so parent_sid is synthesized by whoever creates
    the child leg and echoed through the leg's customData; ring-machine
    state lives on the parent (inbound) channel (ADR-036).
    """
    _inherit = 'connect.channel'

    infobip_leg = fields.Boolean(readonly=True)
    infobip_dialog_id = fields.Char(readonly=True)
    infobip_route_number = fields.Many2one(
        'connect.infobip.number', ondelete='set null')
    infobip_route_user = fields.Many2one(
        'connect.user', ondelete='set null')
    infobip_route_step = fields.Integer(default=0)
    infobip_originate_dest = fields.Char(readonly=True)
    infobip_pending_say = fields.Char()
    infobip_hangup_after_say = fields.Boolean()
    infobip_last_event_ts = fields.Char()

    @api.model
    def _infobip_event_call(self, event):
        """Extract the call object from an event envelope, defensively:
        the exact nesting must be confirmed live (ADR-036)."""
        properties = event.get('properties') or {}
        call = properties.get('call') or {}
        if not call and isinstance(event.get('call'), dict):
            call = event['call']
        return call

    @api.model
    def _map_infobip_params(self, event):
        """Map an Infobip voice event to the generic dict consumed by
        process_channel_event(). Returns None for non-status events."""
        call = self._infobip_event_call(event)
        custom = call.get('customData') or {}
        endpoint = call.get('endpoint') or {}
        etype = (event.get('type') or event.get('event') or '').upper()
        if etype == 'CALL_FAILED':
            code = ((event.get('properties') or {}).get('errorCode')
                    or call.get('errorCode') or {})
            if isinstance(code, str):
                code = {'name': code}
            status = INFOBIP_FAIL_MAP.get(
                (code.get('name') or '').upper(), 'failed')
        else:
            status = INFOBIP_STATUS_MAP.get(etype)
            if not status:
                return None

        def endpoint_address(ep):
            if (ep.get('type') or '').upper() == 'WEBRTC' and ep.get('identity'):
                # client:{identity}@infobip parses through the core
                # _get_channel_numbers regex and our get_user_by_uri.
                return 'client:{}@infobip'.format(ep['identity'])
            return ep.get('phoneNumber') or ep.get('identity') or ''

        direction = (call.get('direction') or '').upper()
        if direction == 'OUTBOUND':
            caller = call.get('from')
            called = endpoint_address(endpoint) or call.get('to')
            tech_dir = custom.get('technical_direction') or 'outbound-dial'
        else:
            if (endpoint.get('type') or '').upper() == 'WEBRTC':
                caller = endpoint_address(endpoint)
            else:
                caller = call.get('from')
            called = call.get('to')
            tech_dir = 'inbound'
        params = {
            'sid': event.get('callId') or call.get('id'),
            'caller': caller,
            'called': called,
            'to': call.get('to'),
            'technical_direction': tech_dir,
            'status': status,
            'call_type': 'phone',
        }
        # Trust duration only on terminal events; earlier events would
        # zero the counter (process_channel_event always writes it).
        if status in CALL_END_STATUSES:
            params['duration'] = int(call.get('duration') or 0)
        if custom.get('parent_sid'):
            params['parent_sid'] = custom['parent_sid']
        for key in ('caller_pbx_user_id', 'called_pbx_user_id'):
            if custom.get(key):
                try:
                    params[key] = int(custom[key])
                except (TypeError, ValueError):
                    pass
        return params

    @api.model
    def on_infobip_event(self, event):
        """Feed an Infobip status event into the shared ledger.

        Returns the channel, or an empty recordset when the event carries
        no callId. Guards: never downgrade a terminal status, drop stale
        events by timestamp (ISO-8601 strings compare correctly).
        """
        params = self._map_infobip_params(event)
        if params is None:
            sid = event.get('callId') or self._infobip_event_call(event).get('id')
            return self.sudo().search([('sid', '=', sid)], limit=1) if sid else self.browse()
        if not params.get('sid'):
            debug(self, 'Infobip event without callId dropped.', level='warning')
            return self.browse()
        channel = self.sudo().search([('sid', '=', params['sid'])], limit=1)
        ts = event.get('timestamp') or ''
        if channel:
            if (channel.status in CALL_END_STATUSES
                    and params['status'] not in CALL_END_STATUSES):
                debug(self, 'Dropping non-terminal event for ended channel {}.'.format(
                    channel.id))
                return channel
            if (ts and channel.infobip_last_event_ts
                    and ts < channel.infobip_last_event_ts):
                debug(self, 'Dropping stale event for channel {}.'.format(
                    channel.id))
                return channel
            if 'duration' not in params:
                params['duration'] = channel.duration
        channel = self.process_channel_event(params)
        vals = {'infobip_leg': True}
        if ts:
            vals['infobip_last_event_ts'] = ts
        channel.write(vals)
        return channel

    # --- REST leg actions -------------------------------------------------

    def infobip_answer_say_hangup(self, text):
        """Answer (when needed), say the text, hang up. The chain is driven
        by CALL_ESTABLISHED -> say and SAY_FINISHED -> hangup events."""
        self.ensure_one()
        self.write({
            'infobip_pending_say': text,
            'infobip_hangup_after_say': True,
        })
        if self.status == 'in-progress':
            self._infobip_flush_pending_say()
        else:
            try:
                self.env['connect.settings'].infobip_api_request(
                    'POST', '/calls/1/calls/{}/answer'.format(self.sid))
            except Exception as e:
                logger.warning('Answer failed for %s: %s', self.sid, e)

    def _infobip_flush_pending_say(self):
        self.ensure_one()
        if not self.infobip_pending_say:
            return
        text = self.infobip_pending_say
        self.infobip_pending_say = False
        try:
            self.env['connect.settings'].infobip_api_request(
                'POST', '/calls/1/calls/{}/say'.format(self.sid),
                {'text': text, 'language': 'en'})
        except Exception as e:
            logger.warning('Say failed for %s: %s', self.sid, e)
            if self.infobip_hangup_after_say:
                self._infobip_hangup()

    def _infobip_hangup(self):
        self.ensure_one()
        try:
            self.env['connect.settings'].infobip_api_request(
                'POST', '/calls/1/calls/{}/hangup'.format(self.sid))
        except Exception as e:
            logger.warning('Hangup failed for %s: %s', self.sid, e)

    def _infobip_create_dialog(self, endpoint, from_, custom_data,
                               connect_timeout=45, record=False,
                               called=None, called_pbx_user_id=None):
        """Bridge this leg to a new child leg via a Dialog.

        The platform keeps this leg ringing, answers it when the child
        answers, bridges media, and turns child no-answer/decline into
        CALL_FAILED + DIALOG_FAILED; the per-step timer is the platform's
        connectTimeout — no Odoo timers (ADR-036). Returns the child
        channel (may be empty when the response carries no child id yet).
        """
        self.ensure_one()
        Settings = self.env['connect.settings']
        cfg = Settings.sudo().get_param('infobip_calls_configuration_id')
        custom_data = dict(custom_data or {})
        custom_data.setdefault('parent_sid', self.sid)
        custom_data.setdefault('technical_direction', 'outbound-dial')
        child_request = {
            'endpoint': endpoint,
            'from': from_,
            'callsConfigurationId': cfg,
            'connectTimeout': connect_timeout,
            'customData': custom_data,
        }
        call_duration_limit = int(
            Settings.sudo().get_param('call_duration_limit') or 0)
        if call_duration_limit:
            child_request['maxDuration'] = call_duration_limit
        payload = {
            'parentCallId': self.sid,
            'childCallRequest': child_request,
        }
        if record:
            payload['recording'] = {'recordingType': 'AUDIO'}
        resp = Settings.infobip_api_request('POST', '/calls/1/dialogs', payload)
        dialog_id = resp.get('id')
        self.infobip_dialog_id = dialog_id
        child_sid = (resp.get('childCallId')
                     or (resp.get('childCall') or {}).get('id'))
        child_channel = self.browse()
        if child_sid:
            params = {
                'sid': child_sid,
                'technical_direction': custom_data['technical_direction'],
                'caller': from_,
                'called': called or endpoint.get('phoneNumber') or '',
                'status': 'initiated',
                'parent_sid': self.sid,
            }
            if called_pbx_user_id:
                params['called_pbx_user_id'] = called_pbx_user_id
            child_channel = self.sudo().process_channel_event(params)
            child_channel.write({
                'infobip_leg': True,
                'infobip_dialog_id': dialog_id,
            })
            self.env['connect.call'].process_call_event(child_channel)
        debug(self, 'Infobip dialog {} created: {} -> {}'.format(
            dialog_id, self.sid, child_sid))
        return child_channel

    # --- Ring machine -----------------------------------------------------

    def _infobip_start_user_ring(self, user):
        self.ensure_one()
        self.write({'infobip_route_user': user.id, 'infobip_route_step': 0})
        self._infobip_ring_step()

    def _infobip_ring_step(self):
        """Dial the current user_callflow step; called again by
        _infobip_advance_ring when the step's dialog fails."""
        self.ensure_one()
        if self.status in CALL_END_STATUSES:
            return
        user = self.infobip_route_user
        steps = self.env['connect.infobip.user_callflow'].sudo().search(
            [('user', '=', user.id)], order='prio')
        index = self.infobip_route_step
        if index >= len(steps):
            self._infobip_ring_exhausted()
            return
        step = steps[index]
        if step.callflow_type == 'phone':
            endpoint = {
                'type': 'PHONE',
                'phoneNumber': user.infobip_phone_number,
            }
            called = user.infobip_phone_number
            # A PSTN leg must present an owned DID as its from number.
            from_ = ((self.infobip_route_number.phone_number
                      if self.infobip_route_number else '')
                     or self._infobip_default_callerid())
        else:
            endpoint = {
                'type': 'WEBRTC',
                'identity': user.infobip_identity,
            }
            called = 'client:{}@infobip'.format(user.infobip_identity)
            from_ = self.caller_number or self.caller or ''
        custom_data = {
            'called_pbx_user_id': str(user.id),
            # Echoed back on the child's events: guards against advancing
            # the machine twice for one step (CALL_FAILED + DIALOG_FAILED).
            'route_step': str(index),
            # Shown by the web phone as the calling party.
            'From': (self.caller_number or self.caller or '').replace('+', ''),
        }
        if self.partner:
            custom_data['Partner'] = str(self.partner.id)
            custom_data['CallerName'] = self.partner.name
        elif self.caller_user:
            custom_data['CallerName'] = self.caller_user.name
        try:
            self._infobip_create_dialog(
                endpoint, from_, custom_data,
                connect_timeout=step.ring_timeout or 30,
                record=user.record_calls,
                called=called,
                called_pbx_user_id=user.id,
            )
        except Exception as e:
            logger.warning(
                'Ring step %s failed for %s: %s', index, self.sid, e)
            self.write({
                'infobip_route_step': index + 1,
                'infobip_dialog_id': False,
            })
            self._infobip_ring_step()

    def _infobip_advance_ring(self, step_index=None, dialog_id=None):
        """Advance to the next ring step, exactly once per failed step."""
        self.ensure_one()
        if self.status in CALL_END_STATUSES:
            return
        if not self.infobip_route_user:
            return
        current = self.infobip_route_step
        if step_index is not None:
            if step_index != current:
                return
        elif dialog_id:
            if dialog_id != self.infobip_dialog_id:
                return
        else:
            return
        self.write({
            'infobip_route_step': current + 1,
            'infobip_dialog_id': False,
        })
        self._infobip_ring_step()

    def _infobip_ring_exhausted(self):
        """All ring steps failed: recorded voicemail is deferred (ADR-036),
        so play the voicemail prompt or a generic apology and hang up."""
        self.ensure_one()
        user = self.infobip_route_user
        text = 'The user is unavailable. Please try again later. Goodbye!'
        if user and user.voicemail_enabled and user.voicemail_prompt:
            try:
                text = user.infobip_render_voicemail_prompt()
            except Exception:
                logger.exception('Voicemail prompt render error:')
        self.infobip_answer_say_hangup(text)

    def _infobip_bridge_external(self, number):
        """Forward the inbound leg to the number's external destination."""
        self.ensure_one()
        if (number.external_callerid_mode == 'caller'
                and self.caller_number):
            from_ = self.caller_number
        else:
            from_ = number.phone_number
        try:
            self._infobip_create_dialog(
                endpoint={
                    'type': 'PHONE',
                    'phoneNumber': number.external_number,
                },
                from_=from_,
                custom_data={},
                connect_timeout=45,
                called=number.external_number,
            )
        except Exception as e:
            logger.warning(
                'External bridge failed for %s: %s', self.sid, e)
            self.infobip_answer_say_hangup(
                'The call cannot be completed. Goodbye!')

    # --- Click-to-call / web phone continuation ----------------------------

    def _infobip_on_established(self):
        """React to CALL_ESTABLISHED on this leg: flush a queued say, or
        bridge the click-to-call destination once the agent answered."""
        self.ensure_one()
        if self.infobip_pending_say:
            self._infobip_flush_pending_say()
            return
        if self.infobip_originate_dest and not self.infobip_dialog_id:
            self._infobip_bridge_originate_dest()

    def _infobip_bridge_originate_dest(self):
        self.ensure_one()
        dest = self.infobip_originate_dest
        exten = self.env['connect.infobip.exten'].sudo().search(
            [('number', '=', dest)], limit=1)
        if exten and exten.dst and exten.dst._name == 'connect.user':
            self._infobip_start_user_ring(exten.dst)
            return
        try:
            self._infobip_create_dialog(
                endpoint={'type': 'PHONE', 'phoneNumber': dest},
                # self.caller holds the callerId resolved at originate time.
                from_=self.caller,
                custom_data={},
                connect_timeout=45,
                record=(self.caller_pbx_user.record_calls
                        if self.caller_pbx_user else False),
                called=dest,
            )
        except Exception as e:
            logger.warning(
                'Click-to-call bridge failed for %s: %s', self.sid, e)
            self.infobip_answer_say_hangup(
                'The call cannot be completed. Goodbye!')

    def _infobip_default_callerid(self):
        default = self.env['connect.infobip.outgoing_callerid'].sudo().search(
            [('is_default', '=', True)], limit=1)
        return default.number or ''

    # --- Webhook-loss safety net -------------------------------------------

    @api.model
    def infobip_close_stale(self):
        """Cron: reconcile long-non-terminal Infobip legs against the API
        and close the ones that ended without us seeing the webhook."""
        Settings = self.env['connect.settings']
        if not Settings.sudo().get_param('infobip_api_key'):
            return
        max_age = int(
            Settings.sudo().get_param('call_duration_limit') or 3600) + 900
        threshold = fields.Datetime.subtract(
            fields.Datetime.now(), seconds=max_age)
        stale = self.sudo().search([
            ('infobip_leg', '=', True),
            ('status', 'not in', CALL_END_STATUSES),
            ('create_date', '<', threshold),
        ], limit=20)
        for channel in stale:
            data = {}
            try:
                data = Settings.infobip_api_request(
                    'GET', '/calls/1/calls/{}'.format(channel.sid))
                state = (data.get('state') or '').upper()
                if state == 'FINISHED':
                    status = 'completed'
                elif state == 'FAILED':
                    status = 'failed'
                else:
                    continue
            except Exception as e:
                if '404' in str(e):
                    status = 'completed'
                else:
                    logger.warning(
                        'Stale check failed for %s: %s', channel.sid, e)
                    continue
            updated = self.sudo().process_channel_event({
                'sid': channel.sid,
                'caller': channel.caller,
                'called': channel.called,
                'to': channel.to,
                'technical_direction': channel.technical_direction,
                'status': status,
                'duration': int(data.get('duration')
                                or channel.duration or 0),
            })
            self.env['connect.call'].process_call_event(updated)
            debug(self, 'Stale Infobip channel {} closed as {}.'.format(
                channel.id, status))
