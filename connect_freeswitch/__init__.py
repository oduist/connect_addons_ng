from . import controllers
from . import models

import logging
import secrets

from odoo import fields

_logger = logging.getLogger(__name__)


def setup_firewall(env):
    """Idempotent firewall initialisation — called from both post_init_hook
    and the per-version post-migration script so an upgrade against a
    pre-installed template gets the same treatment as a fresh install."""
    user = env.ref(
        'connect_freeswitch.user_freeswitch_agent',
        raise_if_not_found=False,
    )
    group_portal = env.ref('base.group_portal', raise_if_not_found=False)
    group_user = env.ref('base.group_user', raise_if_not_found=False)
    group_agent = env.ref(
        'connect_freeswitch.group_freeswitch_agent',
        raise_if_not_found=False,
    )
    if user:
        ops = []
        if group_user and group_user in user.group_ids:
            ops.append((3, group_user.id))
        if group_portal and group_portal not in user.group_ids:
            ops.append((4, group_portal.id))
        if group_agent and group_agent not in user.group_ids:
            ops.append((4, group_agent.id))
        if ops:
            user.sudo().write({'group_ids': ops})

    settings = env['connect.settings'].sudo()
    if not settings.get_param('firewall_service_token'):
        settings.set_param('firewall_service_token', secrets.token_hex(32))
    if not settings.get_param('freeswitch_agent_password'):
        password = secrets.token_urlsafe(24)
        settings.set_param('freeswitch_agent_password', password)
        if user:
            user.sudo().write({'password': password})

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
