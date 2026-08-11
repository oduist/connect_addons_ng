# -*- coding: utf-8 -*-
"""connect.settings Vonage extension tests: client assembly, secret
masking, webhook URLs, originate (ADR-036)."""
from unittest.mock import patch

import jwt as pyjwt

from odoo.exceptions import ValidationError
from odoo.tests import tagged, new_test_user

from odoo.addons.connect_vonage import ensure_vonage_usernames

from .common import VonageTestCommon


@tagged('at_install', '-post_install')
class TestVonageSettings(VonageTestCommon):

    def test_get_client(self):
        client = self.settings.get_client()
        self.assertTrue(client.voice)
        self.assertTrue(client.messages)

    def test_get_client_requires_credentials(self):
        self.settings.set_param('vonage_api_key', False)
        self.settings.set_param('vonage_api_secret', False)
        self.settings.set_param('vonage_application_id', False)
        self.settings.set_param('vonage_private_key', False)
        with self.assertRaises(ValidationError):
            self.settings.get_client()

    def test_secret_masking(self):
        settings = self.env['connect.settings'].sudo().search([], limit=1)
        settings.write({'display_vonage_api_secret': 'SECRET99'})
        self.assertEqual(settings.vonage_api_secret, 'SECRET99')
        self.assertEqual(
            settings.display_vonage_api_secret, '*' * len('SECRET99'))

    def test_webhook_url(self):
        url = self.settings.get_vonage_webhook_url('event')
        self.assertEqual(url, 'https://odoo.example.com/vonage/webhook/event')

    def test_get_client_token(self):
        connect_user = self._create_connect_user('vonage_tok_user')
        result = self.env['connect.user'].with_user(
            connect_user.user).get_client_token()
        self.assertTrue(result.get('token'), result)
        claims = pyjwt.decode(
            result['token'], options={'verify_signature': False})
        self.assertEqual(claims['sub'], connect_user.username)
        self.assertEqual(claims['application_id'], 'app-test-id')
        self.assertIn('/*/sessions/**', claims['acl']['paths'])

    def test_get_client_token_disabled(self):
        connect_user = self._create_connect_user(
            'vonage_tok_user2', client_enabled=False)
        result = self.env['connect.user'].with_user(
            connect_user.user).get_client_token()
        self.assertFalse(result.get('token'))

    def test_originate_requires_connect_user(self):
        odoo_user = new_test_user(self.env, login='vonage_no_pbx')
        with self.mock_license_check():
            with self.assertRaises(ValidationError):
                self.settings.originate_call(
                    '+15559998888', user=odoo_user)

    def test_originate_call(self):
        connect_user = self._create_connect_user('vonage_orig_user')
        callerid = self.env['connect.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'Main',
            'callerid_type': 'number',
            'is_default': True,
        })
        connect_user.outgoing_callerid = callerid
        with self.mock_license_check(), patch.object(
            type(self.env['connect.settings']),
            'vonage_create_call',
            return_value={'uuid': 'leg-orig-1',
                          'conversation_uuid': 'conv-orig-1'},
        ) as mock_create:
            self.settings.originate_call(
                '+15559998888', user=connect_user.user)
        payload = mock_create.call_args[0][0]
        self.assertEqual(
            payload['to'],
            [{'type': 'app', 'user': connect_user.username}])
        self.assertEqual(payload['from']['number'], '15550001111')
        connect_actions = [
            a for a in payload['ncco'] if a['action'] == 'connect']
        self.assertEqual(
            connect_actions[0]['endpoint'][0]['number'], '15559998888')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'leg-orig-1')])
        self.assertTrue(channel)
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller_pbx_user, connect_user)
        self.assertEqual(channel.conversation_uuid, 'conv-orig-1')

    def test_originate_internal_call_uses_phone_callerid(self):
        caller = self._create_connect_user('vonage_internal_caller')
        callee = self._create_connect_user('vonage_internal_callee')
        callerid = self.env['connect.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'Main',
            'callerid_type': 'number',
            'is_default': True,
        })
        caller.outgoing_callerid = callerid
        exten = self.env['connect.exten'].create({'number': '801'})
        exten.dst = callee
        with self.mock_license_check(), patch.object(
            type(self.env['connect.settings']),
            'vonage_create_call',
            return_value={'uuid': 'leg-internal-1'},
        ) as mock_create:
            self.settings.originate_call('801', user=caller.user)
        payload = mock_create.call_args[0][0]
        self.assertEqual(payload['from']['number'], '15550001111')

    def test_backfill_vonage_username_and_not_null_constraint(self):
        connect_user = self._create_connect_user('vonage_backfill_user')
        self.env.cr.execute(
            'ALTER TABLE connect_user ALTER COLUMN username DROP NOT NULL')
        self.env.cr.execute(
            'UPDATE connect_user SET username = NULL WHERE id = %s',
            (connect_user.id,),
        )
        connect_user.invalidate_recordset(['username'])

        ensure_vonage_usernames(self.env)

        self.assertEqual(connect_user.username, 'vonagebackfilluser')
        self.env.cr.execute(
            """SELECT attnotnull
                 FROM pg_attribute
                WHERE attrelid = 'connect_user'::regclass
                  AND attname = 'username'""")
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_originate_whatsapp_not_supported(self):
        with self.mock_license_check():
            with self.assertRaises(ValidationError):
                self.settings.originate_call(
                    '+15559998888', whatsapp_call=True)
