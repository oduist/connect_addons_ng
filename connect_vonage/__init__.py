from . import models
from . import controllers

import logging
import re

from odoo import fields

_logger = logging.getLogger(__name__)


def ensure_vonage_usernames(env):
    """Backfill provider-safe usernames and restore the required constraint."""
    users = env['connect.user'].sudo().with_context(active_test=False).search(
        [], order='id')
    used = {
        user.username.casefold()
        for user in users
        if user.username
    }
    for user in users.filtered(lambda rec: not rec.username):
        base = re.sub(r'[^A-Za-z0-9]', '', user.user.login or '')
        base = base or 'user{}'.format(user.user.id or user.id)
        username = base
        suffix = 1
        while username.casefold() in used:
            suffix += 1
            username = '{}{}'.format(base, suffix)
        user.with_context(skip_sync=True).write({'username': username})
        used.add(username.casefold())

    users.flush_recordset(['username'])
    env.cr.execute(
        'ALTER TABLE connect_user ALTER COLUMN username SET NOT NULL')


def post_init_hook(env):
    ensure_vonage_usernames(env)
    try:
        module = env['ir.module.module'].search(
            [('name', '=', 'connect_vonage')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
