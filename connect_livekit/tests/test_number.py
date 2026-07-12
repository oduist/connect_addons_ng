from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitNumber(LivekitTestCommon):

    def setUp(self):
        super().setUp()
        self.trunk = self._create_trunk(inbound_trunk_sid='ST_in')
        self.agent = self._create_agent()
        self.room = self.env['connect.livekit.room'].create({'name': 'R'})

    def _create(self, **kwargs):
        vals = {
            'phone_number': '+15550000001',
            'trunk': self.trunk.id,
            'destination': 'user',
            'user': self.admin_user.connect_user.id,
        }
        vals.update(kwargs)
        return self.env['connect.livekit.number'].create(vals)

    def test_e164_constraint(self):
        with self.assertRaises(ValidationError):
            self._create(phone_number='0000')

    def test_destination_user_requires_user(self):
        with self.assertRaises(ValidationError):
            self._create(destination='user', user=False)

    def test_write_clears_other_targets(self):
        number = self._create()
        number.write({'destination': 'agent', 'agent': self.agent.id})
        self.assertFalse(number.user)
        self.assertFalse(number.room)
        self.assertEqual(number.agent, self.agent)

    def test_dispatch_request_user_individual(self):
        number = self._create()
        request = number._dispatch_rule_request()
        self.assertTrue(
            request.rule.dispatch_rule_individual.room_prefix.startswith(
                'did-{}-'.format(number.id)))
        self.assertEqual(request.trunk_ids, ['ST_in'])
        self.assertEqual(request.inbound_numbers, [number.phone_number])

    def test_dispatch_request_agent_has_explicit_dispatch(self):
        number = self._create(
            destination='agent', user=False, agent=self.agent.id)
        request = number._dispatch_rule_request()
        self.assertTrue(request.room_config.agents)
        self.assertEqual(
            request.room_config.agents[0].agent_name, 'connect-livekit-agent')

    def test_get_number_for_room(self):
        number = self._create()
        room_name = 'did-{}-abcd'.format(number.id)
        self.assertEqual(
            self.env['connect.livekit.number'].get_number_for_room(room_name),
            number)
        self.assertFalse(
            self.env['connect.livekit.number'].get_number_for_room(
                'meet-x'))
