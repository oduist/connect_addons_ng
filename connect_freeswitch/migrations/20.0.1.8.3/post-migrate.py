"""Initialise the firewall portal user, secrets and agent singleton on
upgrade.

When the module is upgraded against a database that already had a previous
version installed (typical for the fs19-dev template snapshot), the
post_init_hook does not run. This migration calls the same setup routine
so that the freeswitch_agent user lands in Role/Portal + the agent group,
the service token and agent password are generated, and the agent
singleton is created.
"""
import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.connect_freeswitch import setup_firewall

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        setup_firewall(env)
        _logger.info("Firewall setup completed during upgrade")
    except Exception as exc:
        _logger.error("Firewall setup during upgrade failed: %s", exc)
