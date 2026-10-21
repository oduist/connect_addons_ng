# -*- coding: utf-8 -*-
"""SIP credential lifecycle and the browser phone's configuration channel.

The credential is created in the domain's credential list when the SIP
phone is enabled; the password stays readable by its owner because the
browser registers with it (ADR-066 decisions 4 and 5).
"""
from unittest.mock import patch

from odoo.tests import tagged, new_test_user

from .common import VoiceTelTestCommon


@tagged('at_install', '-post_install')
class TestUserSipAccount(VoiceTelTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = cls.env['connect.settings'].sudo()
        settings.set_param('voicetel_auto_sync', True)
        Settings = type(cls.env['connect.settings'])
        with patch.object(Settings, 'get_voicetel_client', return_value=None):
            cls.domain = cls.env['connect.voicetel.domain'].with_context(
                no_voicetel_create=True).create({
                    'friendly_name': 'sip-test',
                    'subdomain': 'siptest',
                    'sid': 'SD' + '0' * 32,
                    'cred_list_sid': 'CL' + '0' * 32,
                })

    def _user(self, login, **kwargs):
        odoo_user = new_test_user(
            self.env, login=login, groups='base.group_user,connect.group_user')
        User = type(self.env['connect.user'])
        with patch.object(User, '_voicetel_create_sip_account',
                          return_value='CR' + '1' * 32) as create:
            vals = {
                'user': odoo_user.id,
                'voicetel_sip_enabled': True,
                'voicetel_username': login,
                'voicetel_domain': self.domain.id,
            }
            vals.update(kwargs)
            pbx_user = self.env['connect.user'].with_context(
                no_clear_cache=True).create(vals)
        return odoo_user, pbx_user, create

    def test_enabling_sip_creates_the_credential_and_a_password(self):
        odoo_user, pbx_user, create = self._user('vtsip1')

        create.assert_called_once()
        self.assertEqual(pbx_user.voicetel_sid, 'CR' + '1' * 32)
        self.assertTrue(pbx_user.voicetel_password)
        self.assertGreaterEqual(len(pbx_user.voicetel_password), 12)
        self.assertNotIn('*', pbx_user.voicetel_password)

    def test_the_browser_phone_gets_its_own_credential_only(self):
        odoo_user, pbx_user, _ = self._user('vtsip2', voicetel_phone_enabled=True)

        config = self.env['res.users'].with_user(odoo_user).get_voicetel_sip_user_config(
            odoo_user.id)

        self.assertEqual(config['user_config']['sip_user'], 'vtsip2')
        self.assertEqual(
            config['user_config']['sip_password'], pbx_user.voicetel_password)
        self.assertEqual(
            config['user_config']['phone_sip_proxy'], 'siptest.vml.voice.tel')
        self.assertEqual(
            config['user_config']['phone_websocket'],
            'wss://siptest.vml.voice.tel:8443')
        self.assertIn('call_popup_is_enabled', config['phone_config'])

    def test_another_user_cannot_read_the_credential(self):
        odoo_user, pbx_user, _ = self._user('vtsip3', voicetel_phone_enabled=True)
        other = new_test_user(
            self.env, login='vtsip3other',
            groups='base.group_user,connect.group_user')

        self.assertFalse(
            self.env['res.users'].with_user(other).get_voicetel_sip_user_config(
                odoo_user.id))

    def test_browser_phone_needs_the_sip_account(self):
        odoo_user, pbx_user, _ = self._user('vtsip4', voicetel_phone_enabled=False)

        self.assertFalse(
            self.env['res.users'].with_user(odoo_user).get_voicetel_sip_user_config(
                odoo_user.id))

    def test_disabling_sip_drops_the_credential(self):
        odoo_user, pbx_user, _ = self._user('vtsip5')
        User = type(self.env['connect.user'])
        with patch.object(User, 'voicetel_delete_sip_account',
                          return_value=True) as delete:
            pbx_user.voicetel_sip_enabled = False

        delete.assert_called_once()
        self.assertFalse(pbx_user.voicetel_sid)
        self.assertFalse(self.env['connect.voicetel.user_callflow'].search(
            [('user', '=', pbx_user.id), ('callflow_type', '=', 'sip')]))

    def test_sip_phone_requires_username_and_domain(self):
        from odoo.exceptions import ValidationError
        odoo_user = new_test_user(self.env, login='vtsip6')
        with self.assertRaises(ValidationError):
            self.env['connect.user'].with_context(
                no_clear_cache=True, no_voicetel_create=True).create({
                    'user': odoo_user.id,
                    'voicetel_sip_enabled': True,
                    'voicetel_domain': False,
                })
