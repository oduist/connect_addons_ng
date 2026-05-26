from . import models
from . import controllers
from . import wizard

import logging
from odoo import fields

_logger = logging.getLogger(__name__)


def register_provider(env):
    """Idempotent upsert of the Twilio entry in connect.provider.
    Called from post_init_hook and from per-version post-migration scripts."""
    env['connect.provider'].sudo()._register_code(code='twilio', name='Twilio', sequence=10)


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_twilio')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
        register_provider(env)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))


def uninstall_hook(env):
    try:
        env['connect.provider'].sudo()._deactivate('twilio')
    except Exception as e:
        _logger.error('Error in uninstall_hook: %s', str(e))
