# -*- coding: utf-8 -*-
"""Shared fixtures for connect_asterisk tests."""
import time

from odoo.tests import TransactionCase, new_test_user

AGENT_TOKEN = 'test-agent-token-0123456789abcdef'


class AsteriskTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        cls.Channel = cls.env['connect.channel']
        cls.Call = cls.env['connect.call']
        cls.Settings.set_param('asterisk_agent_token', AGENT_TOKEN)
        cls.odoo_user = new_test_user(
            cls.env, login='ast_user_101', groups='base.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({
                'user': cls.odoo_user.id,
                'asterisk_exten_number': '101',
                'originate_provider': 'asterisk',
            })
        cls.endpoint = cls.env['connect.asterisk.endpoint'].create({
            'name': 'Office phone 101',
            'connect_user_id': cls.connect_user.id,
            'asterisk_channel': 'PJSIP/101',
            'asterisk_sip_transport': 'udp',
        })
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'Asterisk Test Partner',
                'phone': '+15551234567',
            })

    @classmethod
    def _ami_event(cls, event, uniqueid, channel='PJSIP/101-0000af', **kw):
        """Build an AMI-shaped event dict as the agent forwards it."""
        data = {
            'Event': event,
            'Uniqueid': uniqueid,
            'Linkedid': kw.pop('linkedid', uniqueid),
            'Channel': channel,
            'CallerIDNum': kw.pop('caller', '101'),
            'Exten': kw.pop('exten', ''),
            'ChannelStateDesc': kw.pop('state', 'Ring'),
            'EventTime': kw.pop('event_time', time.time()),
        }
        data.update(kw)
        return data
