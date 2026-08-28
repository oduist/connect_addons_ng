import logging

from odoo import api, fields
from odoo.api import SUPERUSER_ID

from . import models
from . import controllers

_logger = logging.getLogger(__name__)


def post_init_hook(*args):
    """Start the trial clock at install and pull the initial Connect license /
    pricing. Mirrors the connect suite's per-module hook (see connect_twilio)."""
    try:
        if len(args) == 1:
            env = args[0]
        else:
            cr, registry = args
            env = api.Environment(cr, SUPERUSER_ID, {})
        module = env["ir.module.module"].search(
            [("name", "=", "connect_s3")], limit=1)
        if module:
            module.write({"create_date": fields.Datetime.now()})
        env["oduist.license"].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error("Error in connect_s3 post_init_hook: %s", str(e))
