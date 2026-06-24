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
    endpoints = env['connect.endpoint'].sudo().with_context(active_test=False).search([
        '|', ('auth_password', '=', False), ('auth_password', '=', ''),
    ])
    for endpoint in endpoints:
        endpoint.auth_password = generate_passphrase()


def setup_firewall(env):
    """Idempotent firewall bootstrap — called from post_init_hook and
    per-version post-migration scripts. Generates the shared service
    token if missing and ensures the agent singleton exists."""
    cfg = env['connect.provider.freeswitch.config'].sudo()._get()
    if not cfg.firewall_service_token:
        cfg.firewall_service_token = secrets.token_hex(32)
    env['connect.firewall.agent'].sudo()._get_singleton()


def register_provider(env):
    """Idempotent upsert of the FreeSWITCH entry in connect.provider.
    Called from post_init_hook and from per-version post-migration scripts."""
    env['connect.provider'].sudo()._register_code(code='freeswitch', name='FreeSWITCH', sequence=20)


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_freeswitch')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
        setup_firewall(env)
        register_provider(env)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))


def uninstall_hook(env):
    """Clean up FS-specific config that lives outside the module's own
    XML data so a fresh re-install (or a switch to a Twilio-only deploy)
    starts from a clean slate.

    - firewall_service_token: shared secret used by firewall API; if
      left behind a future reinstall would reuse a token the operator
      may no longer know about. Drop it.
    - connect.provider 'freeswitch' is deactivated (not deleted) so any
      connect.call.provider_id still referencing it keeps resolving.
    - connect.exten.dst Reference cleanup (ODU-18): refs pointing at
      FS-owned models would dangle once those models are dropped on
      uninstall. NULL them here.
    """
    try:
        # firewall_service_token now lives on connect.provider.freeswitch.config —
        # the ir.config_parameter cleanup from earlier versions was a no-op
        # but harmless; keep it for backwards-compatibility on older DBs.
        env['ir.config_parameter'].sudo().search(
            [('key', '=', 'firewall_service_token')]
        ).unlink()
        env['connect.provider'].sudo()._deactivate('freeswitch')
        fs_models = (
            'connect.fs_fifo',
            'connect.endpoint',  # FS-only standalone endpoints
            'connect.freeswitch.parking.slot',
            'connect.freeswitch.gateway',
            'connect.freeswitch.outgoing_route',
            'connect.freeswitch.template',
        )
        env.cr.execute(
            "UPDATE connect_exten SET model = NULL, res_id = NULL "
            "WHERE model = ANY(%s)",
            (list(fs_models),),
        )
    except Exception as e:
        _logger.error('Error in uninstall_hook: %s', str(e))
