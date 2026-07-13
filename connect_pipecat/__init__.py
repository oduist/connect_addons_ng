import logging

from odoo import fields

from . import controllers, models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search(
            [('name', '=', 'connect_pipecat')], limit=1,
        )
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as exc:
        _logger.error('Error in connect_pipecat post_init_hook: %s', exc)
