import re

from odoo.addons.connect_freeswitch import ensure_deployment_tokens
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "connect_freeswitch")
class DeploymentTokenBootstrapCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env["connect.settings"].sudo()

    def test_bootstrap_generates_both_missing_tokens(self):
        self.settings.set_param("freeswitch_webhook_token", False)
        self.settings.set_param("firewall_service_token", False)

        ensure_deployment_tokens(self.env)

        webhook_token = self.settings.get_param("freeswitch_webhook_token")
        firewall_token = self.settings.get_param("firewall_service_token")
        self.assertRegex(webhook_token, re.compile(r"^[A-Za-z0-9_-]{24,}$"))
        self.assertRegex(firewall_token, re.compile(r"^[A-Za-z0-9_-]{24,}$"))
        self.assertNotEqual(webhook_token, firewall_token)
        self.assertTrue(self.env["connect.firewall.agent"].sudo().search([], limit=1))

    def test_bootstrap_preserves_existing_tokens(self):
        webhook_token = "existing-webhook-token-123456789"
        firewall_token = "existing-firewall-token-12345678"
        self.settings.set_param("freeswitch_webhook_token", webhook_token)
        self.settings.set_param("firewall_service_token", firewall_token)

        ensure_deployment_tokens(self.env)

        self.assertEqual(
            self.settings.get_param("freeswitch_webhook_token"), webhook_token
        )
        self.assertEqual(
            self.settings.get_param("firewall_service_token"), firewall_token
        )
