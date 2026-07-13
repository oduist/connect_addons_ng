from unittest.mock import patch

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitCallerId(LivekitTestCommon):

    def setUp(self):
        super().setUp()
        self.trunk = self._create_trunk()

    def _create(self, number, **kwargs):
        vals = {
            'friendly_name': 'CID',
            'number': number,
            'trunk': self.trunk.id,
        }
        vals.update(kwargs)
        return self.env['connect.livekit.outgoing_callerid'].create(vals)

    def test_e164_constraint(self):
        with self.assertRaises(ValidationError):
            self._create('5551234567')

    def test_valid_e164(self):
        cid = self._create('+15551234567')
        self.assertTrue(cid.id)

    def test_is_default_resets_others(self):
        first = self._create('+15551110000', is_default=True)
        second = self._create('+15552220000', is_default=True)
        first.invalidate_recordset()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_unique_number(self):
        self._create('+15553330000')
        with self.assertRaises(Exception):
            self._create('+15553330000')
            self.env.flush_all()

    def test_reassign_trunk_pushes_old_and_new_trunks(self):
        cid = self._create('+15554440000')
        new_trunk = self._create_trunk(name='New Trunk')
        self.settings.sudo().set_param('livekit_auto_sync', True)
        pushed = []

        def _push_outbound(trunks):
            pushed.extend(trunks.ids)

        with patch.object(
                type(self.env['connect.livekit.trunk']),
                '_push_outbound', _push_outbound):
            cid.write({'trunk': new_trunk.id})
        self.assertIn(self.trunk.id, pushed)
        self.assertIn(new_trunk.id, pushed)
