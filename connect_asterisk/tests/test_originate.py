# -*- coding: utf-8 -*-
"""Click-to-call originate tests with a mocked agent."""
from unittest.mock import patch, MagicMock

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AsteriskTestCommon


def _agent_response(payload, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.text = str(payload)
    response.raise_for_status.return_value = None
    return response


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestOriginate(AsteriskTestCommon):

    def _originate(self, agent_payload=None, number='+1 555 123-4567',
                   **kwargs):
        payload = agent_payload or {'response': {'Response': 'Success'}}
        target = ('odoo.addons.connect_asterisk.models.settings'
                  '.requests.request')
        with patch(target, return_value=_agent_response(payload)) as mock:
            self.Settings.with_user(self.odoo_user).originate_call(
                number, **kwargs)
        return mock

    def test_originate_creates_outbound_channel(self):
        mock = self._originate()
        self.assertEqual(mock.call_count, 1)
        action = mock.call_args.kwargs['json']['action']
        self.assertEqual(action['Action'], 'Originate')
        self.assertEqual(action['Channel'], 'PJSIP/101')
        self.assertEqual(action['Exten'], '15551234567')
        self.assertEqual(action['Async'], 'true')
        channel = self.Channel.search([('sid', '=', action['ChannelId'])])
        self.assertTrue(channel)
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.status, 'queued')
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        self.assertEqual(channel.asterisk_channel, 'PJSIP/101')
        self.assertEqual(channel.call.direction, 'outgoing')

    def test_originate_uses_endpoint_context(self):
        self.endpoint.sudo().asterisk_originate_context = 'custom-ctx'
        mock = self._originate()
        action = mock.call_args.kwargs['json']['action']
        self.assertEqual(action['Context'], 'custom-ctx')

    def test_originate_bearer_header(self):
        mock = self._originate()
        headers = mock.call_args.kwargs['headers']
        self.assertTrue(headers['Authorization'].startswith('Bearer '))

    def test_newchannel_updates_pre_created_leg(self):
        mock = self._originate()
        action = mock.call_args.kwargs['json']['action']
        sid = action['ChannelId']
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', sid, channel='PJSIP/101-000a',
            caller='101', exten='15551234567'))
        channels = self.Channel.search([('sid', '=', sid)])
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels.technical_direction, 'outbound-api')
        self.assertEqual(channels.status, 'ringing')
        self.assertEqual(channels.call.direction, 'outgoing')

    def test_agent_error_marks_call_failed(self):
        mock = self._originate(agent_payload={
            'response': {'Response': 'Error',
                         'Message': 'Permission denied'}})
        action = mock.call_args.kwargs['json']['action']
        channel = self.Channel.search([('sid', '=', action['ChannelId'])])
        self.assertEqual(channel.status, 'failed')
        self.assertTrue(channel.call.has_error)
        self.assertIn('Permission denied', channel.call.error_message)

    def test_originate_response_failure_event(self):
        mock = self._originate()
        action = mock.call_args.kwargs['json']['action']
        sid = action['ChannelId']
        self.Channel.on_ami_originate_response_failure(self._ami_event(
            'OriginateResponse', sid, Response='Failure', Reason='0'))
        channel = self.Channel.search([('sid', '=', sid)])
        self.assertEqual(channel.status, 'failed')
        self.assertTrue(channel.call.has_error)
        # Success responses are ignored.
        self.assertFalse(self.Channel.on_ami_originate_response_failure(
            self._ami_event('OriginateResponse', 'x', Response='Success')))

    def test_originate_without_pbx_user_raises(self):
        user = self.env['res.users'].create({
            'name': 'No PBX', 'login': 'ast_no_pbx'})
        with self.assertRaises(UserError):
            self.Settings.with_user(user).originate_call('15551234567')

    def test_originate_without_enabled_endpoint_raises(self):
        self.endpoint.sudo().asterisk_originate_enabled = False
        with self.assertRaises(ValidationError):
            self._originate()

    def test_originate_empty_number_raises(self):
        with self.assertRaises(ValidationError):
            self.Settings.with_user(self.odoo_user).originate_call('')
