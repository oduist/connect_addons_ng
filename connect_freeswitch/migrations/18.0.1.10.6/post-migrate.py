"""Generate freeswitch_webhook_token for existing installations (ADR-025).

18.0.1.10.5 added token authentication to every FreeSWITCH -> Odoo HTTP
endpoint (/freeswitch/xml and /freeswitch/webhook/*). The ORM backfills
the new column from the field default, but this script guarantees the
token exists even if the column was created empty. A random value means
the endpoints are locked (fail-closed) until the operator copies the
token into the FS_WEBHOOK_TOKEN env var of the FreeSWITCH container.

Idempotent: a second run finds the token already set and does nothing.
"""
import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.connect_freeswitch import ensure_webhook_token

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_webhook_token(env)
    _logger.info('connect_freeswitch: freeswitch_webhook_token ensured')
