from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install', 'connect_freeswitch_parking')
class ParkingSlotTestCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Slot = cls.env['connect.freeswitch.parking.slot']
        # Clear any demo/default slots so sequence ordering in the tests is
        # deterministic regardless of data XML load order.
        cls.env['connect.freeswitch.parking.slot'].search([]).unlink()
        cls.slot_701 = cls.Slot.create({
            'name': 'Slot 701', 'exten': '701', 'sequence': 10,
        })
        cls.slot_702 = cls.Slot.create({
            'name': 'Slot 702', 'exten': '702', 'sequence': 20,
        })

        cls.user = cls.env['res.users'].create({
            'name': 'Alice', 'login': 'alice@test',
        })
        cls.connect_user = cls.env['connect.user'].create({
            'user': cls.user.id,
        })
        cls.env['connect.freeswitch.exten'].create({
            'number': '1001', 'model': 'connect.user',
            'res_id': cls.connect_user.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'External Bob',
        })
        cls.call = cls.env['connect.call'].create({
            'caller': '+48123456789',
            'called': '1001',
            'partner': cls.partner.id,
            'status': 'active',
        })
        # Fake FreeSWITCH channel for the remote (caller) leg
        cls.channel = cls.env['connect.channel'].create({
            'sid': 'uuid-remote-leg-xxx',
            'call': cls.call.id,
            'caller': '+48123456789',
            'called': '1001',
            'status': 'active',
        })

    # ------------------------------------------------------------------
    # Park action
    # ------------------------------------------------------------------

    def test_find_remote_leg_uuid_skips_user_leg(self):
        """Local user leg is skipped; remote leg UUID is returned."""
        # Add a local leg owned by the current user
        self.env['connect.channel'].create({
            'sid': 'uuid-local-leg-yyy',
            'call': self.call.id,
            'caller': '+48123456789',
            'called': '1001',
            'caller_pbx_user': self.connect_user.id,
            'status': 'active',
        })
        found = self.slot_701.with_user(self.user)._find_remote_leg_uuid(self.call)
        self.assertEqual(found, 'uuid-remote-leg-xxx')

    def test_action_park_call_success(self):
        """Successful park writes slot state and calls freeswitch_api."""
        with patch.object(
            type(self.env['connect.settings']), 'freeswitch_api',
            return_value='+OK Success',
        ) as fs_api:
            result = self.slot_701.action_park_call(self.call.id)

        fs_api.assert_called_once()
        cmd, args = fs_api.call_args[0]
        self.assertEqual(cmd, 'uuid_transfer')
        self.assertIn('uuid-remote-leg-xxx', args)
        # The transfer goes through the XML dialplan extension so the
        # parking webhook in connect_valet_parking_<slot> fires; an
        # inline valet_park would bypass it (see fs_parking_slot.py).
        self.assertIn('701 XML default', args)

        self.slot_701.invalidate_recordset()
        self.assertTrue(self.slot_701.is_occupied)
        self.assertEqual(self.slot_701.parked_uuid, 'uuid-remote-leg-xxx')
        self.assertEqual(self.slot_701.parked_call, self.call)
        self.assertEqual(result['params']['type'], 'success')

    def test_action_park_already_occupied(self):
        """Parking onto an occupied slot raises UserError."""
        self.slot_701.write({
            'parked_uuid': 'some-other-uuid',
            'parked_at': '2026-04-21 10:00:00',
        })
        with self.assertRaises(UserError):
            self.slot_701.action_park_call(self.call.id)

    def test_action_park_no_active_channel(self):
        """No remote channel -> UserError; freeswitch_api not called."""
        self.channel.unlink()
        with patch.object(
            type(self.env['connect.settings']), 'freeswitch_api',
        ) as fs_api:
            with self.assertRaises(UserError):
                self.slot_701.action_park_call(self.call.id)
            fs_api.assert_not_called()

    def test_action_fs_park_picks_first_free_slot(self):
        """connect.call.action_fs_park() delegates to the lowest-seq slot."""
        # Occupy 701 so 702 should be selected
        self.slot_701.write({'parked_uuid': 'xxx'})
        with patch.object(
            type(self.env['connect.settings']), 'freeswitch_api',
            return_value='+OK Success',
        ):
            self.call.action_fs_park()

        self.slot_702.invalidate_recordset()
        self.assertTrue(self.slot_702.is_occupied)
        self.assertFalse(self.slot_702.parked_call != self.call)

    def test_action_fs_park_no_free_slot(self):
        """No free slot → UserError."""
        self.slot_701.write({'parked_uuid': 'a'})
        self.slot_702.write({'parked_uuid': 'b'})
        with self.assertRaises(UserError):
            self.call.action_fs_park()

    # ------------------------------------------------------------------
    # Webhook handlers
    # ------------------------------------------------------------------

    def test_webhook_entered_updates_slot(self):
        self.Slot.on_parking_entered(
            exten='701',
            uuid='fs-uuid-aaa',
            caller_number='+48999888777',
            caller_name='Caller Name',
        )
        self.slot_701.invalidate_recordset()
        self.assertEqual(self.slot_701.parked_uuid, 'fs-uuid-aaa')
        self.assertTrue(self.slot_701.is_occupied)
        self.assertEqual(self.slot_701.parked_caller_number, '+48999888777')
        self.assertEqual(self.slot_701.parked_caller_name, 'Caller Name')

    def test_webhook_entered_idempotent(self):
        """Replaying the same entered event is a no-op."""
        self.Slot.on_parking_entered(
            exten='701', uuid='fs-uuid-aaa',
            caller_number='1', caller_name='One')
        parked_at_first = self.slot_701.parked_at
        self.Slot.on_parking_entered(
            exten='701', uuid='fs-uuid-aaa',
            caller_number='2', caller_name='Two')
        self.slot_701.invalidate_recordset()
        # Idempotency: fields should not have been overwritten with new values
        self.assertEqual(self.slot_701.parked_caller_number, '1')
        self.assertEqual(self.slot_701.parked_at, parked_at_first)

    def test_webhook_entered_unknown_slot(self):
        """Webhook for non-existent slot returns False, doesn't error."""
        result = self.Slot.on_parking_entered(
            exten='999', uuid='fs-uuid-aaa')
        self.assertFalse(result)

    def test_webhook_released_clears_slot(self):
        self.slot_701.write({
            'parked_uuid': 'fs-uuid-aaa',
            'parked_caller_number': '+48999',
            'parked_caller_name': 'Someone',
        })
        self.Slot.on_parking_released(exten='701')
        self.slot_701.invalidate_recordset()
        self.assertFalse(self.slot_701.is_occupied)
        self.assertFalse(self.slot_701.parked_uuid)
        self.assertFalse(self.slot_701.parked_caller_number)
        self.assertFalse(self.slot_701.parked_caller_name)

    def test_webhook_released_idempotent_on_empty_slot(self):
        """Releasing an already-empty slot is safe."""
        result = self.Slot.on_parking_released(exten='701')
        self.assertTrue(result)


