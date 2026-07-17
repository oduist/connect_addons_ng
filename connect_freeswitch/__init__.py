from . import controllers
from . import models

import logging
import secrets

from odoo import fields

_logger = logging.getLogger(__name__)


def backfill_endpoint_passwords(env):
    """Generate a passphrase for any endpoint missing an auth_password.

    Non-destructive: endpoints with a password already set are left untouched.
    Shared helper called from the per-series post-migration entry point.
    """
    from .models.passphrase import generate_passphrase
    endpoints = env['connect.freeswitch.endpoint'].sudo().with_context(active_test=False).search([
        '|', ('auth_password', '=', False), ('auth_password', '=', ''),
    ])
    for endpoint in endpoints:
        endpoint.auth_password = generate_passphrase()


def setup_firewall(env):
    """Idempotent firewall bootstrap — called from post_init_hook and
    per-version post-migration scripts. Generates the shared service
    token if missing and ensures the agent singleton exists."""
    settings = env['connect.settings'].sudo()
    if not settings.get_param('firewall_service_token'):
        settings.set_param('firewall_service_token', secrets.token_hex(32))
    env['connect.firewall.agent'].sudo()._get_singleton()


def ensure_webhook_token(env):
    """Idempotent: generate freeswitch_webhook_token if missing (ADR-025).

    A random token locks the FreeSWITCH HTTP endpoints (fail-closed)
    until the operator pairs the container via FS_WEBHOOK_TOKEN.
    """
    settings = env['connect.settings'].sudo()
    if not settings.get_param('freeswitch_webhook_token'):
        settings.set_param('freeswitch_webhook_token', secrets.token_urlsafe(32))


def ensure_deployment_tokens(env):
    """Ensure all credentials required by the deployed services exist.

    The individual helpers remain public because older per-series migrations
    import them directly. This aggregate is the installation and current
    migration contract used by Oduflow deployments (ADR-044).
    """
    setup_firewall(env)
    ensure_webhook_token(env)


def post_init_hook(env):
    try:
        ensure_deployment_tokens(env)
        module = env['ir.module.module'].search([('name', '=', 'connect_freeswitch')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
