"""Backfill auth_password for endpoints created before passphrase generation.

In 18.0.1.10.0 ``connect.endpoint.auth_password`` became an auto-generated,
read-only passphrase. Endpoints that predate this change may have an empty
password. This migration fills only those; endpoints with a password already
set (including weak manual ones) are left untouched, per the non-destructive
requirement.

Idempotent: re-running it finds no empty passwords on the second pass.
"""
import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.connect_freeswitch import backfill_endpoint_passwords

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    backfill_endpoint_passwords(env)
