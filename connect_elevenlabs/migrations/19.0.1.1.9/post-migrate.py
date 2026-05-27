"""Migrate ElevenLabs settings off `connect.settings` into the new
singleton `connect.provider.elevenlabs.config` (ADR-025 / ODU-11).

Strategy:
1. Read the existing values from `connect_settings.elevenlabs_*` columns
   if they're still present (information_schema check — the columns are
   defined on `connect.settings` by this module's previous versions; on
   a fresh install they don't exist and the migration becomes a no-op
   except for creating an empty singleton).
2. INSERT into `connect_provider_elevenlabs_config` with those values.
3. DROP the old columns from `connect_settings`.

Raw SQL throughout because this post-migrate runs at module upgrade
time — `connect_elevenlabs/__init__.py` may have already loaded the new
model, but the columns we're reading from are about to be dropped from
under the ORM, so we can't safely use the ORM to read the old values.
"""
import logging
import uuid

_logger = logging.getLogger(__name__)

LEGACY_COLUMNS = [
    ('elevenlabs_enabled', 'enabled'),
    ('elevenlabs_api_key', 'api_key'),
    ('display_elevenlabs_api_key', 'display_api_key'),
    ('elevenlabs_agent_token', 'agent_token'),
    ('elevenlabs_post_call_webhook_secret', 'post_call_webhook_secret'),
    ('display_elevenlabs_post_call_webhook_secret', 'display_post_call_webhook_secret'),
]
# elevenlabs_voice is a Many2one — fk needs special handling
LEGACY_M2O_COLUMNS = [
    ('elevenlabs_voice', 'voice'),
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

    # 1. Ensure the singleton exists. Insert one if not present.
    cr.execute("SELECT id FROM connect_provider_elevenlabs_config LIMIT 1")
    row = cr.fetchone()
    if row:
        singleton_id = row[0]
    else:
        # agent_token is required=True; ORM default would set it but raw
        # INSERT skips that — generate one in Python. The legacy column
        # value (if present) overrides this default in step 2 below.
        cr.execute(
            "INSERT INTO connect_provider_elevenlabs_config "
            "(agent_token, create_uid, write_uid, create_date, write_date) "
            "VALUES (%s, 1, 1, NOW(), NOW()) RETURNING id",
            (str(uuid.uuid4()),),
        )
        singleton_id = cr.fetchone()[0]

    # 2. Copy values from connect_settings where the legacy columns still exist.
    legacy_present = [
        (legacy, new) for legacy, new in LEGACY_COLUMNS
        if _col_exists(cr, 'connect_settings', legacy)
    ]
    legacy_m2o_present = [
        (legacy, new) for legacy, new in LEGACY_M2O_COLUMNS
        if _col_exists(cr, 'connect_settings', legacy)
    ]

    if legacy_present or legacy_m2o_present:
        select_parts = ', '.join(
            f'"{legacy}"' for legacy, _ in legacy_present + legacy_m2o_present
        )
        cr.execute(
            f'SELECT {select_parts} FROM connect_settings LIMIT 1'
        )
        row = cr.fetchone()
        if row:
            sets = []
            params = []
            for (legacy, new), value in zip(legacy_present + legacy_m2o_present, row):
                if value is not None:
                    sets.append(f'"{new}" = %s')
                    params.append(value)
            if sets:
                params.append(singleton_id)
                cr.execute(
                    f'UPDATE connect_provider_elevenlabs_config '
                    f'SET {", ".join(sets)} WHERE id = %s',
                    params,
                )
                _logger.info(
                    'connect_elevenlabs: migrated %d fields from connect_settings',
                    len(sets),
                )

    # 3. Drop the old columns from connect_settings now that values are moved.
    for legacy, _ in LEGACY_COLUMNS + LEGACY_M2O_COLUMNS:
        if _col_exists(cr, 'connect_settings', legacy):
            cr.execute(f'ALTER TABLE connect_settings DROP COLUMN "{legacy}"')
            _logger.info('connect_elevenlabs: dropped connect_settings.%s', legacy)