@tagged('post_install', '-at_install', 'connect_freeswitch_parking_http')
class ParkingWebhookHttpCase(HttpCase):

    def _token(self):
        # Auto-generated on settings creation (ADR-025); webhook URLs
        # rendered by Odoo carry it as the ``token`` query parameter.
        return self.env['connect.settings'].sudo().get_param(
            'freeswitch_webhook_token')

    def test_parking_webhook_entered(self):
        Slot = self.env['connect.freeswitch.parking.slot']
        Slot.search([]).unlink()
        slot = Slot.create({'name': 'Slot 701', 'exten': '701'})
        token = self._token()

        resp = self.url_open(
            '/freeswitch/webhook/parking'
            '?event=entered&slot=701&uuid=ws-uuid-1'
            '&caller_number=%2B48111&caller_name=WebCaller'
            '&token=' + token)
        self.assertEqual(resp.status_code, 200)
        slot.invalidate_recordset()
        self.assertTrue(slot.is_occupied)
        self.assertEqual(slot.parked_uuid, 'ws-uuid-1')

        resp2 = self.url_open(
            '/freeswitch/webhook/parking?event=released&slot=701'
            '&token=' + token)
        self.assertEqual(resp2.status_code, 200)
        slot.invalidate_recordset()
        self.assertFalse(slot.is_occupied)

    def test_parking_webhook_rejects_missing_params(self):
        token = self._token()
        self.assertEqual(
            self.url_open(
                '/freeswitch/webhook/parking?token=' + token
            ).status_code, 400)
        self.assertEqual(
            self.url_open(
                '/freeswitch/webhook/parking?event=entered&slot=701'
                '&token=' + token
            ).status_code, 400)  # missing uuid
        self.assertEqual(
            self.url_open(
                '/freeswitch/webhook/parking?event=bogus&slot=701&uuid=x'
                '&token=' + token
            ).status_code, 400)

    def test_parking_webhook_rejects_bad_token(self):
        # No token and a wrong token are both 401 before any processing.
        self.assertEqual(
            self.url_open(
                '/freeswitch/webhook/parking?event=released&slot=701'
            ).status_code, 401)
        self.assertEqual(
            self.url_open(
                '/freeswitch/webhook/parking?event=released&slot=701'
                '&token=wrong'
            ).status_code, 401)
