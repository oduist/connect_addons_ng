# -*- coding: utf-8 -*-
import logging
import uuid

from odoo import api, models
from odoo.exceptions import AccessError, UserError

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def _freeswitch_clean_var(self, value):
        value = (value or '').strip()
        if value in ['_undef_', 'undefined', '-ERR', '-ERR no reply']:
            return ''
        if value.startswith('-ERR'):
            return ''
        return value

    @api.model
    def _freeswitch_getvar(self, call_id, name):
        result = self.env['connect.settings'].sudo().freeswitch_api(
            'uuid_getvar', '{} {}'.format(call_id, name))
        return self._freeswitch_clean_var(result)

    @api.model
    def _freeswitch_setvar(self, call_id, name, value):
        return self.env['connect.settings'].sudo().freeswitch_api(
            'uuid_setvar', '{} {} {}'.format(call_id, name, value or ''))

    @api.model
    def _freeswitch_check_result(self, result, action):
        if result is False or (isinstance(result, str)
                               and result.strip().startswith('-ERR')):
            raise UserError(
                'FreeSWITCH could not {} recording: {}'.format(
                    action, result or 'no response'))

    @api.model
    def _freeswitch_call_id(self, payload):
        call_id = (payload or {}).get('call_id') or (payload or {}).get('channel_sid')
        if not call_id:
            raise UserError('Missing active FreeSWITCH call identifier.')
        return call_id

    @api.model
    def _freeswitch_current_user_connect_id(self):
        connect_user = self.env.user.connect_user
        return str(connect_user.id) if connect_user else ''

    @api.model
    def _freeswitch_check_access(self, call_id):
        if self.env.user.has_group('connect.group_admin'):
            return True
        user_id = str(self.env.user.id)
        connect_user_id = self._freeswitch_current_user_connect_id()
        live_values = {
            'odoo_user_id': self._freeswitch_getvar(call_id, 'odoo_user_id'),
            'odoo_connect_user_id': self._freeswitch_getvar(
                call_id, 'odoo_connect_user_id'),
            'odoo_caller_pbx_user_id': self._freeswitch_getvar(
                call_id, 'odoo_caller_pbx_user_id'),
            'odoo_called_user_id': self._freeswitch_getvar(
                call_id, 'odoo_called_user_id'),
        }
        if live_values['odoo_user_id'] == user_id:
            return True
        if connect_user_id and connect_user_id in [
                live_values['odoo_connect_user_id'],
                live_values['odoo_caller_pbx_user_id'],
                live_values['odoo_called_user_id']]:
            return True
        raise AccessError('You can control recording only for your own calls.')

    @api.model
    def _freeswitch_default_recording_path(self, call_id):
        base_url = self.env['connect.settings'].sudo().get_recording_webhook_url()
        if not base_url:
            return ''
        return '{}/{}.wav'.format(base_url, call_id)

    @api.model
    def _freeswitch_recording_payload(self, call_id, state=None, path=None, error=''):
        if state is None:
            live_state = self._freeswitch_getvar(
                call_id, 'odoo_recording_state')
            state = live_state or 'off'
            if not live_state and self.env.user.connect_user.record_calls:
                state = 'on'
        if path is None:
            path = self._freeswitch_getvar(
                call_id, 'odoo_recording_path')
            if not path and state == 'on':
                path = self._freeswitch_default_recording_path(call_id)
        return {
            'supported': True,
            'state': state,
            'recording_ref': self._freeswitch_getvar(
                call_id, 'odoo_recording_ref'),
            'recording_path': path or '',
            'error': error or self._freeswitch_getvar(
                call_id, 'odoo_recording_error'),
            'channel_sid': call_id,
        }

    @api.model
    def _softphone_recording_state_freeswitch(self, payload):
        call_id = self._freeswitch_call_id(payload)
        self._freeswitch_check_access(call_id)
        return self._freeswitch_recording_payload(call_id)

    @api.model
    def _softphone_recording_start_freeswitch(self, payload):
        call_id = self._freeswitch_call_id(payload)
        self._freeswitch_check_access(call_id)
        base_url = self.env['connect.settings'].sudo().get_recording_webhook_url()
        if not base_url:
            raise UserError('FreeSWITCH recording webhook URL is not configured.')
        recording_ref = uuid.uuid4().hex
        path = '{}/{}__{}.wav'.format(base_url, call_id, recording_ref)
        self._freeswitch_setvar(call_id, 'odoo_recording_state', 'starting')
        self._freeswitch_setvar(call_id, 'odoo_recording_error', '')
        result = self.env['connect.settings'].sudo().freeswitch_api(
            'uuid_record', '{} start {}'.format(call_id, path))
        self._freeswitch_check_result(result, 'start')
        self._freeswitch_setvar(call_id, 'odoo_recording_state', 'on')
        self._freeswitch_setvar(call_id, 'odoo_recording_ref', recording_ref)
        self._freeswitch_setvar(call_id, 'odoo_recording_path', path)
        return self._freeswitch_recording_payload(
            call_id, state='on', path=path)

    @api.model
    def _softphone_recording_stop_freeswitch(self, payload):
        call_id = self._freeswitch_call_id(payload)
        self._freeswitch_check_access(call_id)
        path = (
            self._freeswitch_getvar(call_id, 'odoo_recording_path')
            or (payload or {}).get('recording_path')
            or self._freeswitch_default_recording_path(call_id)
        )
        if not path:
            raise UserError('No active FreeSWITCH recording path was found.')
        self._freeswitch_setvar(call_id, 'odoo_recording_state', 'stopping')
        self._freeswitch_setvar(call_id, 'odoo_recording_error', '')
        result = self.env['connect.settings'].sudo().freeswitch_api(
            'uuid_record', '{} stop {}'.format(call_id, path))
        self._freeswitch_check_result(result, 'stop')
        self._freeswitch_setvar(call_id, 'odoo_recording_state', 'off')
        self._freeswitch_setvar(call_id, 'odoo_recording_ref', '')
        self._freeswitch_setvar(call_id, 'odoo_recording_path', '')
        return self._freeswitch_recording_payload(
            call_id, state='off', path='')
