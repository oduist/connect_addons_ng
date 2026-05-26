"""Backfill connect.{call,number,callflow,exten}.provider_id from
provider-specific signal columns when present.

Idempotent — every UPDATE is gated on `provider_id IS NULL`, so re-running
the script is safe. The script is also defensive about installed
providers: it reads the `connect.provider` registry at runtime and only
backfills for providers that actually exist.

Rows that have no telltale signal (notably most `connect.call` rows on a
FreeSWITCH-only deploy — the FS module does not stamp a UUID on
`connect_call`) stay NULL. The façade dispatch in ODU-4 will fall back
to `connect.provider._default()` for those.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _backfill(cr, table, column, provider_id, *, not_null=True):
    """UPDATE <table> SET provider_id=<provider_id> WHERE provider_id IS NULL AND <column> IS NOT NULL."""
    if not provider_id or not _col_exists(cr, table, column):
        return 0
    cond = f'"{column}" IS NOT NULL' if not_null else f'"{column}" = TRUE'
    cr.execute(
        f'UPDATE {table} SET provider_id = %s '
        f'WHERE provider_id IS NULL AND {cond}',
        (provider_id,),
    )
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    by_code = {
        p.code: p.id
        for p in env['connect.provider']
            .with_context(active_test=False)
            .search([])
    }
    twilio = by_code.get('twilio')
    freeswitch = by_code.get('freeswitch')
    elevenlabs = by_code.get('elevenlabs')

    counts = {}
    counts['call/twilio'] = _backfill(cr, 'connect_call', 'call_sid', twilio)
    counts['call/elevenlabs'] = _backfill(
        cr, 'connect_call', 'elevenlabs_conversation_id', elevenlabs)

    counts['number/twilio'] = _backfill(cr, 'connect_number', 'sid', twilio)
    counts['number/freeswitch'] = _backfill(
        cr, 'connect_number', 'fs_fifo_id', freeswitch)
    counts['number/elevenlabs'] = _backfill(
        cr, 'connect_number', 'elevenlabs_agent', elevenlabs)

    counts['callflow/freeswitch'] = _backfill(
        cr, 'connect_callflow', 'fs_fifo_id', freeswitch)

    # connect.exten — `dst` is a Reference field; the underlying storage
    # is the `model` text column (model name) + `res_id`. Use the ORM
    # so we share the existing dst → model decoding logic.
    if any([twilio, freeswitch, elevenlabs]):
        Exten = env['connect.exten'].search([('provider_id', '=', False)])
        for exten in Exten:
            model = exten.model or ''
            if elevenlabs and model.startswith('connect.elevenlabs_'):
                exten.provider_id = elevenlabs
                counts['exten/elevenlabs'] = counts.get('exten/elevenlabs', 0) + 1
            elif freeswitch and model.startswith('connect.fs_'):
                exten.provider_id = freeswitch
                counts['exten/freeswitch'] = counts.get('exten/freeswitch', 0) + 1
            # No Twilio-specific exten dst target today — twiml lives on
            # connect.number, not connect.exten.

    _logger.info(
        'connect.provider_id backfill: %s',
        ', '.join(f'{k}={v}' for k, v in counts.items() if v),
    )
