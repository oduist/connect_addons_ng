# -*- coding: utf-8 -*-
"""connect.twilio.exten tests (moved from the shared core exten suite
after the provider model separation, ADR-031)."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestTwilioExten(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user('tw_extenuser1')
        cls.exten = cls.env['connect.twilio.exten'].create({
            'number': '8200',
            'model': 'connect.user',
            'res_id': cls.connect_user.id,
        })

    def test_create_exten(self):
        self.assertTrue(self.exten.id)
        self.assertEqual(self.exten.number, '8200')

    def test_unique_number(self):
        with self.assertRaises(Exception):
            self.env['connect.twilio.exten'].create({
                'number': '8200',
                'model': 'connect.user',
                'res_id': self.connect_user.id,
            })

    def test_model_friendly_compute(self):
        self.assertEqual(self.exten.model_friendly, 'User')

    def test_model_friendly_callflow(self):
        callflow = self.env['connect.twilio.callflow'].create({
            'name': 'Test Flow',
        })
        exten = self.env['connect.twilio.exten'].create({
            'number': '300',
            'model': 'connect.twilio.callflow',
            'res_id': callflow.id,
        })
        self.assertEqual(exten.model_friendly, 'Call Flow')

    def test_dst_compute(self):
        self.assertEqual(self.exten.dst._name, 'connect.user')
        self.assertEqual(self.exten.dst.id, self.connect_user.id)

    def test_user_back_link(self):
        self.assertEqual(self.connect_user.twilio_exten, self.exten)
        self.assertEqual(self.connect_user.twilio_exten_number, '8200')

    def test_unlink_clears_dst_exten(self):
        self.exten.unlink()
        self.assertFalse(self.connect_user.twilio_exten)

    def test_create_refuses_a_number_already_in_use(self):
        """An extension is never taken over by another one being created.

        A number whose extension happens to have no destination used to be
        rewritten with the new values and returned in place of the record
        the caller asked to create.
        """
        orphan = self.env['connect.twilio.exten'].create({'number': '500'})
        with self.assertRaises(ValidationError):
            self.env['connect.twilio.exten'].create({
                'number': '500',
                'model': 'connect.user',
                'res_id': self.connect_user.id,
            })
        self.assertFalse(orphan.dst)
        self.assertEqual(
            self.env['connect.twilio.exten'].search_count([('number', '=', '500')]), 1)

    def test_a_second_extension_for_the_same_user_is_refused(self):
        second = self.env['connect.twilio.exten'].create({'number': '501'})
        with self.assertRaises(ValidationError):
            second.write({
                'model': 'connect.user', 'res_id': self.connect_user.id})
            self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(self.connect_user.twilio_exten, self.exten)

    def test_moving_an_extension_releases_the_previous_user(self):
        other = self._create_connect_user('tw_extenuser2')
        self.exten.write({'model': 'connect.user', 'res_id': other.id})
        self.env.flush_all()
        self.assertFalse(self.connect_user.twilio_exten)
        self.assertEqual(other.twilio_exten, self.exten)

    def test_clearing_the_destination_releases_the_user(self):
        self.exten.write({'model': False, 'res_id': False})
        self.env.flush_all()
        self.assertFalse(self.connect_user.twilio_exten)

    def test_create_extension_action(self):
        result = self.env['connect.twilio.exten'].create_extension(
            self.connect_user, 'connect.user',
            current_exten=self.connect_user.twilio_exten)
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.twilio.exten')

    def test_repair_relinks_a_destination_missing_its_back_link(self):
        # State left by builds before the _set_dst fix: the extension names
        # the user, the user names no extension (inbound DIDs answered 404).
        user = self._create_connect_user('relink_user')
        exten = self.env['connect.twilio.exten'].create({
            'number': '8290', 'model': 'connect.user', 'res_id': user.id})
        user.twilio_exten = False
        self.assertFalse(user.twilio_exten)
        self.env['connect.twilio.exten']._repair_dst_links()
        self.assertEqual(user.twilio_exten, exten)
