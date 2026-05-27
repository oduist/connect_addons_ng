"""Migrate Twilio settings off `connect.settings` into the new singleton
`connect.provider.twilio.config` (ADR-025 / ODU-22).

Field-name renames (strip `twilio_` prefix where present):
  twilio_api_key       → api_key
  twilio_api_secret    → api_secret
  display_twilio_api_secret → display_api_secret
  twilio_balance       → balance
  twilio_region        → region
  twilio_edge          → edge
  twilio_auto_sync     → auto_sync
  twilio_verify_requests → verify_requests
  account_sid / auth_token / display_auth_token / fetch_call_prices
    keep their names.
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_COLUMNS = [
    # (legacy_on_connect_settings, new_on_provider_config)
    ('account_sid', 'account_sid'),
    ('auth_token', 'auth_token'),
    ('display_auth_token', 'display_auth_token'),
    ('twilio_api_key', 'api_key'),
    ('twilio_api_secret', 'api_secret'),
    ('display_twilio_api_secret', 'display_api_secret'),
    ('twilio_balance', 'balance'),
    ('twilio_region', 'region'),
    ('twilio_edge', 'edge'),
    ('twilio_auto_sync', 'auto_sync'),
    ('twilio_verify_requests', 'verify_requests'),
    ('fetch_call_prices', 'fetch_call_prices'),
]


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    # Ensure singleton exists.
    cr.execute("SELECT id FROM connect_provider_twilio_config LIMIT 1")
    row = cr.fetchone()
    if row:
        singleton_id = row[0]
    else:
        # `region` and `edge` are required=True with ORM defaults that
        # raw INSERT bypasses; supply them explicitly. Legacy column
        # values (if present) overwrite these in the UPDATE below.
        cr.execute(
            "INSERT INTO connect_provider_twilio_config "
            "(region, edge, create_uid, write_uid, create_date, write_date) "
            "VALUES ('us1', 'ashburn', 1, 1, NOW(), NOW()) RETURNING id"
        )
        singleton_id = cr.fetchone()[0]

    legacy_present = [
        (legacy, new) for legacy, new in LEGACY_COLUMNS
        if _col_exists(cr, 'connect_settings', legacy)
    ]

    if legacy_present:
        select_parts = ', '.join(f'"{legacy}"' for legacy, _ in legacy_present)
        cr.execute(f'SELECT {select_parts} FROM connect_settings LIMIT 1')
        row = cr.fetchone()
        if row:
            sets, params = [], []
            for (legacy, new), value in zip(legacy_present, row):
                if value is not None:
                    sets.append(f'"{new}" = %s')
                    params.append(value)
            if sets:
                params.append(singleton_id)
                cr.execute(
                    f'UPDATE connect_provider_twilio_config '
                    f'SET {", ".join(sets)} WHERE id = %s',
                    params,
                )
                _logger.info(
                    'connect_twilio: migrated %d fields from connect_settings',
                    len(sets),
                )

    for legacy, _ in LEGACY_COLUMNS:
        if _col_exists(cr, 'connect_settings', legacy):
            cr.execute(f'ALTER TABLE connect_settings DROP COLUMN "{legacy}"')
            _logger.info('connect_twilio: dropped connect_settings.%s', legacy)
