from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitAgent(LivekitTestCommon):

    def test_tool_token_generated(self):
        agent = self._create_agent()
        self.assertTrue(agent.sudo().tool_token)

    def test_rotate_tool_token(self):
        agent = self._create_agent()
        old = agent.sudo().tool_token
        agent.action_rotate_tool_token()
        self.assertNotEqual(agent.sudo().tool_token, old)

    def test_time_limit_constraint(self):
        with self.assertRaises(ValidationError):
            self._create_agent(time_limit_secs=10)
        with self.assertRaises(ValidationError):
            self._create_agent(time_limit_secs=99999)

    def test_enabled_tools_contact_only(self):
        agent = self._create_agent(
            enable_contact_tools=True,
            enable_crm_tools=True, enable_helpdesk_tools=True)
        tools = agent._enabled_tools()
        self.assertIn('lookup_contact', tools)
        self.assertIn('add_contact_note', tools)
        # crm/helpdesk only when the module is present.
        if 'crm.lead' not in self.env:
            self.assertNotIn('upsert_crm_lead', tools)

    def test_config_payload_shape(self):
        agent = self._create_agent(voice='alloy', llm_model='gpt-4o-mini')
        self.settings.sudo().set_param('deepgram_api_key', 'dg-key')
        payload = agent._agent_config_payload()
        self.assertEqual(payload['id'], agent.id)
        self.assertEqual(payload['llm_model'], 'gpt-4o-mini')
        self.assertIn('/livekit/webhook/agent/{}'.format(agent.id),
                      payload['webhook_base'])
        self.assertEqual(payload['tool_token'], agent.sudo().tool_token)
        self.assertEqual(payload['keys']['deepgram'], 'dg-key')

    def test_execute_tool_unknown(self):
        agent = self._create_agent()
        with self.assertRaises(ValidationError):
            agent.execute_tool('drop_table', {})

    def test_execute_tool_disabled_contact(self):
        agent = self._create_agent(enable_contact_tools=False)
        with self.assertRaises(ValidationError):
            agent.execute_tool('lookup_contact', {})

    def test_execute_lookup_contact(self):
        agent = self._create_agent(enable_contact_tools=True)
        result = agent.execute_tool(
            'lookup_contact', {'phone': self.partner.phone})
        self.assertTrue(result['found'])
        self.assertEqual(result['partner_id'], self.partner.id)

    def test_execute_add_contact_note(self):
        agent = self._create_agent(enable_contact_tools=True)
        result = agent.execute_tool(
            'add_contact_note',
            {'phone': self.partner.phone, 'note': 'Called about invoice'})
        self.assertTrue(result['ok'])
        messages = self.partner.message_ids.filtered(
            lambda m: 'invoice' in (m.body or ''))
        self.assertTrue(messages)
