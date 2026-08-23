from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestSettings(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].search([])
        if not cls.settings:
            cls.settings = cls.env['connect.settings'].sudo().with_context(
                no_constrains=True).create({})

    def test_singleton_get_param(self):
        """Test get_param returns the value."""
        self.settings.debug_mode = True
        result = self.env['connect.settings'].get_param('debug_mode')
        self.assertTrue(result)

    def test_singleton_set_param(self):
        """Test set_param updates the value."""
        self.env['connect.settings'].set_param('debug_mode', True)
        self.assertTrue(self.settings.debug_mode)

    def test_name_compute(self):
        """Test name computes to General Settings."""
        self.assertEqual(self.settings.name, 'General Settings')

    def test_default_summary_prompt(self):
        """Test default summary prompt is set."""
        self.assertTrue(self.settings.summary_prompt)

    def test_default_number_search_operation(self):
        """Test default number_search_operation is =."""
        self.assertEqual(self.settings.number_search_operation, '=')

    def test_default_proxy_recordings(self):
        """Test default proxy_recordings is True."""
        self.assertTrue(self.settings.proxy_recordings)

    def test_default_transcript_provider(self):
        """Test default transcript_provider is openai."""
        self.assertEqual(self.settings.transcript_provider, 'openai')

    def test_recording_deletion_after_transcription_is_opt_in(self):
        """Audio retention remains enabled unless an admin opts out."""
        self.assertFalse(self.settings.delete_recording_after_transcription)

    def test_default_openai_summary_model(self):
        """Test GPT-5.4 mini is the default summary model."""
        self.assertEqual(self.settings.openai_summary_model, 'gpt-5.4-mini')

    def test_open_settings_form(self):
        """Test open_settings_form returns action window."""
        result = self.settings.open_settings_form()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.settings')
        self.assertEqual(result['res_id'], self.settings.id)

    def test_check_api_url_http(self):
        """Test check_api_url warns on HTTP."""
        self.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'http://example.com')
        message = self.settings.check_api_url()
        self.assertIn('HTTPS', message)

    def test_check_api_url_localhost(self):
        """Test check_api_url warns on localhost."""
        self.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://localhost:8069')
        message = self.settings.check_api_url()
        self.assertIn('Localhost', message)

    def test_check_api_url_valid(self):
        """Test check_api_url returns None for valid URL."""
        self.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://api.example.com')
        message = self.settings.check_api_url()
        self.assertIsNone(message)

    def test_write_protected_fields(self):
        """Test writing display_openai_api_key copies to real field."""
        self.settings.write({'display_openai_api_key': 'sk-test-123'})
        self.assertEqual(self.settings.openai_api_key, 'sk-test-123')
        self.assertEqual(self.settings.display_openai_api_key, '***********')

    def test_connect_notify(self):
        """Test connect_notify sends bus notification."""
        result = self.env['connect.settings'].connect_notify(
            'Test message', title='Test')
        self.assertTrue(result)

    def test_action_open_system_parameters(self):
        """Test action_open_system_parameters returns action."""
        result = self.settings.action_open_system_parameters()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'ir.config_parameter')

    # def test_set_default_admin_and_company(self):
    #     """Test set_default_admin_and_company fills admin fields."""
    #     self.settings.with_user(self.admin_user).set_default_admin_and_company()
    #     self.assertTrue(self.settings.admin_name)
