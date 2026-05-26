"""Register FreeSWITCH entry in connect.provider for existing installations.

post_init_hook only runs on fresh install. For DBs already running
connect_freeswitch < 19.0.1.8.19 the connect.provider table won't have
the 'freeswitch' row until this script populates it. Idempotent —
the helper upserts by `code`.
"""
import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.connect_freeswitch import register_provider

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    register_provider(env)
    _logger.info('connect.provider: freeswitch registered')
