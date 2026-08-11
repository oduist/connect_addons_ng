"""Backfill Vonage usernames on databases upgraded from 18.0.1.0.0."""

from odoo import api, SUPERUSER_ID

from odoo.addons.connect_vonage import ensure_vonage_usernames


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_vonage_usernames(env)
