"""Rotate XML-RPC credentials and ensure deployment tokens (ADR-044/045)."""

from odoo import SUPERUSER_ID, api
from odoo.addons.connect_freeswitch import ensure_deployment_tokens


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        ALTER TABLE connect_settings
            DROP COLUMN IF EXISTS freeswitch_xmlrpc_port,
            DROP COLUMN IF EXISTS freeswitch_xmlrpc_user,
            DROP COLUMN IF EXISTS display_freeswitch_xmlrpc_password,
            DROP COLUMN IF EXISTS freeswitch_xmlrpc_tls_verify
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_deployment_tokens(env)
    settings = env["connect.settings"].sudo().search([], limit=1)
    if settings:
        settings._rotate_freeswitch_xmlrpc_password()
