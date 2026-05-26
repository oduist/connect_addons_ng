"""Register ElevenLabs entry in connect.provider for existing installations.

post_init_hook only runs on fresh install. This script ensures DBs already
running connect_elevenlabs get the 'elevenlabs' row in connect.provider.
Idempotent — the helper upserts by `code`.
"""
import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.connect_elevenlabs import register_provider

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    register_provider(env)
    _logger.info('connect.provider: elevenlabs registered')
