from . import controllers
from . import models

import logging
import secrets

from odoo import fields

_logger = logging.getLogger(__name__)


def setup_firewall(env):
    """Idempotent firewall bootstrap — called from post_init_hook and
    per-version post-migration scripts. Generates the shared service
    token if missing and ensures the agent singleton exists."""
    settings = env['connect.settings'].sudo()
    if not settings.get_param('firewall_service_token'):
        settings.set_param('firewall_service_token', secrets.token_hex(32))
    env['connect.firewall.agent'].sudo()._get_singleton()


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_freeswitch')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
        setup_firewall(env)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))


def uninstall_hook(env):
    """Clean up FS-specific config that lives outside the module's own
    XML data so a fresh re-install (or a switch to a Twilio-only deploy)
    starts from a clean slate.

    - firewall_service_token: shared secret used by firewall API; if left
      behind a future reinstall would reuse a token the operator may no
      longer know about. Drop it.
    """
    try:
        env['ir.config_parameter'].sudo().search(
            [('key', '=', 'firewall_service_token')]
        ).unlink()
    except Exception as e:
        _logger.error('Error in uninstall_hook: %s', str(e))
