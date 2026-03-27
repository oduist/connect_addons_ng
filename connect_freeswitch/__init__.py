from . import controllers
from . import models

import logging
from odoo import fields

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_freeswitch')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
    _ensure_acl_in_sofia_template(env)


def _ensure_acl_in_sofia_template(env):
    """Ensure apply-inbound-acl is present in config_sofia template."""
    try:
        template = env['connect.freeswitch.template'].search(
            [('key', '=', 'config_sofia')], limit=1)
        if not template:
            return
        acl_line = '<param name="apply-inbound-acl" value="gateways"/>'
        auth_line = '<param name="auth-calls" value="true"/>'
        for field in ('content', 'default_content'):
            content = template[field] or ''
            if acl_line not in content and auth_line in content:
                template[field] = content.replace(
                    auth_line, auth_line + '\n        ' + acl_line)
                _logger.info('Added apply-inbound-acl to config_sofia %s', field)
    except Exception as e:
        _logger.error('Error ensuring ACL in sofia template: %s', e)
