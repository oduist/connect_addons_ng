from . import controllers
from . import models

import logging
import secrets

from odoo import fields

_logger = logging.getLogger(__name__)


def setup_threecx_api_key(env):
    """Idempotent bootstrap — called from post_init_hook. Generates the
    shared webhook API key if missing so the CRM template can be
    downloaded right after install."""
    settings = env['connect.settings'].sudo()
    if not settings.get_param('threecx_api_key'):
        settings.set_param('threecx_api_key', secrets.token_urlsafe(24))


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search(
            [('name', '=', 'connect_3cx')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
        setup_threecx_api_key(env)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
