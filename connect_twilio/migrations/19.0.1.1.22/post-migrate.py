"""Migrate Twilio settings back from the `connect.provider.twilio.config`
singleton onto `connect.settings` (ADR-031 / ODU-46).

Inverse of `19.0.1.1.9`: restore the prefixed columns on
`connect_settings` and copy the single config-table row across. The
`connect_provider_twilio_config` model is removed with this release, so
Odoo drops its table during the upgrade; this script only carries the
data. Idempotent via `information_schema`.

Name map (config column -> connect_settings column):
  account_sid          -> account_sid
  auth_token           -> auth_token
  display_auth_token   -> display_auth_token
  api_key              -> twilio_api_key
  api_secret           -> twilio_api_secret
  display_api_secret   -> display_twilio_api_secret
  balance              -> twilio_balance
  region               -> twilio_region
  edge                 -> twilio_edge
  auto_sync            -> twilio_auto_sync
  verify_requests      -> twilio_verify_requests
  fetch_call_prices    -> fetch_call_prices
"""
import logging

_logger = logging.getLogger(__name__)

# (config_column, connect_settings_column, sql_type)
COLUMNS = [
    ('account_sid', 'account_sid', 'varchar'),
    ('auth_token', 'auth_token', 'varchar'),
    ('display_auth_token', 'display_auth_token', 'varchar'),
    ('api_key', 'twilio_api_key', 'varchar'),
    ('api_secret', 'twilio_api_secret', 'varchar'),
    ('display_api_secret', 'display_twilio_api_secret', 'varchar'),
    ('balance', 'twilio_balance', 'varchar'),
    ('region', 'twilio_region', 'varchar'),
    ('edge', 'twilio_edge', 'varchar'),
    ('auto_sync', 'twilio_auto_sync', 'boolean'),
    ('verify_requests', 'twilio_verify_requests', 'boolean'),
    ('fetch_call_prices', 'fetch_call_prices', 'boolean'),
]


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    # The ORM creates the new columns from the connect_twilio fields on
    # upgrade; add them defensively so the copy below is self-contained.
    for _src, dst, sqltype in COLUMNS:
        if not _col_exists(cr, 'connect_settings', dst):
            cr.execute(
                f'ALTER TABLE connect_settings ADD COLUMN "{dst}" {sqltype}')

    if not _table_exists(cr, 'connect_provider_twilio_config'):
        _logger.info('connect_twilio: no config table to migrate from')
        return

    cr.execute("SELECT id FROM connect_settings ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.info('connect_twilio: no connect_settings row yet')
        return
    settings_id = row[0]

    present = [
        (src, dst) for src, dst, _t in COLUMNS
        if _col_exists(cr, 'connect_provider_twilio_config', src)
    ]
    if not present:
        return

    select_parts = ', '.join(f'"{src}"' for src, _dst in present)
    cr.execute(
        f'SELECT {select_parts} FROM connect_provider_twilio_config '
        f'ORDER BY id LIMIT 1')
    cfg_row = cr.fetchone()
    if not cfg_row:
        return

    sets, params = [], []
    for (src, dst), value in zip(present, cfg_row):
        if value is not None:
            sets.append(f'"{dst}" = %s')
            params.append(value)
    if sets:
        params.append(settings_id)
        cr.execute(
            f'UPDATE connect_settings SET {", ".join(sets)} WHERE id = %s',
            params,
        )
        _logger.info(
            'connect_twilio: restored %d fields onto connect_settings',
            len(sets),
        )

    # Odoo deletes the obsolete model's ir.model record but skips the SQL
    # DROP (the model is already absent from the registry by now), leaving an
    # orphan table. Drop it explicitly so the revert is clean.
    cr.execute('DROP TABLE IF EXISTS connect_provider_twilio_config CASCADE')
