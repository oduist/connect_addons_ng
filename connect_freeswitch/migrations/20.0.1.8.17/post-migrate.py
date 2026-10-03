"""Drop the freeswitch_agent portal user, partner and group on upgrade.

In 19.0.1.8.17 the firewall service stops authenticating to Odoo as a
portal user. It now hits dedicated /freeswitch/firewall/api/* HTTP
controllers protected by the shared firewall_service_token. This
migration removes the leftover Odoo objects that the previous schema
created — the user (via noupdate XML data, so a manifest-driven
removal alone wouldn't unlink it), its partner, the dedicated group,
and the stored agent password.

Idempotent: each lookup uses raise_if_not_found=False.
"""
import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.connect_freeswitch import setup_firewall

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    env['ir.config_parameter'].sudo().search(
        [('key', '=', 'freeswitch_agent_password')]
    ).unlink()

    user = env.ref(
        'connect_freeswitch.user_freeswitch_agent', raise_if_not_found=False,
    )
    if user:
        user.sudo().unlink()

    partner = env.ref(
        'connect_freeswitch.partner_freeswitch_agent', raise_if_not_found=False,
    )
    if partner:
        partner.sudo().unlink()

    group = env.ref(
        'connect_freeswitch.group_freeswitch_agent', raise_if_not_found=False,
    )
    if group:
        group.sudo().unlink()

    setup_firewall(env)
    _logger.info(
        "Firewall agent user/group removed; service now authenticates "
        "via shared firewall_service_token."
    )
