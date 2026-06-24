from . import models

import logging
from odoo import fields

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_crm')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
