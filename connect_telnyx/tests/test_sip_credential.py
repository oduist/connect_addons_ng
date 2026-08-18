# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.connect.models.settings import Settings as CoreSettings
from odoo.addons.connect_telnyx.models.settings import Settings

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxSipCredential(TelnyxTestCommon):
    """Telnyx owns the SIP username and password: they can only be
    rotated by issuing a new credential."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._create_connect_user(
            'telnyx_sip_cred',
            telnyx_domain=cls.domain.id,
            telnyx_sip_enabled=True,
            telnyx_sip_credential_sid='old-credential',
            telnyx_sip_username='old-username',
            telnyx_sip_password='old-password',
        )
        cls._grant_group(cls.user.user, 'connect.group_admin')

    def _client(self, deleted):
        class Credentials:
            @staticmethod
            def delete(sid):
                deleted.append(sid)
                return True

            @staticmethod
            def create(**kwargs):
                return type('Response', (), {'data': type('Data', (), {
                    'id': 'new-credential',
                    'sip_username': 'new-username',
                    'sip_password': 'new-password',
                })()})()

        class Client:
            telephony_credentials = Credentials()

        return Client()

    def test_regenerate_replaces_the_credential(self):
        deleted = []
        with patch.object(Settings, 'get_telnyx_client', autospec=True,
                          return_value=self._client(deleted)), patch.object(
                              CoreSettings, 'connect_notify', autospec=True):
            self.user.with_user(
                self.user.user).action_regenerate_telnyx_sip_credential()
        self.assertEqual(deleted, ['old-credential'])
        self.assertEqual(self.user.telnyx_sip_credential_sid, 'new-credential')
        self.assertEqual(self.user.telnyx_sip_username, 'new-username')
        self.assertEqual(self.user.telnyx_sip_password, 'new-password')

    def test_regenerate_requires_an_administrator(self):
        plain = self._create_connect_user('telnyx_sip_plain')
        self._grant_group(plain.user, 'connect.group_user')
        with self.assertRaises(ValidationError):
            self.user.with_user(
                plain.user).action_regenerate_telnyx_sip_credential()

    def test_regenerate_needs_the_sip_phone_enabled(self):
        self.user.with_context(skip_telnyx_sync=True).write(
            {'telnyx_sip_enabled': False})
        with self.assertRaises(ValidationError):
            self.user.with_user(
                self.user.user).action_regenerate_telnyx_sip_credential()

    def test_password_is_readable_on_own_record(self):
        """A plain Connect user provisioning a hardphone reads the
        credential off their own PBX user; the record rule keeps other
        users' credentials out of reach."""
        reader = self._create_connect_user(
            'telnyx_sip_reader',
            telnyx_domain=self.domain.id,
            telnyx_sip_enabled=True,
            telnyx_sip_username='reader-username',
            telnyx_sip_password='reader-password',
        )
        self._grant_group(reader.user, 'connect.group_user')
        data = reader.with_user(reader.user).read(
            ['telnyx_sip_username', 'telnyx_sip_password'])[0]
        self.assertEqual(data['telnyx_sip_password'], 'reader-password')
        with self.assertRaises(AccessError):
            self.user.with_user(reader.user).read(['telnyx_sip_password'])
