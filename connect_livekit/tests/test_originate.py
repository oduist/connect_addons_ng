from unittest.mock import MagicMock

from odoo.tests import tagged

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitOriginate(LivekitTestCommon):

    def setUp(self):
        super().setUp()
        self.trunk = self._create_trunk(outbound_trunk_sid='ST_out')
        self.callerid = self.env['connect.livekit.outgoing_callerid'].create({
            'friendly_name': 'Main',
            'number': '+15550000001',
            'trunk': self.trunk.id,
            'is_default': True,
        })
        self.admin_user.connect_user.originate_provider = 'livekit'

    def test_originate_creates_channel_and_bus_push(self):
        # sip.create_sip_participant returns an object with sip_call_id.
        def _api(path, request=None):
            if path == 'sip.create_sip_participant':
                return MagicMock(sip_call_id='CALL_out')
            return MagicMock()

        sent = []
        with self.mock_license_check(True):
            with self.mock_api(side_effect=_api):
                with self._capture_bus(sent):
                    self.env['connect.settings'].originate_call(
                        '+15559998877', user=self.admin_user)
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'CALL_out')])
        self.assertTrue(channel)
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller, '+15550000001')
        self.assertEqual(channel.called, '+15559998877')
        self.assertTrue(any(
            p.get('action') == 'join' for _, _, p in sent))

    def _capture_bus(self, sink):
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def _cm():
            orig = type(self.env['bus.bus'])._sendone

            def _spy(self2, target, channel, message):
                sink.append((target, channel, message))
                return orig(self2, target, channel, message)

            with patch.object(
                    type(self.env['bus.bus']), '_sendone', _spy):
                yield
        return _cm()
