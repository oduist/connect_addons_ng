"""Initialise the firewall portal user, secrets and agent singleton on
upgrade — Odoo 18 series counterpart of migrations/19.0.1.8.3.

Odoo only runs migrations whose folder name matches a version on the
upgrade path. The 19.x migration script never fires when the module is
upgraded inside an 18-series database (18.0.1.7.11 -> 18.0.1.8.0), so
this matching script is needed.
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
